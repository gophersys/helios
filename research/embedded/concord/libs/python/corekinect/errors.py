"""Structured error types for the validation framework.

    from corekinect.errors import CloudError, FirmwareError

    raise CloudError("Device not registered in CoreCloud")
    raise FirmwareError("Version mismatch", expected="0.5.2", actual="0.5.1")

Hierarchy:
    ValidationError          Base for all framework errors
    ├── ConfigError          Profile, manifest, environment config
    ├── HardwareError        MTIB, power, GPIO, flash failures
    ├── FirmwareError        Boot, version mismatch, CFW parsing
    ├── CloudError           CoreCloud API, FUOTA delivery
    └── TimeoutError         Any polling timeout (cloud, FUOTA, boot)
"""


class ValidationError(Exception):
    """Base exception for all validation framework errors."""


class ConfigError(ValidationError):
    """Fixture profile, manifest, or environment configuration error."""


class HardwareError(ValidationError):
    """MTIB, power, GPIO, or physical hardware failure."""


class FirmwareError(ValidationError):
    """Firmware flash, boot, version, or CFW parsing failure.

    Attributes:
        expected: Expected value (version, state, etc.).
        actual: Actual observed value.
    """

    def __init__(
        self,
        message: str,
        expected: str = "",
        actual: str = "",
    ):
        self.expected = expected
        self.actual = actual
        super().__init__(message)


class CloudError(ValidationError):
    """CoreCloud API or FUOTA delivery failure."""


class TimeoutError(ValidationError):
    """Polling timeout for any async operation (cloud, FUOTA, boot).

    Attributes:
        timeout_s: The timeout that was exceeded.
        elapsed_s: Actual elapsed time when raised.
    """

    def __init__(
        self,
        message: str,
        timeout_s: float = 0,
        elapsed_s: float = 0,
    ):
        self.timeout_s = timeout_s
        self.elapsed_s = elapsed_s
        super().__init__(message)
