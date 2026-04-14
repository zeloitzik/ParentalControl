from datetime import datetime, timezone
from warden_core.database import DatabaseManager

class ServerEngine:

    def __init__(self, db):
        self.db = db


    def process_event(self, event):

        event_name = event["event_name"]
        sid = event["sid"]
        metadata = event["metadata"]
        timestamp_utc = datetime.fromisoformat(event["timestamp"])
        timestamp = timestamp_utc.astimezone().replace(tzinfo=None)

        if event_name == "APP_STARTED":
            self.handle_app_start(sid, metadata["app"], timestamp)

        elif event_name == "APP_STOPPED":
            self.handle_app_stop(sid, metadata["app"], timestamp)
    def handle_app_start(self, sid, app, timestamp):
        user_id = self.db.get_user_id_by_sid(sid)
        if not user_id:
            return

        session = self.db.get_running_session(user_id, app)
        if session:
            return  # deduplicate repeated APP_STARTED events

        # Check if the app is allowed BEFORE starting session
        # We still want to log the start attempt in app_sessions even if blocked?
        # Actually, if it's blocked, it will be killed.
        # But for tracking why it was killed, having it in app_sessions helps.
        # However, the current logic kills it if can_user_run_app is False.
        
        # FIX: Always start session to record the attempt.
        # This ensures the user sees 'notepad.exe' in the sessions table even if it's already over the limit.
        self.db.start_app_session(user_id, app, timestamp)
    def can_user_run_app(self, sid, app):
        user_id = self.db.get_user_id_by_sid(sid)
        if not user_id:
            return False

        rule = self.db.get_app_rule(user_id, app)
        if not rule:
            return True

        allowed_minutes = rule["allowed_minutes"]
        used_today = self.db.get_used_time_today(user_id, app)
        active_time = self.db.get_active_session_time(user_id, app)

        total_used = used_today + active_time
        return total_used < allowed_minutes

    def handle_app_stop(self, sid, app, timestamp):

        user_id = self.db.get_user_id_by_sid(sid)
        if not user_id:
            return

        session = self.db.get_running_session(user_id, app)
        if not session:
            return

        session_id = session["id"]
        start_time = session["start_time"]

        # Ensure start_time is offset-aware if timestamp is
        if start_time.tzinfo is None and timestamp.tzinfo is not None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        duration = (timestamp - start_time).total_seconds() / 60
        if duration < 0:
            duration = 0

        update_sql = """
        UPDATE app_sessions
        SET end_time=%s, status='CLOSED'
        WHERE id=%s
        """
        self.db.cursor.execute(update_sql, (timestamp, session_id))

        log_sql = """
        INSERT INTO usage_logs (user_id, app_name, duration, start_time)
        VALUES (%s,%s,%s,%s)
        """
        self.db.cursor.execute(log_sql, (user_id, app, duration, start_time))
        self.db.db.commit()
        
    def cleanup_stale_sessions(self, timeout_minutes=10):
        sql = """
        UPDATE app_sessions
        SET status='CLOSED', end_time=NOW()
        WHERE status='RUNNING'
          AND TIMESTAMPDIFF(MINUTE, start_time, NOW()) > %s
        """
        self.db.cursor.execute(sql, (timeout_minutes,))
        self.db.db.commit()

#Test
if __name__ == "__main__":
    db = DatabaseManager()
    engine = ServerEngine(db)