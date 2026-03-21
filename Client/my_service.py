#Windows sercive template
#Maybe switch to c++ 
import datetime
import win32serviceutil
import win32service
import win32event
import requests
import time
from SID import SID
import logging
import my_time

'''
Need to gather the SID of all the users, store in a database and distinguish
between a parent and a child. 
Needs to also add the time limits for each  chlid.
'''


class MyParentalControlService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WardenService"
    _svc_display_name_ = "Warden's Parental Control Service"
    _svc_description_ = "Monitors user SIDs and enforces lockouts."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.user_SID = SID.GetSID()
        logging.basicConfig(filename='service.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.server_url = "http://localhost:8000/event"
        self.logger = logging.getLogger(__name__)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False

    def SvcDoRun(self):
        tracker = my_time.TimeTracker()
        while self.is_running:
            events = tracker.scan_processes(self.user_SID)
            for event in events:
                self.send_event(
                    event["event_name"],
                    {"app": event["app"]}
                )
            time.sleep(5)

    def send_event(self, event_name, metadata):
        event = {
            "sid": self.user_SID,
            "event_name": event_name,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            requests.post(self.server_url, json=event, timeout=2)
        except Exception as e:
            self.logger.error(f"Failed sending event: {e}")
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
    win32serviceutil.HandleCommandLine(MyParentalControlService)