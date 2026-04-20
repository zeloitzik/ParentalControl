import subprocess
import time
import sys
import os
import socket
import pytest
import requests
import psutil
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
SERVER_PATH = SRC_PATH / "warden_server" / "main.py"
SERVICE_PATH = SRC_PATH / "warden_client" / "service.py"
LOCK_SCREEN_PATH = SRC_PATH / "warden_client" / "lock_manager" / "lock_screen.py"

# Configure environment
env = os.environ.copy()
env["PYTHONPATH"] = str(SRC_PATH)

def wait_for_port(port, timeout=15):
    """Wait for a port to be open on localhost."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout):
            time.sleep(1)
    return False

class TestWardenIntegration:
    processes = []

    @classmethod
    def setup_class(cls):
        """Start the Server and Service in background."""
        print("\n[SETUP] Starting Warden Server...")
        cls.server_proc = subprocess.Popen(
            [sys.executable, str(SERVER_PATH)],
            env=env,
            stdout=sys.stdout, # Stream to console
            stderr=sys.stderr,
            text=True
        )
        cls.processes.append(cls.server_proc)

        # Wait for FastAPI to be ready
        if not wait_for_port(8000):
            print("\n[ERROR] Server failed to start on port 8000.")
            cls.teardown_class()
            pytest.fail("FAILED: Server failed to start on port 8000")

        print("[SETUP] Starting Warden Service (Test Mode)...")
        # Run service in 'run' mode which we added earlier for testing
        cls.service_proc = subprocess.Popen(
            [sys.executable, str(SERVICE_PATH), "run"],
            env=env,
            stdout=sys.stdout, # Stream to console
            stderr=sys.stderr,
            text=True
        )
        cls.processes.append(cls.service_proc)
        
        # Give service time to initialize
        time.sleep(3)

    @classmethod
    def teardown_class(cls):
        """Cleanup all spawned processes."""
        print("\n[TEARDOWN] Cleaning up processes...")
        for proc in cls.processes:
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except psutil.NoSuchProcess:
                pass
        
        # Specifically look for any orphaned lock_screen.py or notepad.exe
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if any("lock_screen.py" in s for s in cmdline) or proc.info['name'] == "Notepad.exe":
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def test_server_heartbeat(self):
        """Verify the raw socket server and AES encryption heartbeat."""
        if str(SRC_PATH) not in sys.path:
            sys.path.append(str(SRC_PATH))
            
        try:
            from warden_client.net_client import WardenNetClient
            client = WardenNetClient(host="127.0.0.1", port=8000)
            assert client.connect(), "FAILED: Raw socket handshake completely failed"
            
            response = client.send_command("dashboard", {})
            assert "status" in response and response["status"] == "success", "FAILED: Dashboart via socket encryption failed"
        except Exception as e:
            pytest.fail(f"FAILED: Connection to socket server failed: {e}")

    def test_threshold_and_lock_trigger(self):
        """
        Simulate a time-overage and verify lock screen trigger.
        1. We'll manually inject an event that pushes 'notepad.exe' over the limit.
        2. We'll wait and see if the service spawns the lock screen.
        """
        # Ensure SRC_PATH is in sys.path for this test process too
        if str(SRC_PATH) not in sys.path:
            sys.path.append(str(SRC_PATH))
        
        print("\n[TEST] Simulating time-overage for notepad.exe...")
        
        # 1. Start notepad.exe locally to give the service something to track
        notepad = subprocess.Popen(["notepad.exe"])
        self.processes.append(notepad)
        
        # 2. Wait for service to detect it and send APP_STARTED to server
        time.sleep(7) 

        # 3. Simulate threshold logic: The service checks with server.
        # We already have a 1-minute limit in the DB from seed_test_data.py.
        # To trigger it immediately, we could wait 1 minute, but for the test, 
        # we'll use a trick: We'll modify the rule in the database to be 0 minutes.
        
        print("[TEST] Modifying rule to 0 minutes for immediate trigger...")
        from warden_core.database import DatabaseManager
        db = DatabaseManager()
        try:
            # Get current user SID
            from warden_core.sid_helper import SID
            user_sid = SID().GetSID()
            db.cursor.execute("SELECT id FROM users WHERE sid=%s", (user_sid,))
            user_id = db.cursor.fetchone()[0]
            
            # Set allowed minutes to 0 for notepad.exe and DEVICE_TOTAL
            db.cursor.execute(
                "UPDATE app_rules SET allowed_minutes=1 WHERE user_id=%s AND app_name IN ('Notepad.exe', 'notepad.exe', 'DEVICE_TOTAL')",
                (user_id,)
            )
            db.db.commit()
        finally:
            db.close()

        # 4. Wait for service's next poll cycle (5-10 seconds)
        print("[TEST] Waiting for service to enforce policy...")
        
        lock_screen_found = False
        for _ in range(30): # Increased polling to 30 seconds
            time.sleep(1)
            for proc in psutil.process_iter(['cmdline']):
                cmdline = proc.info.get('cmdline') or []
                if any("lock_screen.py" in s for s in cmdline):
                    lock_screen_found = True
                    print("[SUCCESS] Lock screen process detected!")
                    break
            if lock_screen_found:
                break
        
        assert lock_screen_found, "FAILED: Lock screen was not triggered after time limit reached."
        
        # Check if notepad was killed
        assert not psutil.pid_exists(notepad.pid), "FAILED: Notepad was not killed after limit reached"

if __name__ == "__main__":
    # Ensure dependencies are installed
    try:
        import pytest
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest", "requests", "psutil"])
    
    # Run the test
    sys.exit(pytest.main([__file__, "-v", "-s"]))
