import streamlit as st
import sys
import logging
from pathlib import Path

# Provide resolving for our imported warden_client and warden_core modules
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from warden_client.net_client import WardenNetClient
from warden_core.database import DatabaseManager

logger = logging.getLogger("admin_panel.socket_manager")


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
