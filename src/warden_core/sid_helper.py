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
            # When running as a service (SYSTEM), we need to find the interactive session user.
            # This is a simplified approach for single-user interactive session.
            import psutil
            import win32security
            import win32api

            # Try to find explorer.exe which usually runs as the logged in user
            for proc in psutil.process_iter(['name', 'username']):
                if proc.info['name'].lower() == 'explorer.exe':
                    username = proc.info['username']
                    if username:
                        # username is usually "DOMAIN\User"
                        if '\\' in username:
                            domain, user = username.split('\\', 1)
                        else:
                            user = username
                        
                        sid_obj, domain, account_type = win32security.LookupAccountName(None, user)
                        self.sidstr = win32security.ConvertSidToStringSid(sid_obj)
                        self.logger.debug("Found active user SID via explorer.exe: %s", self.sidstr)
                        return self.sidstr

            # Fallback to previous logic if explorer not found (maybe no one logged in)
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
