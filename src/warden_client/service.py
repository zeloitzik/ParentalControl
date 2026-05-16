import sys
import os
from pathlib import Path

# Add src to sys.path if running as script to allow absolute imports
current_dir = Path(__file__).resolve().parent
if (current_dir.parent / "warden_core").exists():
    sys.path.append(str(current_dir.parent.parent))

#Windows sercive template
#Maybe switch to c++ 
import datetime
import win32serviceutil
import win32service
import win32event
import time
import logging
import subprocess

# Standard imports assuming sys.path is correct
try:
    import warden_core.sid_helper as sid_helper
    import warden_client.time_tracker as time_tracker
    import warden_client.lock_manager.lock_app as lock_app
    SID = sid_helper.SID
    TimeTracker = time_tracker.TimeTracker
    AppLocker = lock_app.AppLocker
except ImportError:
    # Use absolute paths as last resort
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    import warden_core.sid_helper as sid_helper
    import warden_client.time_tracker as time_tracker
    import warden_client.lock_manager.lock_app as lock_app
    SID = sid_helper.SID
    TimeTracker = time_tracker.TimeTracker
    AppLocker = lock_app.AppLocker

class MyParentalControlService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WardenService"
    _svc_display_name_ = "Warden's Parental Control Service"
    _svc_description_ = "Monitors user SIDs and enforces lockouts."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.sid_helper = SID()
        self.user_SID = self.sid_helper.GetSID()
        logging.basicConfig(filename='service.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.net_client = WardenNetClient(host="192.168.1.213", port=8000)
        self.logger = logging.getLogger(__name__)
        self.app_locker = AppLocker()
        self.lock_screen_active = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False

    def SvcDoRun(self):
        tracker = TimeTracker()
        while self.is_running:
            try:
                # Re-check SID in case of user switch (if service survives logout)
                self.user_SID = self.sid_helper.GetSID()
                if not self.user_SID:
                    time.sleep(5)
                    continue

                self.logger.info("Service loop start for SID: %s", self.user_SID)
                
                # 1. Periodic check for overall device time and running apps
                self.enforce_policies(tracker)

                # 2. Scan for process changes (starts/stops)
                events = tracker.scan_processes(self.user_SID)
                for event in events:
                    if event["event_name"] == "APP_STARTED":
                        app_name = event["app"]
                        pid = event["pid"]
                        
                        # Check local registry first
                        blocked_locally = False
                        if self.app_locker.is_locked(app_name):
                            self.logger.info("App is locked locally: %s", app_name)
                            blocked_locally = True

                        allowed = self.check_with_server(app_name)
                        
                        if allowed is True:
                            # Server says allowed, so unblock
                            blocked_locally = False
                        elif allowed is None and blocked_locally:
                            # Server unreachable, rely on local cache
                            pass
                        elif allowed is False:
                            # Server says blocked
                            blocked_locally = True
                            self.app_locker.lock_app(app_name)
                            
                        if blocked_locally:
                            self.logger.info("Blocking app: %s", app_name)
                            self.kill_process(pid)
                            self.trigger_lock_screen()

                        # Always send START event to server so it's recorded in app_sessions
                        self.send_event(
                            "APP_STARTED",
                            {"app": app_name, "pid": pid}
                        )

                        if blocked_locally or not allowed:
                            continue

                    else:
                        self.send_event(
                            event["event_name"],
                            {"app": event["app"], "pid": event["pid"]}
                        )
            except Exception as e:
                self.logger.error("Error in service loop: %s", e)
            
            time.sleep(5)

    def enforce_policies(self, tracker):
        """
        Periodically checks if the user has exceeded their time limits.
        If so, triggers the lock screen or kills the violating process.
        """
        self.logger.info("Enforcing policies. Active apps: %s", list(tracker.active_processes.values()))


        # 2. Check each active process
        for pid, app_name in list(tracker.active_processes.items()):
            allowed = self.check_with_server(app_name)
            if allowed is False:
                self.logger.info("Time limit reached for %s (PID %s). Killing.", app_name, pid)
                self.app_locker.lock_app(app_name)
                self.kill_process(pid)
                self.trigger_lock_screen()

    def trigger_lock_screen(self):
        """
        Launches the lock_screen UI. 
        Using subprocess to run it as a separate process to avoid blocking the service.
        Needs to run in the user session context if possible. 
        Note: Python services run as SYSTEM, so launching UI requires care.
        """
        if self.lock_screen_active: 
            return

        try:
            # Check if running as a PyInstaller compiled executable
            if getattr(sys, 'frozen', False):
                # The lock_screen.exe should be in the same directory as the service executable
                base_dir = os.path.dirname(sys.executable)
                exe_path = os.path.join(base_dir, "lock_screen.exe")
                subprocess.Popen([exe_path])
            else:
                # We launch the lock_screen script. 
                # In a real service, we'd use CreateProcessAsUser to target the active session.
                # Here we assume a simple subprocess might reach the desktop if permissions allow or for demo purposes.
                script_path = os.path.join(os.path.dirname(__file__), "lock_manager", "lock_screen.py")
                # Set PYTHONPATH so lock_screen can find warden_core if needed
                new_env = os.environ.copy()
                src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                new_env["PYTHONPATH"] = src_path
                
                subprocess.Popen([sys.executable, script_path], env=new_env)
            self.lock_screen_active = True
            self.logger.info("Lock screen triggered.")
        except Exception as e:
            self.logger.error("Failed to trigger lock screen: %s", e)

    def check_with_server(self, app_name):
        try:
            payload = {"sid": self.user_SID, "app": app_name}
            data = self.net_client.send_command("check_app", payload)
            
            # Pass usage data to UI if available
            used_minutes = data.get("used_minutes", 0)
            self.update_ui_logs(app_name, used_minutes)
            
            allowed = data.get("allowed", True)
            self.logger.info("Check app %s: allowed=%s, used=%s", app_name, allowed, used_minutes)
            
            if allowed:
                self.app_locker.unlock_app(app_name)
                
            return allowed
        except Exception as e:
            self.logger.error("Failed to check with server for %s: %s", app_name, e)
            return None # Fail-safe, rely on local registry

    def update_ui_logs(self, app_name, used_minutes):
        """Helper to send usage data to the lock screen or log it."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Convert minutes to HH:MM:SS
            total_seconds = int(used_minutes * 60)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            log_entry = f"[{timestamp}] [{app_name}] - Duration: [{duration_str}]"
            self.logger.info("UI_LOG: %s", log_entry)
            
            # In a real app, we might send this via a queue or socket to the UI process.
            # For now, we'll write it to a shared file that the UI can read.
            log_path = Path(os.getenv('APPDATA')) / "Warden" / "usage_display.log"
            with open(log_path, "a") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            self.logger.error("Failed to update UI logs: %s", e)

    def kill_process(self, pid):
        try:
            import psutil
            p = psutil.Process(pid)
            p.terminate()
            self.logger.info("Killed blocked process: PID %s", pid)
        except Exception as e:
            self.logger.error("Failed to kill process %s: %s", pid, e)

    def apply_local_fallback_policy(self, event):
        # Placeholder for local cache logic
        pass

    def send_event(self, event_name, metadata):
        event = {
            "sid": self.user_SID,
            "event_name": event_name,
            "metadata": metadata,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        try:
            self.net_client.send_command("event", event)
        except Exception as e:
            self.logger.error("Server unavailable for event %s: %s", event_name, e)
            self.apply_local_fallback_policy(event)
    def Install(self):
        win32serviceutil.InstallService(
            MyParentalControlService._svc_name_,
            MyParentalControlService._svc_display_name_,
            MyParentalControlService._svc_description_
        )
        self.logger.info("Service installed successfully.")
    def Start(self):
        win32serviceutil.StartService(MyParentalControlService._svc_name_)
        self.logger.info("Service started successfully.")
    def Stop(self):
        win32serviceutil.StopService(MyParentalControlService._svc_name_)
        self.logger.info("Service stopped successfully.")
    def Uninstall(self):
        win32serviceutil.RemoveService(MyParentalControlService._svc_name_)
        self.logger.info("Service uninstalled successfully.")
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        # Simple test runner
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        class MockService(MyParentalControlService):
            def __init__(self, args):
                # Absolute imports using PYTHONPATH
                import warden_core.sid_helper as sid_helper
                import warden_client.time_tracker as time_tracker
                from warden_client.lock_manager.lock_app import AppLocker
                from warden_client.net_client import WardenNetClient
                
                self.hWaitStop = None
                self.is_running = True
                self.sid_helper = sid_helper.SID()
                self.user_SID = self.sid_helper.GetSID()
                self.net_client = WardenNetClient(host="192.168.1.213", port=8000)
                self.logger = logging.getLogger(__name__)
                self.app_locker = AppLocker()
                self.lock_screen_active = False
            
            def ReportServiceStatus(self, *args):
                pass
                
        service = MockService(None)
        print("Starting Service in test mode (script). Press Ctrl+C to stop.")
        try:
            service.SvcDoRun()
        except KeyboardInterrupt:
            print("Stopping...")
    else:
        win32serviceutil.HandleCommandLine(MyParentalControlService)