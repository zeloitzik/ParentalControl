import sys
import os
import socket
import threading
from pathlib import Path

# Add src to sys.path if running as script to allow absolute imports
current_dir = Path(__file__).resolve().parent
if (current_dir.parent / "warden_core").exists():
    sys.path.append(str(current_dir.parent.parent))

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

            # --- Communication Loop ---
            while True:
                encrypted_payload = Protocol.recv_packet(client_sock)
                if not encrypted_payload:
                    break # Client gracefully closed
                    
                decrypted_bytes = CryptoManager.decrypt_aes(aes_key, encrypted_payload)
                cmd, data = Protocol.deserialize_message(decrypted_bytes)
                
                response_data = self.process_command(cmd, data)
                
                response_bytes = Protocol.serialize_message("response", response_data)
                encrypted_response = CryptoManager.encrypt_aes(aes_key, response_bytes)
                Protocol.send_packet(client_sock, encrypted_response)
                
        except ConnectionResetError:
            self.logger.warning(f"Connection reset by {addr}")
        except Exception as e:
            self.logger.exception(f"Error handling client {addr}: {e}")
        finally:
            client_sock.close()
            self.logger.info(f"Connection closed for {addr}")

    def process_command(self, cmd, data):
        try:
            if cmd == "event":
                self.engine.process_event(data)
                self.logger.info("Event processed: %s", data)
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
