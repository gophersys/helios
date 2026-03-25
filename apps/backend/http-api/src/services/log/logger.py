from corekinect.utils import Logger

_logger: Logger = None


def init_logger(config: Logger.Config):
    """Initialize the logger"""
    global _logger
    _logger = Logger(config)


def get_logger():
    return _logger
