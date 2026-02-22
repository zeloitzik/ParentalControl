import psutil
import time
from datetime import datetime
import win32security
import logging
class TimeTracker:
    def __init__(self):
        logging.basicConfig(filename='time_tracker.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def get_sid_of_process(self,pid):
        try:
            process_handle = psutil.Process(pid)
            username = process_handle.username()
            sid_obj , domain , type = win32security.LookupAccountName(None, username)
            self.logger.debug("Got SID %s for process with PID %s", win32security.ConvertSidToStringSid(sid_obj), pid)
            return win32security.ConvertSidToStringSid(sid_obj)
        except:
            self.logger.error("Failed to get SID for process with PID %s", pid)
            return None
        
    def track_time(self, target_sid):
        self.logger.info("Starting time tracking for SID %s", target_sid)
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                pid = proc.info['pid']
                sid = self.get_sid_of_process(pid)
                if sid == target_sid:
                    start_time = datetime.fromtimestamp(proc.info['create_time'])
                    elapsed_time = datetime.now() - start_time
                    self.logger.info("Process %s (PID: %s) has been running for %s", proc.info['name'],pid,elapsed_time)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        self.logger.info("Finished time tracking for SID %s", target_sid)