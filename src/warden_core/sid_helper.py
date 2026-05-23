#Getting the SID of the current user

import win32security
import logging
from warden_core.setup_logger import my_logger
class SID:
    def __init__(self):
        self.logger = my_logger("SID", "sid.log", logging.DEBUG).setup_logger()
        self.sidstr = None
    def GetSID(self):
        try:
            import win32security
            import ctypes

            session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
            wtsapi32 = ctypes.windll.wtsapi32
            buffer = ctypes.c_wchar_p()
            bytes_returned = ctypes.c_uint()
            
            username = None
            domain = None
            
            # WTSUserName = 5
            if wtsapi32.WTSQuerySessionInformationW(0, session_id, 5, ctypes.byref(buffer), ctypes.byref(bytes_returned)):
                username = buffer.value
                wtsapi32.WTSFreeMemory(buffer)
                
            # WTSDomainName = 7
            if wtsapi32.WTSQuerySessionInformationW(0, session_id, 7, ctypes.byref(buffer), ctypes.byref(bytes_returned)):
                domain = buffer.value
                wtsapi32.WTSFreeMemory(buffer)
                
            if username:
                user_str = f"{domain}\\{username}" if domain else username
                sid_obj, _, _ = win32security.LookupAccountName(None, user_str)
                self.sidstr = win32security.ConvertSidToStringSid(sid_obj)
                self.logger.debug("Found active user SID via WTS: %s", self.sidstr)
                return self.sidstr

            # Fallback if no active session
            desc = win32security.GetFileSecurity(
                ".", win32security.OWNER_SECURITY_INFORMATION
            )
            sid = desc.GetSecurityDescriptorOwner()
            self.sidstr = win32security.ConvertSidToStringSid(sid)
            self.logger.debug("SID (fallback) is %s", self.sidstr)
            return self.sidstr
        except Exception as e:
            self.logger.error("Failed to GetSID: %s", e)
            return None

#Test
if __name__ == "__main__":
    sid = SID()
    print(sid.GetSID())
