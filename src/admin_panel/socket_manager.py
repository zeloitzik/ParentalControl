import streamlit as st
import sys
import pandas as pd
from pathlib import Path

# Provide resolving for our imported warden_client and warden_core modules
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from warden_client.net_client import WardenNetClient
from warden_core.database import DatabaseManager

@st.cache_resource
def get_client() -> WardenNetClient:
    """Provides a cached socket client to prevent disconnecting on every streamlit rerun"""
    client = WardenNetClient(host="127.0.0.1", port=8000)
    try:
        if client.connect():
            return client
    except Exception as e:
        st.error(f"Failed to connect to backend server: {e}")
    return client

def get_db() -> DatabaseManager:
    """Returns DatabaseManager instance stored in session state"""
    if "db" not in st.session_state:
        st.session_state.db = DatabaseManager()
    return st.session_state.db

def send_remote_command(cmd, data):
    """Wrapper to properly utilize the socket connection over Streamlit"""
    client = get_client()
    
    if not client.sock:
        # Retry connect
        success = client.connect()
        if not success:
            return {"error": "Failed to connect to backend."}
            
    try:
        return client.send_command(cmd, data)
    except Exception as e:
        # Force a reconnect manually on next try if socket died
        client.sock = None
        return {"error": str(e)}
