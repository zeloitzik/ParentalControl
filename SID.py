#Getting the SID of the current user

import win32security
import logging
from setup_logger import my_logger
class SID:
    def __init__(self):
        self.logger = my_logger("SID", "sid.log", logging.DEBUG).setup_logger()
        self.sidstr = None
    def GetSID(self):
        desc = win32security.GetFileSecurity(
            ".", win32security.OWNER_SECURITY_INFORMATION # "." = current working directory
        )

        sid = desc.GetSecurityDescriptorOwner()

        self.sidstr = win32security.ConvertSidToStringSid(sid)
        self.logger.debug("SID is %s", self.sidstr)
        return self.sidstr

#Test
if __name__ == "__main__":
    sid = SID()
    print(sid.GetSID())
