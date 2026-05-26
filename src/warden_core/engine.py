from datetime import datetime, timezone
from warden_core.database import DatabaseManager
from warden_core.setup_logger import my_logger

class ServerEngine:

    def __init__(self, db):
        self.db = db
        self.logger = my_logger(self.__class__.__name__, "engine.log").setup_logger()


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
            return  
        self.db.start_app_session(user_id, app, timestamp)
    def can_user_run_app(self, sid, app):
        remaining = self.db.remaining_time(sid, app)
        if remaining is None:
            return True
        return remaining > 0

    def handle_app_stop(self, sid, app, timestamp):

        user_id = self.db.get_user_id_by_sid(sid)
        if not user_id:
            return

        session = self.db.get_running_session(user_id, app)
        if not session:
            return

        session_id = session["id"]
        start_time = session["start_time"]

        if start_time.tzinfo is None and timestamp.tzinfo is not None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        duration = (timestamp - start_time).total_seconds() / 60
        if duration < 0:
            duration = 0

        cursor = self.db._new_cursor()
        try:
            update_sql = """
            UPDATE app_sessions
            SET end_time=%s, status='CLOSED'
            WHERE id=%s
            """
            cursor.execute(update_sql, (timestamp, session_id))

            log_sql = """
            INSERT INTO usage_logs (user_id, app_name, duration, start_time)
            VALUES (%s,%s,%s,%s)
            """
            cursor.execute(log_sql, (user_id, app, duration, start_time))
            self.db.db.commit()
        except Exception:
            self.db.db.rollback()
            raise
        finally:
            cursor.close()
        
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