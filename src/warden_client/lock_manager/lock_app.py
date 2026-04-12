import os
import json
import logging
from pathlib import Path

class AppLocker:
    def __init__(self, config_file=None):
        if config_file is None:
            # Place in a persistent location
            app_data_dir = Path(os.getenv('APPDATA')) / "Warden"
            app_data_dir.mkdir(parents=True, exist_ok=True)
            self.config_file = app_data_dir / "locked_apps.json"
        else:
            self.config_file = Path(config_file)
            
        self.logger = logging.getLogger("AppLocker")
        self.locked_apps = self.load_config()
    
    def load_config(self):
        #Load locked apps from configuration file
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error("Failed to load locked_apps config: %s", e)
        return []
    
    def save_config(self):
        #Save locked apps to configuration file
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.locked_apps, f)
        except Exception as e:
            self.logger.error("Failed to save locked_apps config: %s", e)
    
    def lock_app(self, app_name):
        #Add app to locked list (using app_name for consistency with service's event data)
        if app_name not in self.locked_apps:
            self.locked_apps.append(app_name)
            self.save_config()
            self.logger.info("App locked: %s", app_name)
    
    def unlock_app(self, app_name):
        #Remove app from locked list
        if app_name in self.locked_apps:
            self.locked_apps.remove(app_name)
            self.save_config()
            self.logger.info("App unlocked: %s", app_name)
    
    def is_locked(self, app_name):
        #Check if app is locked
        return app_name in self.locked_apps
    
    def list_locked_apps(self):
        #Display all locked apps
        return self.locked_apps

if __name__ == "__main__":
    locker = AppLocker()
    locker.lock_app("notepad.exe")
    print("Locked apps:", locker.list_locked_apps())
    print("Is notepad locked?", locker.is_locked("notepad.exe"))