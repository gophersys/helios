"""Base timing utilities for validation tests.

Provides common timing constants and helpers that all products share.
Products define their own stage-specific timing by creating frozen
dataclasses and composing them with CommonTiming.

Framework usage:
    from corekinect.test.timing import CommonTiming, timeout, wait_with_progress

Product pattern (in apps/validation/{product}/tests/common/timing.py):

    from corekinect.test.timing import CommonTiming, timeout, wait_with_progress

    @dataclass(frozen=True)
    class FuotaTiming:
        TOTAL: int = 900
        FLASH_ALL: int = 150
        ...

    class Timing:
        FUOTA = FuotaTiming()
        REGRESSION = RegressionTiming()
        COMMON = CommonTiming()  # From framework
"""

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

import pytest

from corekinect.utils import Logger

F = TypeVar("F", bound=Callable)

_log = Logger(log_name="timing")


@dataclass(frozen=True)
class CommonTiming:
    """Timing constants common to all products and stages."""

    POWER_CYCLE_OFF: float = 2.0  # Time to stay powered off
    POWER_CYCLE_ON: float = 10.0  # Time to wait after power-on
    UART_SETTLE: float = 0.5  # UART buffer settle time
    MTIB_CONNECT: int = 10  # MTIB gRPC connection timeout


# Singleton instance for direct import
COMMON = CommonTiming()


def timeout(seconds: int) -> Callable[[F], F]:
    """Decorator to set pytest timeout on a test function.

    Usage:
        @timeout(300)
        def test_power_profile():
            ...
    """

    def decorator(func: F) -> F:
        """Decorator."""
        return pytest.mark.timeout(seconds)(func)

    return decorator


def wait_with_progress(
    duration_s: float,
    message: str = "Waiting",
    interval_s: float = 10.0,
    logger: Optional[Any] = None,
) -> None:
    """Wait with progress logging.

    Args:
        duration_s: Total wait time in seconds.
        message: Log message prefix.
        interval_s: Log interval.
        logger: Logger instance. Defaults to module logger.
    """
    out = logger or _log
    start = time.time()
    elapsed = 0.0

    while elapsed < duration_s:
        remaining = duration_s - elapsed
        out.info(
            "%s: %.0fs / %.0fs (%.0fs remaining)",
            message, elapsed, duration_s, remaining,
        )
        time.sleep(min(interval_s, remaining))
        elapsed = time.time() - start

    out.info("%s: complete (%.1fs)", message, elapsed)
