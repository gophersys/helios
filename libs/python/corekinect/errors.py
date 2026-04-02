"""Structured error types for the validation test framework.

All framework exceptions inherit from ``ValidationError``. This lets
runners and reporters catch and categorize failures by type instead
of parsing error message strings.

Hierarchy:
    ValidationError          Base for all framework errors
    ├── ConfigError          Profile, manifest, environment config
    ├── HardwareError        MTIB, power, GPIO, flash failures
    ├── FirmwareError        Boot, version mismatch, CFW parsing
    ├── CloudError           CoreCloud API, FUOTA delivery
    └── TimeoutError         Any polling timeout (cloud, FUOTA, boot)

Usage:
    from corekinect.errors import CloudError, FirmwareError

    raise CloudError("Device not registered in CoreCloud")
    raise FirmwareError(
        "Version mismatch: expected 0.5.2, got 0.5.1",
        expected="0.5.2",
        actual="0.5.1",
    )
"""


class ValidationError(Exception):
    """Base exception for all validation framework errors.

    Runners can catch this to handle any framework-level failure
    without catching unrelated Python exceptions.
    """


class ConfigError(ValidationError):
    """Fixture profile, manifest, or environment configuration error.

    Raised when:
    - Required environment variables are missing
    - Fixture profile JSON is malformed or missing required fields
    - Stage build labels are missing from a pipeline
    - concord.test.yaml manifest is invalid
    """


class HardwareError(ValidationError):
    """MTIB, power, GPIO, or physical hardware failure.

    Raised when:
    - MTIB gRPC connection fails
    - Power read returns unexpected values
    - GPIO configuration fails
    - J-Link probe not found
    """


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
