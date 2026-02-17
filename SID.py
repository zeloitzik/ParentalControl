#Getting the SID of the current user

import win32security
import logging
class SID:
    def __init__(self):
        logging.basicConfig(filename='SID.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        self.sidstr = None
    def GetSID(self):
        desc = win32security.GetFileSecurity(
            ".", win32security.OWNER_SECURITY_INFORMATION # "." = current working directory
        )

        sid = desc.GetSecurityDescriptorOwner()

        self.sidstr = win32security.ConvertSidToStringSid(sid)
        self.logger.debug("SID is %s", self.sidstr)
        return self.sidstr

