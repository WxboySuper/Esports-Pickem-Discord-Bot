import os
import logging

os.makedirs('logs', exist_ok=True)

def configure_logging():
    log = logging.getLogger()
    
    log.basicConfig(
        level=logging.DEBUG,
        format='%(filename)s:%(lineno)d - %(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler('logs/app.log'),
            logging.StreamHandler()
        ]
    )
    
    return log