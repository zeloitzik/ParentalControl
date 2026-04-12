import pytest
import datetime
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Ensure the project root and src directory are in the path for imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(root_path, 'src'))

# Mocking modules that might not be available or are environment-dependent
sys.modules['win32security'] = MagicMock()
sys.modules['win32con'] = MagicMock()
sys.modules['win32api'] = MagicMock()
sys.modules['win32event'] = MagicMock()
sys.modules['win32service'] = MagicMock()
sys.modules['win32serviceutil'] = MagicMock()
sys.modules['psutil'] = MagicMock()

# Specifically handle warden_core.sid_helper.SID mock
sys.modules['warden_core.sid_helper'] = MagicMock()
import warden_core.sid_helper as sid_helper
sid_helper.SID.return_value.GetSID.return_value = "S-1-5-Default-Mock"

# Mocking win32serviceutil.ServiceFramework to avoid StopIteration during super().__init__
win32serviceutil_mock = MagicMock()
sys.modules['win32serviceutil'] = win32serviceutil_mock
# ServiceFramework is a class, so it needs to return an object (or itself)
win32serviceutil_mock.ServiceFramework = MagicMock

from warden_core.database import DatabaseManager
from warden_core.engine import ServerEngine
from warden_client.service import MyParentalControlService
from warden_client.time_tracker import TimeTracker

# --- 1. Database Tests ---
class TestDatabase:
    """Validates CRUD operations and connection resilience in DatabaseManager."""

    @patch('mysql.connector.connect')
    def test_database_initialization(self, mock_connect):
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        db_manager = DatabaseManager()
        assert mock_connect.called
        assert db_manager.db_name == "warden_db"

    @patch('mysql.connector.connect')
    def test_add_user_success(self, mock_connect):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_db
        
        db_manager = DatabaseManager()
        db_manager.cursor = mock_cursor
        db_manager.add_user(1, "S-1-5-21-test", "ChildA", "child")
        
        assert mock_cursor.execute.called
        assert mock_db.commit.called

    @patch('mysql.connector.connect')
    def test_add_user_empty_input(self, mock_connect):
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        db_manager = DatabaseManager()
        
        with pytest.raises(ValueError):
            db_manager.add_user(None, None, None, None)

# --- 2. Engine Logic Tests ---
class TestEngine:
    """Validates core algorithms, state transitions, and time calculations."""

    def test_handle_app_start_deduplication(self):
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        # Scenario: App is already running
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_running_session.return_value = {"id": 101, "start_time": datetime.datetime.now()}
        
        engine.handle_app_start("S-1-5-X", "Game.exe", datetime.datetime.now())
        assert not mock_db.start_app_session.called

    def test_can_user_run_app_limit_reached(self):
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_app_rule.return_value = {"allowed_minutes": 60}
        mock_db.get_used_time_today.return_value = 55
        mock_db.get_active_session_time.return_value = 10
        
        # 55 + 10 = 65 > 60 -> should be False
        allowed = engine.can_user_run_app("S-1-5-X", "Game.exe")
        assert allowed is False

# --- 3. Service-Server Communication ---
class TestCommunication:
    """Verifies data exchange and network failure resilience."""

    @patch('requests.post')
    def test_send_event_success(self, mock_post):
        mock_post.return_value.status_code = 200
        service = MyParentalControlService([])
        service.user_SID = "S-1-5-Test"
        
        service.send_event("APP_STARTED", {"app": "Chrome.exe"})
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert kwargs['json']['event_name'] == "APP_STARTED"

    @patch('requests.post')
    def test_check_app_server_disconnected(self, mock_post):
        # Scenario: Server is down
        mock_post.side_effect = Exception("Connection Refused")
        service = MyParentalControlService([])
        
        # Fail-open policy check
        allowed = service.check_with_server("Game.exe")
        assert allowed is True # System should fail-safe (open) by default

# --- 4. Service Logic Tests ---
class TestServiceLogic:
    """Validates standalone business rules in 'my_service.py'."""

    @patch('psutil.Process')
    def test_kill_process_logic(self, mock_proc_class):
        mock_proc = MagicMock()
        mock_proc_class.return_value = mock_proc
        service = MyParentalControlService([])
        
        service.kill_process(1234)
        assert mock_proc.terminate.called

# --- 5. Time Tracking & Timezone Handling ---
class TestTimeTracking:
    """Validates accuracy of duration calculations and timezone offset awareness."""

    def test_handle_app_stop_timezone_awareness(self):
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        start_time = datetime.datetime(2026, 3, 29, 10, 0, 0) # Naive
        stop_time = datetime.datetime(2026, 3, 29, 10, 30, 0, tzinfo=datetime.timezone.utc) # Aware
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_running_session.return_value = {"id": 1, "start_time": start_time}
        
        engine.handle_app_stop("S-1-5-X", "App.exe", stop_time)
        
        # Verify duration calculation (30 mins)
        args, kwargs = mock_db.cursor.execute.call_args_list[1]
        duration = args[1][2]
        assert duration == 30.0

# --- 6. Integration (Engine + Server/DB) ---
class TestIntegration:
    """Ensures end-to-end compatibility between components."""

    def test_engine_db_commit_on_event(self):
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_running_session.return_value = None
        mock_db.get_app_rule.return_value = {"allowed_minutes": 100}
        mock_db.get_used_time_today.return_value = 0
        mock_db.get_active_session_time.return_value = 0

        event = {
            "event_name": "APP_STARTED",
            "sid": "S-1-5-X",
            "metadata": {"app": "Note.exe"},
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        engine.process_event(event)
        assert mock_db.start_app_session.called
