"""Firmware utilities: CFW generation, parsing, and validation."""

from .cfw import (
    CfwMetadata,
    generate_cfw,
    generate_cfw_from_build,
    parse_cfw,
    encode_flags,
    TRACK_BENCH,
    TRACK_ENGINEERING,
    TRACK_PRODUCTION,
    APPID_NRF9151_COMMS,
    APPID_NRF52840_APP,
)

from .validator import (
    FirmwarePackageValidator,
    ValidationResult,
    ValidationError,
    VersionInfo,
    validate_package,
)

__all__ = [
    # CFW
    "CfwMetadata",
    "generate_cfw",
    "generate_cfw_from_build",
    "parse_cfw",
    "encode_flags",
    "TRACK_BENCH",
    "TRACK_ENGINEERING",
    "TRACK_PRODUCTION",
    "APPID_NRF9151_COMMS",
    "APPID_NRF52840_APP",
    # Validator
    "FirmwarePackageValidator",
    "ValidationResult",
    "ValidationError",
    "VersionInfo",
    "validate_package",
]
