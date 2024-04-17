# Standard includes
import logging
import os
import random
import string
from datetime import datetime

# Third Party includes
from termcolor import colored

class CustomFormatter(logging.Formatter):
    """Custom logging formatter to add colors and customize the message format."""

    # Define format
    format = "%(asctime)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: colored(format, 'white'),
        logging.INFO: colored(format, 'blue'),
        logging.WARNING: colored(format, 'yellow'),
        logging.ERROR: colored(format, 'red'),
        logging.CRITICAL: colored(format, 'red', attrs=['bold']),
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logging(conf):
    """ Sets up the global logger with colors in the terminal output,
        as well as a file log writter so that we can save the server 
        logs for debugging purposes """
    
    # Generate log file name with current timestamp and a random suffix
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    log_file_name = f"test_{current_time}_{random_suffix}.log"
    log_file_path = os.path.join(conf.LOG_PATH, log_file_name)

    # Ensure the logs directory exists
    os.makedirs(conf.LOG_PATH, exist_ok=True)

    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Set to lowest level to handle filtering with handlers

    # Create handlers
    c_handler = logging.StreamHandler()  # Console handler
    f_handler = logging.FileHandler(log_file_path)  # File handler
    
    # Set levels based on configuration
    if conf.LOG_LEVEL == 4:
        c_handler.setLevel(logging.DEBUG)
    elif conf.LOG_LEVEL == 3:
        c_handler.setLevel(logging.INFO)
    elif conf.LOG_LEVEL == 2:
        c_handler.setLevel(logging.WARNING)
    elif conf.LOG_LEVEL == 1:
        c_handler.setLevel(logging.ERROR)
    else:
        raise ValueError(f"Invalid debug level {conf.LOG_LEVEL}. Valid values 0-4")

    f_handler.setLevel(logging.DEBUG)  # File handler logs everything

    # Create formatters and add it to handlers
    c_formatter = CustomFormatter()
    f_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    c_handler.setFormatter(c_formatter)
    f_handler.setFormatter(f_formatter)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)