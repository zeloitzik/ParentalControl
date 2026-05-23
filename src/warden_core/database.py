from dotenv import load_dotenv
import mysql.connector
import os
import bcrypt

load_dotenv()


class DatabaseManager:

    def __init__(self):
        self.host = "127.0.0.1"
        # self.user = os.environ.get("DB_USER")
        # self.password = os.environ.get("DB_PASSWORD")
        self.user = "root"
        self.password = "Itzik@2007"
        self.db_name = "warden_db"

        self._initialize_database()
        self._connect()
        self._initialize_tables()

    # DATABASE INITIALIZATION
    
    def _initialize_database(self):
        conn = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password
        )

        cursor = conn.cursor()

        cursor.execute("SHOW DATABASES LIKE %s", (self.db_name,))
        result = cursor.fetchone()

        if not result:
            cursor.execute(f"CREATE DATABASE {self.db_name}")

        cursor.close()
        conn.close()

    def _connect(self):
        self.db = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.db_name
        )

        self.cursor = self.db.cursor(buffered=True)

    def _new_cursor(self):
        return self.db.cursor(buffered=True)

    # TABLE CREATION
    def get_cursor(self): 
        return self.cursor
    def _initialize_tables(self):

        # Families table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS families (
            id INT AUTO_INCREMENT PRIMARY KEY,
            parent_email VARCHAR(255) UNIQUE,
            password_hash VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        try:
            self.cursor.execute("ALTER TABLE families ADD COLUMN password_hash VARCHAR(255)")
        except mysql.connector.Error:
            pass

        # Users table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            family_id INT,
            sid VARCHAR(255) UNIQUE,
            name VARCHAR(255),
            type ENUM('parent','child'),
            FOREIGN KEY (family_id) REFERENCES families(id)
        )
        """)

        # Devices table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            family_id INT,
            device_name VARCHAR(255),
            last_seen TIMESTAMP,
            FOREIGN KEY (family_id) REFERENCES families(id)
        )
        """)

        # App rules table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_rules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            app_name VARCHAR(255),
            allowed_minutes INT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        try:
            self.cursor.execute("ALTER TABLE app_rules ADD UNIQUE INDEX uidx_user_app (user_id, app_name)")
        except mysql.connector.Error:
            pass

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            app_name VARCHAR(255) NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NULL,
            status ENUM('RUNNING','CLOSED') NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            INDEX idx_user_app_status (user_id, app_name, status)
        )
        """)

        # Usage logs table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            app_name VARCHAR(255),
            start_time TIMESTAMP,
            duration INT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        self.db.commit()

    # INSERT FUNCTIONS

    def add_family(self, parent_email):

        sql = "INSERT INTO families (parent_email) VALUES (%s)"
        try:
            self.cursor.execute(sql, (parent_email,))
            self.db.commit()
            return self.cursor.lastrowid
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def add_user(self, family_id, sid, name, user_type):
        if not all([family_id, sid, name, user_type]):
            raise ValueError("All user fields are required")
        sql = """
        INSERT INTO users (family_id, sid, name, type)
        VALUES (%s, %s, %s, %s)
        """
        try:
            self.cursor.execute(sql, (family_id, sid, name, user_type))
            self.db.commit()
            return self.cursor.lastrowid
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def add_device(self, family_id, device_name):

        sql = """
        INSERT INTO devices (family_id, device_name)
        VALUES (%s, %s)
        """
        try:
            self.cursor.execute(sql, (family_id, device_name))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def add_app_rule(self, user_id, app_name, allowed_minutes):

        sql = """
        INSERT INTO app_rules (user_id, app_name, allowed_minutes)
        VALUES (%s, %s, %s)
        """
        try:
            self.cursor.execute(sql, (user_id, app_name, allowed_minutes))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def log_usage(self, user_id, app_name, duration):

        sql = """
        INSERT INTO usage_logs (user_id, app_name, start_time, duration)
        VALUES (%s, %s, NOW(), %s)
        """
        try:
            self.cursor.execute(sql, (user_id, app_name, duration))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def start_app_session(self, user_id, app_name, start_time):
        sql = """
        INSERT INTO app_sessions (user_id, app_name, start_time, status)
        VALUES (%s, %s, %s, 'RUNNING')
        """
        try:
            self.cursor.execute(sql, (user_id, app_name, start_time))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def get_running_session(self, user_id, app_name):
        sql = """
        SELECT id, start_time FROM app_sessions 
        WHERE user_id = %s AND app_name = %s AND status = 'RUNNING'
        LIMIT 1
        """
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_id, app_name))
            result = cursor.fetchone()
            if result:
                return {"id": result[0], "start_time": result[1]}
            return None
        finally:
            cursor.close()

    def get_app_rule(self, user_id, app_name):
        sql = "SELECT allowed_minutes FROM app_rules WHERE user_id = %s AND app_name = %s"
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_id, app_name))
            result = cursor.fetchone()
            return {"allowed_minutes": result[0]} if result else None
        finally:
            cursor.close()

    # AUTHENTICATION
    def set_admin_password(self, email, password):
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        sql = "UPDATE families SET password_hash = %s WHERE parent_email = %s"
        self.cursor.execute(sql, (hashed.decode('utf-8'), email))
        self.db.commit()

    def verify_admin(self, email, password):
        sql = "SELECT password_hash FROM families WHERE parent_email = %s"
        self.cursor.execute(sql, (email,))
        result = self.cursor.fetchone()
        
        # Auto-setup for empty password cases (initial login)
        if result and not result[0]:
            self.set_admin_password(email, password)
            return True
            
        if result and result[0]:
            stored_hash = result[0].encode('utf-8') if isinstance(result[0], str) else result[0]
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
        return False

    # ADMIN API METHODS
    def get_users_by_type(self, user_type):
        sql = "SELECT id, name, sid, family_id FROM users WHERE type = %s"
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_type,))
            return [{"id": row[0], "name": row[1], "sid": row[2], "family_id": row[3]} for row in cursor.fetchall()]
        finally:
            cursor.close()

    def update_app_rule(self, user_id, app_name, allowed_minutes):
        sql = """
        INSERT INTO app_rules (user_id, app_name, allowed_minutes)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE allowed_minutes = VALUES(allowed_minutes)
        """
        try:
            self.cursor.execute(sql, (user_id, app_name, allowed_minutes))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def delete_app_rule(self, user_id, app_name):
        sql = "DELETE FROM app_rules WHERE user_id = %s AND app_name = %s"
        try:
            self.cursor.execute(sql, (user_id, app_name))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err
            
    def get_dataframe_data(self, query, params=None):
        import pandas as pd
        if not params:
            return pd.read_sql(query, self.db)
        return pd.read_sql(query, self.db, params=params)

    # FUNCTIONS
    def get_user_id_by_sid(self, sid):
        sql = "SELECT id FROM users WHERE sid = %s"
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (sid,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def get_start_time_of_active_session(self, user_id, app_name):
        sql = """
        SELECT start_time
        FROM app_sessions
        WHERE user_id = %s
        AND app_name = %s
        AND status = 'RUNNING'
        """
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_id, app_name))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def get_active_session_time(self, user_id, app_name):
        sql = """
        SELECT IFNULL(TIMESTAMPDIFF(MINUTE, start_time, NOW()),0)
        FROM app_sessions
        WHERE user_id = %s
        AND app_name = %s
        AND status = 'RUNNING'
        """
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_id, app_name))
            result = cursor.fetchone()
            return result[0] if result else 0
        finally:
            cursor.close()
    # DEBUG UTILITIES

    def print_table(self, table):

        self.cursor.execute(f"SELECT * FROM {table}")
        rows = self.cursor.fetchall()

        for row in rows:
            print(row)

    def close(self):
        self.cursor.close()
        self.db.close()

    def clear_table(self, table_name):

        self.cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        self.cursor.execute(f"TRUNCATE TABLE {table_name}")
        self.cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        self.db.commit()
    
    def clear_families(self):
        self.clear_table("families")

    def clear_users(self):
        self.clear_table("users")

    def clear_devices(self):
        self.clear_table("devices")

    def clear_app_rules(self):
        self.clear_table("app_rules")

    def clear_usage_logs(self):
        self.clear_table("usage_logs")
    
    def clear_all_tables(self):

        self.cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        tables = [
            "usage_logs",
            "app_sessions",
            "app_rules",
            "devices",
            "users",
            "families"
        ]

        for table in tables:
            self.cursor.execute(f"TRUNCATE TABLE {table}")

        self.cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        self.db.commit()
    
    def reset_database(self):

        self.cursor.close()
        self.db.close()

        conn = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password
        )

        cursor = conn.cursor()

        cursor.execute(f"DROP DATABASE IF EXISTS {self.db_name}")
        cursor.execute(f"CREATE DATABASE {self.db_name}")

        cursor.close()
        conn.close()

        self._connect()
        self._initialize_tables()

    # Time functions
    def can_user_run_app(self, sid, app_name):
        cursor = self._new_cursor()
        try:
            sql = "SELECT id FROM users WHERE sid = %s"
            cursor.execute(sql, (sid,))
            user = cursor.fetchone()

            if not user:
                return True  # no user registered -> allow

            user_id = user[0]

            sql = """
            SELECT allowed_minutes
            FROM app_rules
            WHERE user_id = %s AND app_name = %s
            """
            cursor.execute(sql, (user_id, app_name))
            rule = cursor.fetchone()

            if not rule:
                return True  # no rule -> allow

            allowed_minutes = rule[0]

            sql = """
            SELECT IFNULL(SUM(duration),0)
            FROM usage_logs
            WHERE user_id = %s
            AND app_name = %s
            AND DATE(start_time) = CURDATE()
            """
            cursor.execute(sql, (user_id, app_name))
            used_minutes = cursor.fetchone()[0]

            if used_minutes >= allowed_minutes:
                return False

            return True
        finally:
            cursor.close()

    def remaining_time(self, sid, app_name):
        cursor = self._new_cursor()
        try:
            sql = "SELECT id FROM users WHERE sid = %s"
            cursor.execute(sql, (sid,))
            user = cursor.fetchone()

            if not user:
                return None

            user_id = user[0]

            sql = """
            SELECT allowed_minutes
            FROM app_rules
            WHERE user_id = %s AND app_name = %s
            """
            cursor.execute(sql, (user_id, app_name))
            rule = cursor.fetchone()

            if not rule:
                return None

            allowed_minutes = rule[0]

            sql = """
            SELECT IFNULL(SUM(duration),0)
            FROM usage_logs
            WHERE user_id = %s
            AND app_name = %s
            AND DATE(start_time) = CURDATE()
            """
            cursor.execute(sql, (user_id, app_name))
            used = cursor.fetchone()[0]

            return max(allowed_minutes - used, 0)
        finally:
            cursor.close()
    
    
    def get_used_time_today(self, user_id, app_name):
        sql = """
        SELECT IFNULL(SUM(duration), 0)
        FROM usage_logs
        WHERE user_id = %s
          AND app_name = %s
          AND DATE(start_time) = CURDATE()
        """
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_id, app_name))
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def get_known_apps(self, user_id):
        """Return distinct app names this user has ever run (from sessions + usage logs)."""
        sql = """
        SELECT DISTINCT app_name FROM (
            SELECT app_name FROM app_sessions WHERE user_id = %s
            UNION
            SELECT app_name FROM usage_logs WHERE user_id = %s
        ) AS combined
        ORDER BY app_name
        """
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (user_id, user_id))
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def email_exists(self, email):
        """Check if a parent email already exists in the families table."""
        sql = "SELECT COUNT(*) FROM families WHERE parent_email = %s"
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (email,))
            return cursor.fetchone()[0] > 0
        finally:
            cursor.close()

    def register_parent(self, email, password):
        """Register a new parent with bcrypt-hashed password. Returns the new family ID."""
        if self.email_exists(email):
            raise ValueError("An account with this email already exists.")
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        sql = "INSERT INTO families (parent_email, password_hash) VALUES (%s, %s)"
        try:
            self.cursor.execute(sql, (email, hashed.decode('utf-8')))
            self.db.commit()
            return self.cursor.lastrowid
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err

    def update_child_name(self, user_id, new_name):
        """Update the human-readable name for a child user."""
        sql = "UPDATE users SET name = %s WHERE id = %s"
        cursor = self._new_cursor()
        try:
            cursor.execute(sql, (new_name, user_id))
            self.db.commit()
        except mysql.connector.Error as err:
            self.db.rollback()
            raise err
        finally:
            cursor.close()

    def auto_register_sid(self, sid, family_id=None):
        """Auto-register a new SID as a child user with a placeholder name.
        If no family exists, creates a default family first."""
        # Check if SID already exists
        if self.get_user_id_by_sid(sid):
            return  # Already registered

        # Find or create a default family
        if not family_id:
            cursor = self._new_cursor()
            try:
                cursor.execute("SELECT id FROM families LIMIT 1")
                row = cursor.fetchone()
                if row:
                    family_id = row[0]
                else:
                    cursor.execute("INSERT INTO families (parent_email) VALUES (%s)", ("admin@warden.local",))
                    self.db.commit()
                    family_id = cursor.lastrowid
            finally:
                cursor.close()

        # Create user with placeholder name
        short_sid = sid[-8:] if len(sid) > 8 else sid
        placeholder_name = f"Child ({short_sid})"
        self.add_user(family_id, sid, placeholder_name, "child")

    def ensure_connection(self):
        """Ping the MySQL connection and reconnect if it has gone stale."""
        try:
            self.db.ping(reconnect=True, attempts=3, delay=1)
        except Exception:
            self._connect()

# TEST

if __name__ == "__main__":

    db = DatabaseManager()

    family_id = db.add_family("parent@gmail.com")

    user_id = db.add_user(
        family_id,
        "S-1-5-21-123456",
        "ChildA",
        "child"
    )

    db.add_device(family_id, "Gaming-PC")

    db.add_app_rule(user_id, "Fortnite.exe", 60)

    db.log_usage(user_id, "Fortnite.exe", 15)

    db.print_table("users")