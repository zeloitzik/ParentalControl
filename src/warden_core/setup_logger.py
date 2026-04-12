import logging
import os

class my_logger:
    def __init__(self,name,log_file,level=logging.INFO,log_directory="logs"):
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)
        self.name = name
        self.log_file = os.path.join(log_directory , log_file)
        self.level = level
    def setup_logger(self):
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        handler = logging.FileHandler(self.log_file, mode='w')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False # Prevents propagation to the root logger
        return logger


