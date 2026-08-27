import logging

import pytest

from ..logx.logger import Logger


def test_logger_creation():
    """Test logger creation."""
    logger = Logger()
    assert isinstance(logger, Logger)
    assert isinstance(logger.logger, logging.Logger)
    assert logger.logger.name == "app_logger"


def test_logger_with_custom_name():
    """Test logger with custom name."""
    config = Logger.Config(logger_name="test_logger")
    logger = Logger(config)
    assert logger.logger.name == "test_logger"


@pytest.mark.skip("Test not implemented")
def test_logger_singleton_behavior():
    """Test logger singleton behavior."""
    pass


@pytest.mark.skip("Test not implemented")
def test_logger_methods():
    """Test logger methods."""
    pass


@pytest.mark.skip("Test not implemented")
def test_logger_exception_logging():
    """Test logger exception logging."""
    pass


def test_test_case_logger():
    """Test test case logger."""
    # Ensure that only one test case logger can be set
    config = Logger.Config(test_case_logger=True)
    logger = Logger(config)
    assert logger is Logger.get_test_case_logger()
    with pytest.raises(ValueError):
        Logger(config)  # Attempt to create another test case logger
