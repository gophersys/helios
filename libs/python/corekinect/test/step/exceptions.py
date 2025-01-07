import inspect
from typing import Optional
from abc import abstractmethod

from .types import TestStepData


class BaseTestStepException(Exception):
    """
    Base exception class for test steps.
    This provides the common functionality for capturing the function name,
    marshalling data, and generating a custom message.
    """

    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        data: Optional[TestStepData] = None,
    ):
        """
        Initialize the BaseTestException with an error message, and capture the function name automatically.
        If data is provided, it calls the data's marshall method.
        """
        self.message: str = message
        self.details: Optional[str] = details
        self.data: Optional[TestStepData] = data

        # Capture the name of the calling function automatically
        frame = inspect.currentframe()
        try:
            self.function_name = inspect.getouterframes(frame, 2)[1].function
        finally:
            del frame  # Clean up the frame to avoid memory leaks

        # Call marshall on data if it's provided and is an instance of TestStepData
        if self.data and isinstance(self.data, TestStepData):
            self.marshalled_data = self.data.marshall()
        else:
            self.marshalled_data = None

        super().__init__(self.message)

    def __str__(self):
        """
        Override the string representation of the exception to include the function name, details, and marshalled data.
        """
        base_message = f"{self.get_prefix()} {self.message}"
        if self.function_name:
            base_message += f" | Name: {self.function_name}"
        if self.details:
            base_message += f" | Details: {self.details}"
        if self.marshalled_data:
            base_message += f" | Data: {self.marshalled_data}"
        return base_message

    @abstractmethod
    def get_prefix(self) -> str:
        """
        Method to get the prefix message for the exception.
        This should be overridden in derived classes.
        """
        return "Step exception:"


class PassTestStep(BaseTestStepException):
    """
    Exception to be raised when a test step passes.
    This is so that any step or sub-step can raise an exception to pass the test and provide a reason, in a clean way.
    """

    def get_prefix(self) -> str:
        return "Step passed:"


class FailTestStep(BaseTestStepException):
    """
    Exception to be raised when a test step fails.
    This is so that any step or sub-step can raise an exception to fail the test and provide a reason, in a clean way.
    """

    def get_prefix(self) -> str:
        return "Step failed:"


class ErrorTestStep(BaseTestStepException):
    """
    Exception to be raised when a test step errors.
    This is so that any step or sub-step can raise an exception to error the test and provide a reason, in a clean way.
    """

    def get_prefix(self) -> str:
        return "Step errored:"
