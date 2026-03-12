from dotenv import load_dotenv
import mysql.connector
import os

load_dotenv()


class DatabaseManager:

    def __init__(self):
        self.host = "127.0.0.1"
        # self.user = os.environ.get("DB_USER")
        # self.password = os.environ.get("DB_PASSWORD")
        self.user = "zeloitzik"
        self.password = "itzik123"
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

        self.cursor = self.db.cursor()

    # TABLE CREATION

    def _initialize_tables(self):

        # Families table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS families (
            id INT AUTO_INCREMENT PRIMARY KEY,
            parent_email VARCHAR(255) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

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
        self.cursor.execute(sql, (parent_email,))
        self.db.commit()

        return self.cursor.lastrowid

    def add_user(self, family_id, sid, name, user_type):

        sql = """
        INSERT INTO users (family_id, sid, name, type)
        VALUES (%s, %s, %s, %s)
        """

        self.cursor.execute(sql, (family_id, sid, name, user_type))
        self.db.commit()

        return self.cursor.lastrowid

    def add_device(self, family_id, device_name):

        sql = """
        INSERT INTO devices (family_id, device_name)
        VALUES (%s, %s)
        """

        self.cursor.execute(sql, (family_id, device_name))
        self.db.commit()

    def add_app_rule(self, user_id, app_name, allowed_minutes):

        sql = """
        INSERT INTO app_rules (user_id, app_name, allowed_minutes)
        VALUES (%s, %s, %s)
        """

        self.cursor.execute(sql, (user_id, app_name, allowed_minutes))
        self.db.commit()

    def log_usage(self, user_id, app_name, duration):

        sql = """
        INSERT INTO usage_logs (user_id, app_name, start_time, duration)
        VALUES (%s, %s, NOW(), %s)
        """

        self.cursor.execute(sql, (user_id, app_name, duration))
        self.db.commit()

    # DEBUG UTILITIES

    def print_table(self, table):

        self.cursor.execute(f"SELECT * FROM {table}")
        rows = self.cursor.fetchall()

        for row in rows:
            print(row)

    def close(self):
        self.cursor.close()
        self.db.close()


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