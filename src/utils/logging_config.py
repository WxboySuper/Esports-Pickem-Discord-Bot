import os
import logging
import logging.handlers

os.makedirs('logs', exist_ok=True)


def configure_logging(level=logging.DEBUG, log_file='logs/app.log'):
    """
    Configure application logging with file and console handlers.

    Args:
        level (int): Logging level
        log_file (str): Path to the log file

    Returns:
        logging: The configured logging module.
    """
    logging.basicConfig(
        level=level,
        format='%(filename)s:%(lineno)d - %(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=1024 * 1024,
                backupCount=5
            ),
            logging.StreamHandler()
        ]
    )

    return logging
