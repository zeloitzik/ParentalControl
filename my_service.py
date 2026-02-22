#Windows sercive template
#Maybe switch to c++ 
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import time
import subprocess
from SID import SID
import logging
'''
Need to gather the SID of all the users, store in a database and distinguish
between a parent and a child. 
Needs to also add the time limits for each  chlid.
'''


class MyParentalControlService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PyParentalGuard"
    _svc_display_name_ = "Parental Control Service"
    _svc_description_ = "Monitors user SIDs and enforces lockouts."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.SID = "S-1-5-21-3604211619-2338144593-13737068-1001"
        logging.basicConfig(filename='service.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False

    def SvcDoRun(self):
        # This is where  logic goes
        while self.is_running:
            # TODO: Check which SID is logged in
            '''
            Checks with server if the child is over the time limit.
            '''
            # TODO: If it's the child, launch the Lock UI
            time.sleep(5) 

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