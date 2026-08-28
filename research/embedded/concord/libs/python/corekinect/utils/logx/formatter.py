import logging

from termcolor import colored


class CustomFormatter(logging.Formatter):
    """Custom logging formatter to add colors and customize the message format."""

    # Define level name mappings
    LEVEL_NAMES = {
        logging.DEBUG: "DBG",
        logging.INFO: "INF",
        logging.WARNING: "WRN",
        logging.ERROR: "ERR",
        logging.CRITICAL: "CRT",
    }

    # Define different formats for debug vs other levels
    FORMAT = "%(asctime)s - %(levelshort)s - %(name)s - %(message)s"

    # Define color formats for different log levels
    FORMATS = {
        logging.DEBUG: colored(FORMAT, "white"),
        logging.INFO: colored(FORMAT, "blue"),
        logging.WARNING: colored(FORMAT, "yellow"),
        logging.ERROR: colored(FORMAT, "red"),
        logging.CRITICAL: colored(FORMAT, "red", attrs=["bold"]),
    }

    def format(self, record):
        """Apply the appropriate format to the log message based on its level."""
        # Add custom levelshort attribute
        record.levelshort = self.LEVEL_NAMES.get(record.levelno, record.levelname)

        log_fmt = self.FORMATS.get(record.levelno)

        # For debug level, set funcName as the first part of the message
        if record.levelno == logging.DEBUG:
            # Remove the "debug" function name if it's from our decorator
            if record.funcName == "debug":
                record.funcName = record.msg.split(":")[0]
                record.msg = record.msg.split(":", 1)[1].strip()
            record.msg = f"{record.funcName} - {record.msg}"

        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
