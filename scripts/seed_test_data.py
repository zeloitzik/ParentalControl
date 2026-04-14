import sys
import os
from pathlib import Path

# Add src to sys.path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.append(str(project_root / "src"))

from warden_core.database import DatabaseManager
from warden_core.sid_helper import SID
import mysql.connector

def seed_test_data():
    print("Setting up test data...")
    db = DatabaseManager()
    sid_helper = SID()
    user_sid = sid_helper.GetSID()
    
    if not user_sid:
        print("Error: Could not determine current user SID.")
        return

    print(f"Current User SID: {user_sid}")
    
    # 1. Clear existing data for a fresh start
    print("Resetting database...")
    db.clear_all_tables()
    
    # 2. Clear local locked apps list
    print("Resetting local locked apps...")
    try:
        app_data_dir = Path(os.getenv('APPDATA')) / "Warden"
        locked_apps_file = app_data_dir / "locked_apps.json"
        if locked_apps_file.exists():
            os.remove(locked_apps_file)
            print(f"Removed {locked_apps_file}")
    except Exception as e:
        print(f"Warning: Could not clear local locked apps: {e}")
    
    # 3. Add family
    try:
        db.cursor.execute("INSERT IGNORE INTO families (parent_email) VALUES (%s)", ("test_parent@example.com",))
        db.cursor.execute("SELECT id FROM families WHERE parent_email=%s", ("test_parent@example.com",))
        family_id = db.cursor.fetchone()[0]
        
        # 3. Add child user (the current user)
        db.cursor.execute("INSERT IGNORE INTO users (family_id, sid, name, type) VALUES (%s, %s, %s, %s)", 
                          (family_id, user_sid, os.getlogin(), "child"))
        db.cursor.execute("SELECT id FROM users WHERE sid=%s", (user_sid,))
        user_id = db.cursor.fetchone()[0]
        
        # 4. Add app rule for testing (e.g., 1 minute for notepad.exe or calculator.exe)
        # Or better yet, a rule that is already expired for immediate testing
        test_app = "notepad.exe"
        db.cursor.execute("INSERT INTO app_rules (user_id, app_name, allowed_minutes) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE allowed_minutes=%s", 
                          (user_id, test_app, 1, 1))
        
        # To test device-wide lock, we'll set a high limit (999 minutes) for "DEVICE_TOTAL" 
        # so it doesn't trigger immediately, allowing us to focus on notepad.exe.
        db.cursor.execute("INSERT INTO app_rules (user_id, app_name, allowed_minutes) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE allowed_minutes=%s", 
                          (user_id, "DEVICE_TOTAL", 999, 999))
        
        db.db.commit()
        print(f"Successfully seeded database for user '{os.getlogin()}' (SID: {user_sid}) with 1 minute limit for '{test_app}' and 'DEVICE_TOTAL'.")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_test_data()
