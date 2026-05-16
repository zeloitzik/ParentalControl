import sys
import os
import socket
import threading
from pathlib import Path

# Add src to sys.path if running as script to allow absolute imports
current_dir = Path(__file__).resolve().parent
if (current_dir.parent / "warden_core").exists():
    sys.path.append(str(current_dir.parent))

from warden_core.database import DatabaseManager
from warden_core.engine import ServerEngine
from warden_core.setup_logger import my_logger
from warden_core.crypto import CryptoManager
from warden_core.protocol import Protocol

class WardenServer:
    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self.db = DatabaseManager()
        self.engine = ServerEngine(self.db)
        self.logger = my_logger("server", "server.log").setup_logger()
        
        # Map of authenticated clients by SID -> {sock, aes_key}
        self.clients_by_sid = {}
        self.clients_lock = threading.Lock()

        self.private_key = CryptoManager.generate_rsa_keypair()
        self.public_key_bytes = CryptoManager.get_public_key_bytes(self.private_key)
        self.is_running = True

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.logger.info(f"Warden Server listening on {self.host}:{self.port} (Raw Sockets)")

        try:
            while self.is_running:
                client_sock, addr = self.server_socket.accept()
                self.logger.info(f"Accepted connection from {addr}")
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_sock, addr),
                    daemon=True
                )
                client_thread.start()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            self.logger.exception(f"Server error: {e}")
            if self.is_running:
                self.stop()

    def stop(self):
        self.is_running = False
        if hasattr(self, 'server_socket'):
            self.server_socket.close()
        self.logger.info("Server stopped.")

    def handle_client(self, client_sock, addr):
        try:
            # --- Handshake Phase ---
            # 1. Send RSA public key
            Protocol.send_packet(client_sock, self.public_key_bytes)
            
            # 2. Receive RSA-encrypted AES key from client
            encrypted_aes_key = Protocol.recv_packet(client_sock)
            if not encrypted_aes_key:
                self.logger.error("Failed to receive AES key during handshake.")
                return
                
            aes_key = CryptoManager.decrypt_rsa(self.private_key, encrypted_aes_key)
            self.logger.info(f"Secure AES session established with {addr}")

            # Track whether this socket has completed auth and which SID it belongs to
            client_sid = None

            # --- Communication Loop ---
            while True:
                encrypted_payload = Protocol.recv_packet(client_sock)
                if not encrypted_payload:
                    break # Client gracefully closed
                    
                decrypted_bytes = CryptoManager.decrypt_aes(aes_key, encrypted_payload)
                cmd, data = Protocol.deserialize_message(decrypted_bytes)

                response_data = self.process_command(cmd, data)

                # If this was authentication and succeeded, register the client by SID
                if cmd == "auth" and isinstance(response_data, dict) and response_data.get("status") == "authenticated":
                    client_sid = None
                    if isinstance(data, dict):
                        client_sid = data.get("sid")
                    if client_sid:
                        with self.clients_lock:
                            self.clients_by_sid[client_sid] = {"sock": client_sock, "aes_key": aes_key}
                        self.logger.info(f"Registered client for SID {client_sid}")

                response_bytes = Protocol.serialize_message("response", response_data)
                encrypted_response = CryptoManager.encrypt_aes(aes_key, response_bytes)
                Protocol.send_packet(client_sock, encrypted_response)
                
        except ConnectionResetError:
            self.logger.warning(f"Connection reset by {addr}")
        except Exception as e:
            self.logger.exception(f"Error handling client {addr}: {e}")
        finally:
            client_sock.close()
            # Unregister any SID that used this socket
            try:
                with self.clients_lock:
                    to_remove = [s for s,info in self.clients_by_sid.items() if info.get("sock") == client_sock]
                    for s in to_remove:
                        del self.clients_by_sid[s]
                        self.logger.info(f"Unregistered client for SID {s}")
            except Exception:
                pass
            self.logger.info(f"Connection closed for {addr}")

    def process_command(self, cmd, data):
        try:
            if cmd == "auth":
                # Handle client authentication/registration
                sid = data.get("sid")
                purpose = data.get("purpose", "registration")
                self.logger.info(f"Client authentication: SID={sid}, purpose={purpose}")
                return {"status": "authenticated", "message": "Client registered successfully"}
                
            elif cmd == "event":
                self.engine.process_event(data)
                self.logger.info("Event processed: %s", data)

                # After processing the event, check whether the app is allowed
                try:
                    sid = data.get("sid") if isinstance(data, dict) else None
                    app = None
                    if isinstance(data, dict):
                        app = data.get("metadata", {}).get("app")

                    if sid and app:
                        allowed = self.engine.can_user_run_app(sid, app)
                        if not allowed:
                            # If we have an authenticated client for this SID, push a lock/time_up command
                            client_info = None
                            with self.clients_lock:
                                client_info = self.clients_by_sid.get(sid)

                            if client_info:
                                try:
                                    lock_payload = {"action": "time_up", "app": app}
                                    lock_msg = Protocol.serialize_message("time_up", lock_payload)
                                    encrypted = CryptoManager.encrypt_aes(client_info["aes_key"], lock_msg)
                                    Protocol.send_packet(client_info["sock"], encrypted)
                                    self.logger.info(f"Sent lock command to {sid} for app {app}")
                                except Exception as e:
                                    self.logger.exception(f"Failed to send lock command to {sid}: {e}")
                            else:
                                self.logger.warning(f"No connected client found for SID {sid} to send lock command")
                except Exception:
                    self.logger.exception("Error while evaluating lock condition for event")

                return {"status": "ok"}
                
            elif cmd == "check_app":
                allowed = self.engine.can_user_run_app(data["sid"], data["app"])
                
                user_id = self.db.get_user_id_by_sid(data["sid"])
                used_minutes = 0.0
                if user_id:
                    used_today = float(self.db.get_used_time_today(user_id, data["app"]))
                    active_time = float(self.db.get_active_session_time(user_id, data["app"]))
                    used_minutes = used_today + active_time
                    
                return {
                    "allowed": allowed,
                    "used_minutes": round(used_minutes, 2)
                }
                
            elif cmd == "dashboard":
                result = []
                self.db.cursor.execute("SELECT id, name FROM users WHERE type='child'")
                users = self.db.cursor.fetchall()

                for user_id, name in users:
                    user_data = {
                        "name": name,
                        "apps": []
                    }

                    self.db.cursor.execute("SELECT app_name, allowed_minutes FROM app_rules WHERE user_id=%s", (user_id,))
                    rules = self.db.cursor.fetchall()

                    for app_name, allowed in rules:
                        used = float(self.db.get_used_time_today(user_id, app_name))
                        active = float(self.db.get_active_session_time(user_id, app_name))
                        total = used + active

                        user_data["apps"].append({
                            "app": app_name,
                            "used": round(total, 2),
                            "allowed": float(allowed) if allowed is not None else 0.0
                        })
                    result.append(user_data)
                return {"status": "success", "data": result}
                
            elif cmd == "update_rule":
                user_id = data["user_id"]
                app_name = data["app"]
                allowed = data["allowed"]
                if allowed == 0:
                    self.db.delete_app_rule(user_id, app_name)
                else:
                    self.db.update_app_rule(user_id, app_name, allowed)
                return {"status": "success"}
                
            elif cmd == "add_time":
                user_id = data["user_id"]
                app_name = data["app"]
                added_minutes = data["minutes"]
                
                rule = self.db.get_app_rule(user_id, app_name)
                if rule:
                    new_limit = rule["allowed_minutes"] + added_minutes
                    self.db.update_app_rule(user_id, app_name, new_limit)
                else:
                    # if no rule existed, giving time means giving an explicit allowance
                    self.db.update_app_rule(user_id, app_name, 120 + added_minutes) 
                return {"status": "success"}
                
            elif cmd == "unlock_app":
                user_id = data["user_id"]
                app_name = data["app"]
                # 1440 mins = 24 hours (forces unlock)
                self.db.update_app_rule(user_id, app_name, 1440)
                return {"status": "success"}
                
            else:
                return {"error": "Unknown command"}
        except Exception as e:
            self.logger.exception(f"Command execution error: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    server = WardenServer()
    server.start()
