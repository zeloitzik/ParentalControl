from datetime import datetime
from database import DatabaseManager
from flask import Flask, jsonify, request

app = Flask(__name__)


class ServerEngine:

    def __init__(self, db):
        self.db = db


    def process_event(self, event):

        event_name = event["event_name"]
        sid = event["sid"]
        metadata = event["metadata"]
        timestamp = datetime.fromisoformat(event["timestamp"])

        if event_name == "APP_STARTED":
            self.handle_app_start(sid, metadata["app"], timestamp)

        elif event_name == "APP_STOPPED":
            self.handle_app_stop(sid, metadata["app"], timestamp)
    def handle_app_start(self, sid, app, timestamp):

        user_id = self.db.get_user_id_by_sid(sid)

        sql = """
        INSERT INTO app_sessions (user_id, app_name, start_time, status)
        VALUES (%s, %s, %s, 'RUNNING')
        """

        self.db.cursor.execute(sql, (user_id, app, timestamp))
        self.db.db.commit()
    def can_user_run_app(self, sid, app):
        user_id = self.db.get_user_id_by_sid(sid)

        sql = """
        SELECT allowed_minutes
        FROM app_rules
        WHERE user_id=%s AND app_name=%s
        """

        self.db.cursor.execute(sql, (user_id, app))
        result = self.db.cursor.fetchone()

        if not result:
            return True

        allowed_minutes = result[0]

        start_time = self.db.get_start_time_of_active_session(user_id, app)
        used_minutes = datetime.now() - start_time if start_time else 0
        used_minutes = used_minutes.total_seconds() / 60


        return used_minutes < allowed_minutes

    def handle_app_stop(self, sid, app, timestamp):

        user_id = self.db.get_user_id_by_sid(sid)

        sql = """
        SELECT id, start_time
        FROM app_sessions
        WHERE user_id=%s AND app_name=%s AND status='RUNNING'
        ORDER BY start_time DESC
        LIMIT 1
        """

        self.db.cursor.execute(sql, (user_id, app))
        result = self.db.cursor.fetchone()

        if not result:
            return

        session_id, start_time = result

        duration = (timestamp - start_time).total_seconds() / 60

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
        
    @app.get("/parent_dashboard")
    def get_dashboard(self):

        data = []

        # כל הילדים
        self.db.cursor.execute("SELECT id, name FROM users WHERE type='child'")
        users = self.db.cursor.fetchall()

        for user_id, name in users:

            user_data = {
                "name": name,
                "apps": []
            }

            # כל החוקים של המשתמש
            self.db.cursor.execute("""
            SELECT app_name, allowed_minutes
            FROM app_rules
            WHERE user_id=%s
            """, (user_id,))

            rules = self.db.cursor.fetchall()

            for app_name, allowed in rules:

                used = self.db.get_used_time_today(user_id, app_name)
                active = self.db.get_active_session_time(user_id, app_name)

                total = used + active

                user_data["apps"].append({
                    "app": app_name,
                    "used": round(total,2),
                    "allowed": allowed
                })

            data.append(user_data)

        return data

#Test
if __name__ == "__main__":
    db = DatabaseManager()
    engine = ServerEngine(db)
    app.run(debug=True)