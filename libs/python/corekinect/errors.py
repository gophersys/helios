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

    Raised when:
    - Flash operation fails
    - DUT does not boot after power cycle
    - Firmware version doesn't match expected
    - CFW header is corrupt or malformed
    - MCUboot swap does not complete

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
    """CoreCloud API or FUOTA delivery failure.

    Raised when:
    - CoreCloud API returns an error
    - Device registration fails
    - FUOTA plan creation or assignment fails
    - FUOTA plan target mismatch (D-flag stripping)
    - CFW upload fails
    """


class TimeoutError(ValidationError):
    """Polling timeout for any asynchronous operation.

    Raised when:
    - Device does not check into CoreCloud within deadline
    - FUOTA delivery does not complete within deadline
    - Boot version not detected within deadline
    - FUOTA delivery never starts (stale data)

    Attributes:
        timeout_s: The timeout that was exceeded.
        elapsed_s: Actual elapsed time when timeout was raised.
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
