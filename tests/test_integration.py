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

    @patch('mysql.connector.connect')
    def test_email_exists(self, mock_connect):
        """Verify email_exists returns True for existing emails."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_db.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_db

        db_manager = DatabaseManager()
        result = db_manager.email_exists("test@test.com")
        assert result is True

    @patch('mysql.connector.connect')
    def test_email_not_exists(self, mock_connect):
        """Verify email_exists returns False for unknown emails."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_db.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_db

        db_manager = DatabaseManager()
        result = db_manager.email_exists("nobody@test.com")
        assert result is False

    @patch('mysql.connector.connect')
    def test_get_known_apps(self, mock_connect):
        """Verify get_known_apps returns a sorted list of app names."""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("chrome.exe",), ("notepad.exe",)]
        mock_db.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_db

        db_manager = DatabaseManager()
        apps = db_manager.get_known_apps(1)
        assert apps == ["chrome.exe", "notepad.exe"]

    @patch('mysql.connector.connect')
    def test_ensure_connection(self, mock_connect):
        """Verify ensure_connection pings the database."""
        mock_db = MagicMock()
        mock_connect.return_value = mock_db

        db_manager = DatabaseManager()
        db_manager.ensure_connection()
        mock_db.ping.assert_called_once_with(reconnect=True, attempts=3, delay=1)


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

    def test_can_user_run_app_zero_threshold_locked(self):
        """With allowed_minutes=0, app should ALWAYS be denied (locked)."""
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_app_rule.return_value = {"allowed_minutes": 0}
        mock_db.get_used_time_today.return_value = 0
        mock_db.get_active_session_time.return_value = 0
        
        # allowed=0, used=0, active=0 -> total 0 which is NOT < 0 -> False
        allowed = engine.can_user_run_app("S-1-5-X", "Blocked.exe")
        assert allowed is False

    def test_can_user_run_app_no_rule_allows(self):
        """An app with no rule should be allowed (fail-open policy)."""
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_app_rule.return_value = None
        
        allowed = engine.can_user_run_app("S-1-5-X", "SafeApp.exe")
        assert allowed is True

    def test_can_user_run_app_under_limit(self):
        """An app under its limit should be allowed."""
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_app_rule.return_value = {"allowed_minutes": 60}
        mock_db.get_used_time_today.return_value = 10
        mock_db.get_active_session_time.return_value = 5
        
        # 10 + 5 = 15 < 60 -> True
        allowed = engine.can_user_run_app("S-1-5-X", "Game.exe")
        assert allowed is True


# --- 3. Time Tracking & Timezone Handling ---
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


# --- 4. Integration (Engine + Server/DB) ---
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
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        engine.process_event(event)
        assert mock_db.start_app_session.called

    def test_engine_zero_threshold_immediate_lock(self):
        """Verify that allowed_minutes=0 means the app is instantly blocked."""
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_app_rule.return_value = {"allowed_minutes": 0}
        mock_db.get_used_time_today.return_value = 0
        mock_db.get_active_session_time.return_value = 0
        
        # With allowed_minutes=0, this should return False immediately
        result = engine.can_user_run_app("S-1-5-X", "notepad.exe")
        assert result is False

    def test_engine_app_start_still_creates_session_when_locked(self):
        """Even when locked (0 minutes), handle_app_start should still create a session
        so the lock monitor can detect it and push a lock command."""
        mock_db = MagicMock()
        engine = ServerEngine(mock_db)
        
        mock_db.get_user_id_by_sid.return_value = 1
        mock_db.get_running_session.return_value = None  # no existing session
        
        ts = datetime.datetime.now()
        engine.handle_app_start("S-1-5-X", "notepad.exe", ts)
        
        # Session should be started regardless of rule
        mock_db.start_app_session.assert_called_once_with(1, "notepad.exe", ts)
