import os
import logging
import logging.handlers

os.makedirs('logs', exist_ok=True)


def clear_log_file(log_file='logs/app.log'):
    """
    Clear the contents of the log file.

    Args:
        log_file (str): Path to the log file to clear
    """
    if os.path.exists(log_file):
        # Open in write mode and truncate
        with open(log_file, 'w') as f:
            f.write('')  # Write empty string
        print(f"Log file cleared: {log_file}")


def configure_logging(level=logging.DEBUG, log_file='logs/app.log', clear_logs=False):
    """
    Configure application logging with file and console handlers.

    Args:
        level (int): Logging level
        log_file (str): Path to the log file
        clear_logs (bool): Whether to clear the log file before configuring

    Returns:
        logging: The configured logging module.
    """
    # Clear the log file if requested - MUST happen BEFORE configuring logging
    if clear_logs:
        clear_log_file(log_file)

    # Reset any existing loggers before configuring
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

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
