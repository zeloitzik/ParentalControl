import os
import subprocess
import json
from pathlib import Path

class AppLocker:
    def __init__(self, config_file="locked_apps.json"):
        self.config_file = config_file
        self.locked_apps = self.load_config()
    
    def load_config(self):
        #Load locked apps from configuration file
        if Path(self.config_file).exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return []
    
    def save_config(self):
        #Save locked apps to configuration file
        with open(self.config_file, 'w') as f:
            json.dump(self.locked_apps, f)
    
    def lock_app(self, app_path):
        #Add app to locked list
        if app_path not in self.locked_apps:
            self.locked_apps.append(app_path)
            self.save_config()
            print(f"App locked: {app_path}")
    
    def unlock_app(self, app_path):
        #Remove app from locked list
        if app_path in self.locked_apps:
            self.locked_apps.remove(app_path)
            self.save_config()
            print(f"App unlocked: {app_path}")
    
    def is_locked(self, app_path):
        #Check if app is locked
        return app_path in self.locked_apps
    
    def list_locked_apps(self):
        #Display all locked apps
        return self.locked_apps

if __name__ == "__main__":
    locker = AppLocker()
    
    locker.lock_app("notepad.exe")
    locker.lock_app("calculator.exe")
    
    print("Locked apps:", locker.list_locked_apps())
    
    print("Is notepad locked?", locker.is_locked("notepad.exe"))