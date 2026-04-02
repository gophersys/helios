"""Corekinect — shared Python library for the Concord validation platform.

Top-level exports provide direct access to platform-wide concepts:

Errors:
    from corekinect import ValidationError, ConfigError, HardwareError
    from corekinect import FirmwareError, CloudError
    from corekinect import TimeoutError as ValidationTimeoutError

Stages:
    from corekinect import Stage, STAGE_NUMBERS, STAGE_NAMES
    from corekinect import StageBuildDef, get_stage_build_defs

Capabilities:
    from corekinect import Capability, Feature, FEATURE_REQUIREMENTS

Subpackages:
    corekinect.test        — Validation test framework
    corekinect.utils       — Logger, EnvConfig, time helpers
    corekinect.mtib_client — MTIB gRPC client
    corekinect.core_cloud  — CoreCloud REST API
    corekinect.core_ops    — CoreOps proxy client
    corekinect.firmware    — CFW generator
    corekinect.shells      — Device shell command interfaces
"""

__version__ = "0.2.0"

# ── Errors ──
from .errors import (
    CloudError,
    ConfigError,
    FirmwareError,
    HardwareError,
    TimeoutError,
    ValidationError,
)

# ── Stages ──
from .stages import (
    Stage,
    StageBuildDef,
    STAGE_NAMES,
    STAGE_NUMBERS,
    get_build_def,
    get_labels_with_cfw,
    get_labels_with_hex,
    get_quiet_labels,
    get_required_labels,
    get_stage_build_defs,
    get_stage_capabilities,
    get_verbose_labels,
)

# ── Capabilities ──
from .capabilities import (
    Capability,
    Feature,
    FEATURE_REQUIREMENTS,
)

__all__ = [
    # Errors
    "CloudError",
    "ConfigError",
    "FirmwareError",
    "HardwareError",
    "TimeoutError",
    "ValidationError",
    # Stages
    "Stage",
    "StageBuildDef",
    "STAGE_NAMES",
    "STAGE_NUMBERS",
    "get_build_def",
    "get_labels_with_cfw",
    "get_labels_with_hex",
    "get_quiet_labels",
    "get_required_labels",
    "get_stage_build_defs",
    "get_stage_capabilities",
    "get_verbose_labels",
    # Capabilities
    "Capability",
    "Feature",
    "FEATURE_REQUIREMENTS",
]
