import psutil
import win32security
import win32con
import logging
from datetime import datetime
import time
from datetime import timezone

class TimeTracker:

    def __init__(self):
        self.logger = logging.getLogger("process_tracker")
        self.active_processes = {}

    def get_sid_of_process(self, pid):
        try:
            # First, check if process exists
            if not psutil.pid_exists(pid):
                return None
                
            process = psutil.Process(pid)
            # Try to get SID from process token (more reliable than username lookup)
            import win32process
            import win32api
            import win32security
            import pywintypes

            try:
                # Open process token
                hProcess = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
                hToken = win32security.OpenProcessToken(hProcess, win32con.TOKEN_QUERY)
                # Get SID
                user_sid, _ = win32security.GetTokenInformation(hToken, win32security.TokenUser)
                win32api.CloseHandle(hToken)
                win32api.CloseHandle(hProcess)
                return win32security.ConvertSidToStringSid(user_sid)
            except Exception:
                # Fallback to username lookup if token access fails
                username = process.username()
                if not username:
                    return None
                # Split domain\user if present
                if '\\' in username:
                    username = username.split('\\')[-1]
                sid_obj, _, _ = win32security.LookupAccountName(None, username)
                return win32security.ConvertSidToStringSid(sid_obj)
        except Exception as exc:
            self.logger.debug("Failed to resolve SID for pid=%s: %s", pid, exc)
            return None

    def scan_processes(self, target_sid):

        current_processes = {}
        events = []
        for proc in psutil.process_iter(['pid','name']):
            try:
                pid = proc.info['pid']
                name = proc.info['name']

                sid = self.get_sid_of_process(pid)
                if sid != target_sid:
                    continue
                current_processes[pid] = name
                # NEW PROCESS
                if pid not in self.active_processes:
                    events.append({
                        "event_name": "APP_STARTED",
                        "app": name,
                        "pid": pid,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue


        # detect stopped processes
        for pid in list(self.active_processes):

            if pid not in current_processes:
                events.append({
                    "event_name": "APP_STOPPED",
                    "app": self.active_processes[pid],
                    "pid": pid,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })


        self.active_processes = current_processes

        return events

#Test
if __name__ == "__main__":
    tracker = TimeTracker()
    sid = tracker.get_sid_of_process(psutil.Process().pid)
    print("Current SID:", sid)
    while True:
        events = tracker.scan_processes(sid)
        for event in events:
            print(event)
        time.sleep(5)