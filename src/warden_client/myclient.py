import sys
from pathlib import Path
from socket import *

# Add src directory to path so warden_core modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service import MyParentalControlService
from warden_core.setup_logger import my_logger

class my_client:
    def __init__(self, ip, port):
        self.soc = socket()
        self.ip = ip    
        self.port = port
        logger_instance = my_logger(self.__class__.__name__, "client.log")
        self.logger = logger_instance.setup_logger()
        self.logger.info("Connecting to server at %s:%s", ip, port)
        self.soc.connect((self.ip,self.port))
        self.logger.info("Connected to server successfully")
        self.service = MyParentalControlService()
        self.logger.info("Service initialized")
    
    def install_service(self):
        self.service.Install()



def main():
    client = my_client("127.0.0.1", 12345)
main()