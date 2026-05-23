import streamlit as st
import sys
import logging
import threading
from pathlib import Path

# Provide resolving for our imported warden_client and warden_core modules
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from warden_client.net_client import WardenNetClient
from warden_core.database import DatabaseManager
from warden_core.protocol import Protocol
from warden_core.crypto import CryptoManager

logger = logging.getLogger("admin_panel.socket_manager")

NEW_DEVICE_QUEUE = []

@st.cache_resource
def start_event_listener():
    """Starts a daemon thread to listen for broadcast events from the server."""
    def listener_loop():
        client = WardenNetClient(host="127.0.0.1", port=8000)
        import time
        while True:
            try:
                if not client.sock:
                    if client.connect():
                        # Authenticate as admin event listener
                        client.send_command("auth", {
                            "sid": "ADMIN_EVENTS",
                            "purpose": "admin_events"
                        })
                        logger.info("Admin events listener connected.")
                    else:
                        time.sleep(5)
                        continue

                # Wait for push packets (blocking)
                client.sock.settimeout(None) # Infinite timeout for listening
                encrypted_response = Protocol.recv_packet(client.sock)
                if not encrypted_response:
                    client.close()
                    continue
                    
                decrypted_bytes = CryptoManager.decrypt_aes(client.aes_key, encrypted_response)
                # The server's _push_command sends an encrypted payload containing serialized cmd, data.
                # However, in main.py _push_command uses:
                # msg = Protocol.serialize_message(action, payload)
                # So cmd is the action, data is the payload.
                cmd, data = Protocol.deserialize_message(decrypted_bytes)
                
                if cmd == "new_device":
                    logger.info("Received new_device broadcast for SID: %s", data.get("sid"))
                    NEW_DEVICE_QUEUE.append(data.get("sid"))
                    
            except Exception as e:
                logger.error("Event listener error: %s", e)
                client.close()
                time.sleep(5)

    t = threading.Thread(target=listener_loop, daemon=True)
    t.start()
    return t


@st.cache_resource
def get_db() -> DatabaseManager:
    """Returns a shared DatabaseManager instance with automatic reconnection."""
    return DatabaseManager()


def get_healthy_db() -> DatabaseManager:
    """Returns the cached DB after ensuring the connection is alive."""
    db = get_db()
    try:
        db.ensure_connection()
    except Exception as e:
        logger.warning("DB reconnection failed, clearing cache and retrying: %s", e)
        get_db.clear()
        db = get_db()
    return db


@st.cache_resource
def get_client() -> WardenNetClient:
    """Provides a cached socket client to prevent disconnecting on every streamlit rerun"""
    client = WardenNetClient(host="127.0.0.1", port=8000)
    try:
        if client.connect():
            # Authenticate as admin panel so server registers us
            try:
                client.send_command("auth", {
                    "sid": "ADMIN_PANEL",
                    "purpose": "admin_dashboard"
                })
            except Exception as auth_err:
                logger.warning("Admin auth failed (non-fatal): %s", auth_err)
            return client
    except Exception as e:
        st.error(f"Failed to connect to backend server: {e}")
    return client


def send_remote_command(cmd, data):
    """Wrapper to properly utilize the socket connection over Streamlit"""
    client = get_client()

    if not client.sock:
        # Retry connect
        try:
            success = client.connect()
            if not success:
                return {"error": "Failed to connect to backend."}
            # Re-authenticate after reconnect
            try:
                client.send_command("auth", {
                    "sid": "ADMIN_PANEL",
                    "purpose": "admin_dashboard"
                })
            except Exception:
                pass
        except Exception as e:
            return {"error": f"Connection failed: {e}"}

    try:
        return client.send_command(cmd, data)
    except Exception as e:
        # Force a reconnect manually on next try if socket died
        client.sock = None
        return {"error": str(e)}
