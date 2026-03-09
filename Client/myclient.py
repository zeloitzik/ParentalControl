from socket import *
from my_service import MyParentalControlService
class my_client:
    def __init__(self, ip, port):
        self.soc = socket()
        self.ip = ip    
        self.port = port
        self.soc.connect((self.ip,self.port))
        self.service = MyParentalControlService()
    
    def install_service(self):
        self.service.Install()



def main():
    client = my_client("127.0.0.1", 12345)
main()