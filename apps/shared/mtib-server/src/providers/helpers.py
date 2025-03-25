import functools
import time
from typing import Callable, TypeVar, ParamSpec


# Type variables for generic function signature
P = ParamSpec("P")
R = TypeVar("R")


def grpc_method(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator for gRPC methods that automatically logs request timing and client info.

    Usage:
        @grpc_method
        def HealthCheck(self, request: Empty, context: grpc.ServicerContext) -> HealthCheckResponse:
            response = HealthCheckResponse(ready=True)
            return response
    """

    @functools.wraps(func)
    def method(self, request, context, *args, **kwargs) -> R:
        # Get method name from the original function
        method_name = func.__name__

        # Log request received
        self.logger.debug(f"{method_name}: Request received from client at {context.peer()}")

        # Time the request
        start_time = time.time()

        try:
            # Execute the original function
            response = func(self, request, context, *args, **kwargs)

            # Log request completion time
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"{method_name}: Request processed in {elapsed_ms:.2f}ms")

            return response

        except Exception as e:
            # Log any errors that occur
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.error(f"{method_name}: Request failed after {elapsed_ms:.2f}ms")
            raise  # Re-raise the exception

    return method
