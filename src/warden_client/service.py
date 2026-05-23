import os
import sys
import socket
import threading
import time
import logging
import subprocess
import signal
from pathlib import Path

# Add src directory to path so warden_core modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from warden_core.protocol import Protocol
from warden_core.sid_helper import SID
from warden_core.setup_logger import my_logger
from warden_core.crypto import CryptoManager
from warden_client.time_tracker import TimeTracker

DEFAULT_SERVER_HOST = "192.168.1.213"
DEFAULT_SERVER_PORT = 8000
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 30.0
LOCK_COMMANDS = {"lock", "lock_screen", "times_up", "timeout", "time_up", "lockout"}
UNLOCK_COMMANDS = {"unlock", "emergency_unlock", "unlock_app", "unlock_command"}

try:
    import win32serviceutil
    import win32service
    import win32event
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class WardenControlClient:
    def __init__(self, host=DEFAULT_SERVER_HOST, port=DEFAULT_SERVER_PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.listener_thread = None
        self.event_thread = None
        self.stop_event = threading.Event()
        self.sid_helper = SID()
        self.lock_screen_process = None
        self.locked_app_name = None
        self.aes_key = None
        self.sid = None
        self.tracker = TimeTracker()
        self.max_retries = 5
        self.retry_count = 0
        self.app_states = {}
        logger_instance = my_logger(self.__class__.__name__, "service.log")
        self.logger = logger_instance.setup_logger()

    def get_sid(self):
        sid = self.sid_helper.GetSID()
        if not sid:
            raise RuntimeError("Unable to retrieve current user SID.")
        return sid

    def connect(self):
        self.close_socket()
        try:
            self.logger.info("Connecting to server %s:%s", self.host, self.port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((self.host, self.port))
            self.sock = sock
            self.logger.info("Connection established.")
            return True
        except Exception as exc:
            self.logger.error("Socket connect failed: %s", exc)
            self.close_socket()
            return False

    def authenticate(self):
        """Perform RSA/AES handshake with the server."""
        try:
            # Step 1: Receive server's RSA public key
            self.logger.info("Waiting to receive server public key...")
            pub_key_bytes = Protocol.recv_packet(self.sock)
            if not pub_key_bytes:
                raise ConnectionError("Failed to receive public key from server.")
            
            server_pub_key = CryptoManager.load_public_key(pub_key_bytes)
            self.logger.info("Received server RSA public key")
            
            # Step 2: Generate and encrypt AES key
            self.aes_key = CryptoManager.generate_aes_key()
            encrypted_aes = CryptoManager.encrypt_rsa(server_pub_key, self.aes_key)
            self.logger.info("Generated and encrypted AES session key")
            
            # Step 3: Send encrypted AES key to server
            Protocol.send_packet(self.sock, encrypted_aes)
            self.logger.info("Sent encrypted AES key to server")
            
            # Step 4: Send auth message with SID
            self.sid = self.get_sid()
            auth_payload = {"sid": self.sid, "purpose": "registration"}
            auth_message = Protocol.serialize_message("auth", auth_payload)
            encrypted_auth = CryptoManager.encrypt_aes(self.aes_key, auth_message)
            Protocol.send_packet(self.sock, encrypted_auth)
            self.logger.info("Sent authenticated registration message for SID %s", self.sid)
        except Exception as exc:
            self.logger.error("Authentication handshake failed: %s", exc)
            self.aes_key = None
            self.sid = None
            raise

    def start(self):
        self.stop_event.clear()
        self._install_signal_handlers()
        backoff = RECONNECT_BASE_DELAY
        self.retry_count = 0

        while not self.stop_event.is_set():
            if not self.sock:
                if self.connect():
                    try:
                        self.authenticate()
                        self._start_listener()
                        backoff = RECONNECT_BASE_DELAY
                        self.retry_count = 0
                    except Exception as exc:
                        self.logger.error("Authentication/listener startup failed: %s", exc)
                        self.retry_count += 1
                        self.close_socket()
                        
                        # Stop retrying after max attempts
                        if self.retry_count >= self.max_retries:
                            self.logger.error("Max authentication retries (%d) reached. Shutting down.", self.max_retries)
                            self.stop_event.set()
                            break
                else:
                    self.logger.info("Reconnect attempt in %.1f seconds", backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, RECONNECT_MAX_DELAY)
                    continue

            if self.listener_thread and not self.listener_thread.is_alive():
                self.logger.warning("Listener thread stopped. Reconnecting.")
                self.close_socket()
                continue

            time.sleep(0.5)

        self.shutdown()

    def _install_signal_handlers(self):
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, self._signal_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self.logger.info("Received termination signal: %s", signum)
        self.stop_event.set()

    def _start_event_scanner(self):
        if self.event_thread and self.event_thread.is_alive():
            return
        self.event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self.event_thread.start()
        self.logger.info("Event scanner thread started.")

    def _event_loop(self):
        self.logger.info("Starting process event monitor.")
        while not self.stop_event.is_set() and self.sock and self.aes_key and self.sid:
            try:
                # --- Dynamic SID switching ---
                try:
                    current_sid = self.get_sid()
                    if current_sid != self.sid:
                        self.logger.info("SID changed from %s to %s — re-authenticating.", self.sid, current_sid)
                        self.close_socket()
                        break
                except Exception:
                    pass

                events = self.tracker.scan_processes(self.sid)
                
                # Maintain local time for reconciliation
                for pid, name in self.tracker.active_processes.items():
                    app_lower = name.lower()
                    
                    # Do not inflate time if this app is currently locked
                    if self.locked_app_name and app_lower == self.locked_app_name.lower():
                        continue
                        
                    if app_lower not in self.app_states:
                        self.app_states[app_lower] = {"total_used_time": 0.0, "allowed_minutes": float('inf')}
                    self.app_states[app_lower]["total_used_time"] += (5.0 / 60.0)

                for event in events:
                    payload = {
                        "sid": self.sid,
                        "event_name": event["event_name"],
                        "metadata": {
                            "app": event["app"],
                            "pid": event["pid"]
                        },
                        "timestamp": event["timestamp"]
                    }
                    self.send_message("event", payload)
                    self.logger.info("Sent event to server: %s", payload)

                    # --- Process Watchdog ---
                    # If the locked app has stopped, dismiss the lock screen
                    if (event["event_name"] == "APP_STOPPED"
                            and self.locked_app_name
                            and event["app"].lower() == self.locked_app_name.lower()):
                        self.logger.info("Locked app '%s' has closed. Dismissing lock screen.", event["app"])
                        self.kill_lock_screen()
                        self.locked_app_name = None

            except Exception as exc:
                if self.stop_event.is_set():
                    break
                self.logger.error("Event scanner error: %s", exc)
                self.close_socket()
                break
            time.sleep(5)

    def _start_listener(self):
        if self.listener_thread and self.listener_thread.is_alive():
            return
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()
        self.logger.info("Listener thread started.")
        self._start_event_scanner()

    def _listen_loop(self):
        self.logger.info("Entering receive loop.")
        while not self.stop_event.is_set() and self.sock and self.aes_key:
            try:
                encrypted_payload = Protocol.recv_packet(self.sock)
                if encrypted_payload is None:
                    raise ConnectionError("Server closed the connection.")

                decrypted_bytes = CryptoManager.decrypt_aes(self.aes_key, encrypted_payload)
                cmd, data = Protocol.deserialize_message(decrypted_bytes)
                self.logger.info("Received server command: %s data=%s", cmd, data)
                self._handle_command(cmd, data)
            except socket.timeout:
                continue
            except Exception as exc:
                if self.stop_event.is_set():
                    break
                self.logger.error("Receive loop error: %s", exc)
                self.close_socket()
                break

        self.logger.info("Receive loop exiting.")

    def _handle_command(self, cmd, data):
        normalized_cmd = str(cmd).strip().lower() if cmd else ""
        normalized_action = ""
        normalized_command = ""
        if isinstance(data, dict):
            normalized_action = str(data.get("action", "")).strip().lower()
            normalized_command = str(data.get("command", "")).strip().lower()

        if normalized_cmd == "auth":
            app_states = data.get("app_states", {}) if isinstance(data, dict) else {}
            for app, state in app_states.items():
                app_lower = app.lower()
                self.app_states[app_lower] = {
                    "total_used_time": state.get("total_used_time", 0.0),
                    "allowed_minutes": state.get("allowed_minutes", 0.0)
                }
            self.logger.info("Synchronized initial state from server: %s", self.app_states)
            return

        if (normalized_cmd in LOCK_COMMANDS
                or normalized_action in LOCK_COMMANDS
                or normalized_command in LOCK_COMMANDS):
            
            # Client-side reconciliation check before honoring the lock
            app_name = ""
            if isinstance(data, dict):
                app_name = data.get("app", "")
            
            if app_name:
                app_lower = app_name.lower()
                state = self.app_states.get(app_lower, {})
                allowed = state.get("allowed_minutes", 0.0)
                used = state.get("total_used_time", 0.0)
                if allowed > used:
                    self.logger.info("Ignoring server lock command for %s because local allowed (%.2f) > used (%.2f)", app_name, allowed, used)
                    return
                    
            self.logger.info("Lock command detected from server: %s", cmd)
            # Track which app triggered the lock for the watchdog
            if app_name:
                self.locked_app_name = app_name
            self.launch_lock_screen()
        elif (normalized_cmd in UNLOCK_COMMANDS
                or normalized_action in UNLOCK_COMMANDS
                or normalized_command in UNLOCK_COMMANDS):
            self.logger.info("Unlock command detected from server: %s", cmd)
            self.locked_app_name = None
            self.kill_lock_screen()
        elif (normalized_cmd == "disconnect_and_clear"
                or normalized_action == "disconnect_and_clear"
                or normalized_command == "disconnect_and_clear"):
            self.logger.warning("Received DISCONNECT_AND_CLEAR. Shutting down service completely.")
            self.shutdown()
        elif normalized_action == "time_update_signal":
            app_name = data.get("app", "").lower()
            new_allowed = data.get("new_allowed_minutes", 0.0)
            if app_name not in self.app_states:
                self.app_states[app_name] = {"total_used_time": 0.0, "allowed_minutes": new_allowed}
            
            self.app_states[app_name]["allowed_minutes"] = new_allowed
            used = self.app_states[app_name]["total_used_time"]
            
            self.logger.info("Reconciliation check for %s: allowed=%.2f, used=%.2f", app_name, new_allowed, used)
            if new_allowed > used:
                self.logger.info("Reconciliation logic: Unlocking app %s", app_name)
                if self.locked_app_name and self.locked_app_name.lower() == app_name:
                    self.locked_app_name = None
                self.kill_lock_screen()
            else:
                self.logger.info("Reconciliation logic: Locking app %s", app_name)
                self.locked_app_name = app_name
                self.launch_lock_screen()
            
            # Acknowledge the update
            self.send_message("ack_time_update", {"app": app_name})
        else:
            self.logger.debug("Unhandled command received: %s", cmd)

    def launch_lock_screen(self):
        if self.lock_screen_process and self.lock_screen_process.poll() is None:
            self.logger.info("Lock screen already running.")
            return

        try:
            script_path = Path(__file__).resolve().parent / "lock_manager" / "lock_screen.py"
            
            cmd_args = []
            if getattr(sys, "frozen", False):
                exe_path = Path(sys.executable).with_name("lock_screen.exe")
                if exe_path.exists():
                    cmd_args = [str(exe_path)]
                else:
                    raise FileNotFoundError("lock_screen.exe not found next to service executable.")
            else:
                cmd_args = [sys.executable, str(script_path)]

            if self.locked_app_name:
                cmd_args.extend(["--app", self.locked_app_name])

            if getattr(sys, "frozen", False):
                self.lock_screen_process = subprocess.Popen(
                    cmd_args,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
                self.lock_screen_process = subprocess.Popen(
                    cmd_args,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )

            self.logger.info("Lock screen launched successfully.")
        except Exception as exc:
            self.logger.error("Failed to launch lock screen: %s", exc)

    def kill_lock_screen(self):
        self.logger.info("Attempting robust kill of lock_screen processes...")
        killed_any = False
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = proc.info.get('name')
                    if name and name.lower() == 'lock_screen.exe':
                        proc.kill()
                        killed_any = True
                    elif name and 'python' in name.lower():
                        cmdline = proc.info.get('cmdline')
                        if cmdline and any('lock_screen.py' in cmd for cmd in cmdline):
                            proc.kill()
                            killed_any = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            self.logger.error("Error during robust process kill: %s", e)
            
        if killed_any:
            self.logger.info("Lock screen processes successfully terminated.")
        else:
            self.logger.info("No active lock screen process found via psutil.")
            
        if self.lock_screen_process:
            try:
                self.lock_screen_process.kill()
            except Exception:
                pass
            self.lock_screen_process = None

    def send_message(self, cmd, data):
        if not self.sock or not self.aes_key:
            raise ConnectionError("Not connected or not authenticated.")
        payload = Protocol.serialize_message(cmd, data)
        encrypted_payload = CryptoManager.encrypt_aes(self.aes_key, payload)
        Protocol.send_packet(self.sock, encrypted_payload)

    def close_socket(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.aes_key = None
        self.sid = None

    def shutdown(self):
        self.logger.info("Shutting down WardenControlClient.")
        self.stop_event.set()
        self.close_socket()
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=5)
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5)
        self.logger.info("Shutdown complete.")


if HAS_WIN32:
    class MyParentalControlService(win32serviceutil.ServiceFramework):
        _svc_name_ = "WardenService"
        _svc_display_name_ = "Warden's Parental Control Service"
        _svc_description_ = "Monitors user SIDs and enforces lockouts."

        def __init__(self, args):
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.client = WardenControlClient()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)
            self.client.stop_event.set()

        def SvcDoRun(self):
            self.client.start()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        client = WardenControlClient()
        try:
            client.start()
        except KeyboardInterrupt:
            client.logger.info("KeyboardInterrupt received, terminating client.")
            client.shutdown()
    elif HAS_WIN32:
        win32serviceutil.HandleCommandLine(MyParentalControlService)
    else:
        print("Win32 service support is unavailable. Use 'python service.py run' to execute in console.")


if __name__ == "__main__":
    main()
