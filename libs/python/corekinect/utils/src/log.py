import inspect
import logging
import os
import random
import string
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime

from termcolor import colored


class CustomFormatter(logging.Formatter):
    """Custom logging formatter to add colors and customize the message format."""

    # Default format for logs
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Define color formats for different log levels
    FORMATS = {
        logging.DEBUG: colored(format, "white"),
        logging.INFO: colored(format, "blue"),
        logging.WARNING: colored(format, "yellow"),
        logging.ERROR: colored(format, "red"),
        logging.CRITICAL: colored(format, "red", attrs=["bold"]),
    }

    def format(self, record):
        """Apply the color format to the log message based on its level."""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Logger:
    """
    A logger class that provides versatile logging capabilities to both console and file.

    Parameters:
        config (Config): The configuration object for the logger.

    Returns:
        Logger: A logger object with the specified configuration.

    Raises:
        ValueError: If a test case logger is already set in the context.

    Examples:
        ### Create a logger with default configuration:
        log = Logger(Logger.Config())

        ### Create a logger for test case logging:
        test_case_log = Logger(Logger.Config(test_case_logger=True))

    """

    # Add the context variable
    test_case_logger = ContextVar("test_case_logger", default=None)

    class Config:
        """
        Configuration structure for the logger.

        Parameters:
            logger_name (str): The name of the logger (appears in log messages).
            log_file_name (str): The log file name; if None, a name is generated automatically. Defaults to None.
            log_directory (str): The directory where log files will be saved. Defaults to "./logs".
            overall_log_level (int): The overall log level for the logger. Defaults to logging.DEBUG.
            console_log_level (int): The log level for console output (e.g., DEBUG, INFO). Defaults to logging.INFO.
            file_log_level (int): The log level for file output. Defaults to logging.DEBUG.
            enable_log_color (bool): Whether to enable colored logs in the console. Defaults to True.
            test_case_logger (bool): This flag is used to determine if the logger is for test case logging. Defaults to False.

        Returns:
            Config: A configuration object for the logger.

        Raises:
            None

        """

        def __init__(
            self,
            logger_name: str = "app_logger",
            log_file_name: str = None,
            log_directory: str = "./logs",
            overall_log_level: int = logging.DEBUG,
            console_log_level: int = logging.INFO,
            file_log_level: int = logging.DEBUG,
            enable_log_color: bool = True,
            test_case_logger: bool = False,
        ):
            self.logger_name = logger_name
            self.log_file_name = log_file_name
            self.log_directory = log_directory
            self.overall_log_level = overall_log_level
            self.console_log_level = console_log_level
            self.file_log_level = file_log_level
            self.enable_log_color = enable_log_color
            self.test_case_logger = test_case_logger

    def __init__(self, config: Config = None):
        """Initialize the Logger class with the given configuration."""

        if config is None:
            config = Logger.Config()

        self.config = config
        self.logger = logging.getLogger(self.config.logger_name)

        # Avoid duplicate handlers by removing existing handlers if any
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Prevent the logger from propagating messages to the root logger
        self.logger.propagate = False

        self._setup_logger()

        # If this logger is marked as a test case logger, set it in the context
        if self.config.test_case_logger:

            # Check if a test case logger is already set
            _existing_test_case_logger = Logger.test_case_logger.get()
            if _existing_test_case_logger is not None:
                raise ValueError(
                    "A test case logger is already set in the context. Only one test case logger is allowed."
                )

            # Set the test case logger in the context
            Logger.test_case_logger.set(self)

    def _setup_logger(self):
        """Set up the logger with console and file handlers."""
        self.logger.setLevel(self.config.overall_log_level)

        # Ensure the logs directory exists
        os.makedirs(self.config.log_directory, exist_ok=True)

        # Generate log file name if not provided
        if not self.config.log_file_name:
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
            log_file_name = f"{self.config.logger_name}_{current_time}_{random_suffix}.log"
            self.config.log_file_name = os.path.join(self.config.log_directory, log_file_name)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.config.console_log_level)

        # Create file handler
        file_handler = logging.FileHandler(self.config.log_file_name)
        file_handler.setLevel(self.config.file_log_level)

        # Apply formatters (log format is fixed and not customizable by the user)
        if self.config.enable_log_color:
            console_handler.setFormatter(CustomFormatter())
        else:
            console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        # Add handlers to the logger
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def debug(self, message, *args):
        """Log a message at DEBUG level, including the function name or module."""
        current_stack = inspect.stack()[1]
        current_function = current_stack.function
        if current_function == "<module>":
            current_function = "__main__"

        # Log the message, including the function or module name
        self.logger.debug(f"{current_function}: {message}", *args)

    def info(self, message, *args):
        """Log a message at INFO level."""
        self.logger.info(message, *args)

    def warning(self, message, *args):
        """Log a message at WARNING level."""
        self.logger.warning(message, *args)

    def error(self, message, *args):
        """Log a message at ERROR level. If there is an active exception being handled, log the full stack trace."""
        # Check if an exception is being handled in the current context
        exc_type, exc_value, _ = sys.exc_info()

        if exc_type is not None:
            # If there's an active exception, log the message with the full stack trace
            self.logger.error(f"{message}\nException: {exc_value}", exc_info=True, *args)
        else:
            # If no exception is active, log the message normally
            self.logger.error(message, *args)

    def critical(self, message, *args):
        """Log a message at CRITICAL level. If there is an active exception being handled, log the full stack trace."""
        # Check if an exception is being handled in the current context
        exc_type, exc_value, _ = sys.exc_info()

        if exc_type is not None:
            # If there's an active exception, log the message with the full stack trace
            self.logger.critical(f"{message}\nException: {exc_value}", exc_info=True, *args)
        else:
            # If no exception is active, log the message normally
            self.logger.critical(message, *args)

    def exception(self, message, *args):
        """Log a message at ERROR level with the full stack trace."""
        self.logger.exception(message, *args)

    @staticmethod
    def get_test_case_logger() -> "Logger":
        """Retrieve the current logger from the context variable."""

        _existing_test_case_logger = Logger.test_case_logger.get()
        if _existing_test_case_logger is None:
            return Logger(Logger.Config(test_case_logger=True))

        return _existing_test_case_logger
