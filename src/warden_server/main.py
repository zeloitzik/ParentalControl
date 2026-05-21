import sys
import os
import socket
import threading
import time
from datetime import datetime
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
        self.db_lock = threading.RLock()
        self.locked_sessions = set()
        self.locked_sessions_lock = threading.Lock()

        self.private_key = CryptoManager.generate_rsa_keypair()
        self.public_key_bytes = CryptoManager.get_public_key_bytes(self.private_key)
        self.is_running = True

    def start(self):
        self._cleanup_stale_sessions()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.logger.info(f"Warden Server listening on {self.host}:{self.port} (Raw Sockets)")
        print(f"[SERVER] Starting Warden Server on {self.host}:{self.port}")
        print("[SERVER] Waiting for client connections...")

        self.lock_monitor_thread = threading.Thread(target=self._lock_monitor_loop, daemon=True)
        self.lock_monitor_thread.start()
        self.logger.info("Lock monitor thread started.")
        print("[SERVER] Lock monitor thread started.")

        self.status_printer_thread = threading.Thread(target=self._status_printer_loop, daemon=True)
        self.status_printer_thread.start()
        print("[SERVER] Client status display thread started.")

        try:
            while self.is_running:
                client_sock, addr = self.server_socket.accept()
                self.logger.info(f"Accepted connection from {addr}")
                print(f"[SERVER] Accepted connection from {addr}")
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
        print("[SERVER] Server stopped.")

    def _cleanup_stale_sessions(self):
        """Close any RUNNING sessions left over from a previous server run."""
        with self.db_lock:
            cursor = self.db.db.cursor(buffered=True)
            try:
                cursor.execute(
                    "UPDATE app_sessions SET status='CLOSED', end_time=NOW() "
                    "WHERE status='RUNNING'"
                )
                affected = cursor.rowcount
                self.db.db.commit()
                if affected:
                    self.logger.info("Cleaned up %d stale RUNNING sessions from previous run.", affected)
            finally:
                cursor.close()

    def _lock_monitor_loop(self):
        self.logger.info("Lock monitor loop entering periodic scan mode.")
        while self.is_running:
            try:
                self._check_active_sessions_for_time_expired()
            except Exception as e:
                self.logger.exception(f"Lock monitor error: {e}")
            time.sleep(10)

    def _status_printer_loop(self):
        while self.is_running:
            self._display_connected_client_limits()
            time.sleep(10)

    def _display_connected_client_limits(self):
        with self.clients_lock:
            active_sids = list(self.clients_by_sid.keys())

        print("\n[SERVER STATUS] Connected clients and current time limits:")
        if not active_sids:
            print("[SERVER STATUS] No clients currently connected.")
            return

        for sid in active_sids:
            user_info = self._get_client_session_status(sid)
            if not user_info:
                print(f"[SERVER STATUS] SID {sid} connected, no user record found.")
                continue

            name = user_info.get("name", "Unknown")
            print(f"[SERVER STATUS] SID {sid} | User: {name}")
            apps = user_info.get("apps", [])
            if not apps:
                print("  [SERVER STATUS] No configured rules or active app sessions.")
                continue

            for app_info in apps:
                print(
                    f"  - App: {app_info['app']} | Allowed: {app_info['allowed']} min | "
                    f"Used: {app_info['used']} min | Active: {app_info['active']} min | "
                    f"Remaining: {app_info['remaining']} min"
                )

    def _get_client_session_status(self, sid):
        with self.db_lock:
            user_id = self.db.get_user_id_by_sid(sid)
            if not user_id:
                return None

            cursor = self.db.db.cursor(buffered=True)
            try:
                cursor.execute("SELECT name FROM users WHERE id=%s", (user_id,))
                row = cursor.fetchone()
                name = row[0] if row else None

                cursor.execute("SELECT app_name FROM app_rules WHERE user_id=%s", (user_id,))
                rules = cursor.fetchall()
            finally:
                cursor.close()

        # db_lock released — safe to call _get_app_time_status which acquires its own lock
        apps = []
        for app_name, in rules:
            status = self._get_app_time_status(sid, app_name)
            if not status:
                continue
            apps.append({
                "app": app_name,
                "allowed": status["allowed"],
                "used": status["used"],
                "active": status["active"],
                "remaining": status["remaining"]
            })

        return {"name": name, "apps": apps}

    def _get_app_time_status(self, sid, app_name):
        with self.db_lock:
            user_id = self.db.get_user_id_by_sid(sid)
            if not user_id:
                return None

            rule = self.db.get_app_rule(user_id, app_name)
            if not rule or rule.get("allowed_minutes") is None:
                return None

            try:
                allowed = float(rule["allowed_minutes"])
            except (TypeError, ValueError):
                self.logger.warning(
                    "Malformed allowed_minutes for user_id=%s app=%s: %r; defaulting to allow",
                    user_id,
                    app_name,
                    rule.get("allowed_minutes"),
                )
                return None

            try:
                used = float(self.db.get_used_time_today(user_id, app_name) or 0.0)
            except (TypeError, ValueError):
                used = 0.0

            try:
                active = float(self.db.get_active_session_time(user_id, app_name) or 0.0)
            except (TypeError, ValueError):
                active = 0.0

            remaining = max(allowed - (used + active), 0.0)
            return {
                "allowed": round(allowed, 2),
                "used": round(used, 2),
                "active": round(active, 2),
                "remaining": round(remaining, 2),
            }

    def _check_active_sessions_for_time_expired(self):
        sql = """
            SELECT s.id, u.sid, s.app_name, s.start_time, r.allowed_minutes,
                   IFNULL(SUM(ul.duration), 0) AS used_minutes
            FROM app_sessions s
            JOIN users u ON u.id = s.user_id
            JOIN app_rules r ON r.user_id = s.user_id AND r.app_name = s.app_name
            LEFT JOIN usage_logs ul ON ul.user_id = s.user_id
              AND ul.app_name = s.app_name
              AND DATE(ul.start_time)=CURDATE()
            WHERE s.status = 'RUNNING'
            GROUP BY s.id, u.sid, s.app_name, s.start_time, r.allowed_minutes
        """
        with self.db_lock:
            cursor = self.db.db.cursor(buffered=True)
            try:
                cursor.execute(sql)
                rows = cursor.fetchall()
            finally:
                cursor.close()
        now = datetime.now()

        for session_id, sid, app_name, start_time, allowed_minutes, used_minutes in rows:
            status = self._get_app_time_status(sid, app_name)
            if not status:
                continue

            if status["remaining"] <= 0.0:
                with self.locked_sessions_lock:
                    if session_id in self.locked_sessions:
                        continue

                self.logger.info(
                    f"Session overdue for SID {sid}, app {app_name}: "
                    f"used={status['used']:.2f}, active={status['active']:.2f}, allowed={status['allowed']}"
                )
                if self._push_lock_command(sid, app_name):
                    with self.locked_sessions_lock:
                        self.locked_sessions.add(session_id)

    def _push_command(self, sid, action, app=None):
        client_info = None
        with self.clients_lock:
            client_info = self.clients_by_sid.get(sid)

        if not client_info:
            self.logger.warning(f"No connected client found for SID {sid} to send {action} command")
            return False

        self.logger.info(f"Pushing {action} command to SID {sid}" + (f" for app {app}" if app else ""))

        try:
            payload = {"action": action}
            if app:
                payload["app"] = app
            msg = Protocol.serialize_message(action, payload)
            encrypted = CryptoManager.encrypt_aes(client_info["aes_key"], msg)
            with client_info["write_lock"]:
                Protocol.send_packet(client_info["sock"], encrypted)
            self.logger.info(f"Sent {action} command to {sid}")
            return True
        except Exception as e:
            self.logger.exception(f"Failed to send {action} command to {sid}: {e}")
            return False

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
            socket_write_lock = threading.Lock()

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
                            self.clients_by_sid[client_sid] = {"sock": client_sock, "aes_key": aes_key, "write_lock": socket_write_lock}
                        self.logger.info(f"Registered client for SID {client_sid}")
                        print(f"[SERVER] Registered client SID {client_sid} from {addr}")

                with socket_write_lock:
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
                        print(f"[SERVER] Unregistered client SID {s} from {addr}")
            except Exception:
                pass
            self.logger.info(f"Connection closed for {addr}")
            print(f"[SERVER] Connection closed for {addr}")

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
                        status = self._get_app_time_status(sid, app)
                        if status and status["remaining"] <= 0.0:
                            self._push_lock_command(sid, app)
                except Exception:
                    self.logger.exception("Error while evaluating lock condition for event")

                return {"status": "ok"}
                
            elif cmd == "check_app":
                allowed = self.engine.can_user_run_app(data["sid"], data["app"])
                
                with self.db_lock:
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
                with self.db_lock:
                    cursor = self.db.db.cursor(buffered=True)
                    try:
                        cursor.execute("SELECT id, name FROM users WHERE type='child'")
                        users = cursor.fetchall()

                        for user_id, name in users:
                            user_data = {
                                "name": name,
                                "apps": []
                            }

                            cursor.execute("SELECT app_name, allowed_minutes FROM app_rules WHERE user_id=%s", (user_id,))
                            rules = cursor.fetchall()

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
                    finally:
                        cursor.close()
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
                
                # Push unlock to kill lock screen
                with self.db_lock:
                    cursor = self.db.db.cursor(buffered=True)
                    try:
                        cursor.execute("SELECT sid FROM users WHERE id=%s", (user_id,))
                        row = cursor.fetchone()
                    finally:
                        cursor.close()
                if row:
                    self._push_command(row[0], "unlock", app_name)
                    
                return {"status": "success"}
                
            elif cmd == "unlock_app" or cmd == "UNLOCK_APP":
                user_id = data["user_id"]
                app_name = data["app"]
                # 1440 mins = 24 hours (forces unlock)
                self.db.update_app_rule(user_id, app_name, 1440)
                
                # Push unlock to kill lock screen
                with self.db_lock:
                    cursor = self.db.db.cursor(buffered=True)
                    try:
                        cursor.execute("SELECT sid FROM users WHERE id=%s", (user_id,))
                        row = cursor.fetchone()
                    finally:
                        cursor.close()
                if row:
                    self._push_command(row[0], "unlock", app_name)
                    
                return {"status": "success"}
                
            elif cmd == "lock_app":
                user_id = data["user_id"]
                app_name = data["app"]
                
                # Verify if process is running before pushing lock
                is_running = False
                with self.db_lock:
                    session = self.db.get_running_session(user_id, app_name)
                    if session:
                        is_running = True
                
                # Set allowed_minutes=0 to lock the app immediately
                self.db.update_app_rule(user_id, app_name, 0)
                self.logger.info(f"App '{app_name}' locked for user_id={user_id} via admin panel. Running={is_running}")
                
                # Push lock command to connected client if online AND app is running
                if is_running:
                    with self.db_lock:
                        cursor = self.db.db.cursor(buffered=True)
                        try:
                            cursor.execute("SELECT sid FROM users WHERE id=%s", (user_id,))
                            row = cursor.fetchone()
                        finally:
                            cursor.close()
                    if row:
                        self._push_command(row[0], "time_up", app_name)
                return {"status": "success"}

            elif cmd == "emergency_unlock":
                user_id = data["user_id"]
                with self.db_lock:
                    cursor = self.db.db.cursor(buffered=True)
                    try:
                        cursor.execute("SELECT sid FROM users WHERE id=%s", (user_id,))
                        row = cursor.fetchone()
                    finally:
                        cursor.close()
                if row:
                    self._push_command(row[0], "emergency_unlock")
                return {"status": "success"}

            elif cmd == "get_known_apps":
                user_id = data["user_id"]
                with self.db_lock:
                    apps = self.db.get_known_apps(user_id)
                return {"status": "success", "apps": apps}

            else:
                return {"error": "Unknown command"}
        except Exception as e:
            self.logger.exception(f"Command execution error: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    server = WardenServer()
    server.start()
