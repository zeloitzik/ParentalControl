import psutil
import win32security
import logging
from datetime import datetime
import time

class TimeTracker:

    def __init__(self):
        self.logger = logging.getLogger("process_tracker")
        self.active_processes = {}

    def get_sid_of_process(self, pid):

        try:
            process = psutil.Process(pid)
            username = process.username()

            sid_obj, domain, type = win32security.LookupAccountName(None, username)
            return win32security.ConvertSidToStringSid(sid_obj)
        except Exception:
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
                        "timestamp": datetime.utcnow().isoformat()
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
                    "timestamp": datetime.utcnow().isoformat()
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