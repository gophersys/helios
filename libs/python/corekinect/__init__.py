"""Shared Python library for the Concord validation platform.

    from corekinect import Stage, ValidationError, HardwareError
    from corekinect.stages import get_stage_build_defs

Subpackages:
    corekinect.test        — Validation test framework
    corekinect.utils       — Logger, EnvConfig, time helpers
    corekinect.mtib_client — MTIB gRPC client
    corekinect.core_cloud  — CoreCloud REST API
    corekinect.core_ops    — CoreOps proxy client
    corekinect.firmware    — CFW generator
    corekinect.shells      — Device shell command interfaces
"""

__version__ = "0.12.3"

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
    StageType,
    StageBuildDef,
    STAGE_NAMES,
    STAGE_NUMBERS,
    STAGE_TYPES,
    get_build_def,
    get_labels_with_cfw,
    get_labels_with_hex,
    get_quiet_labels,
    get_required_labels,
    get_stage_build_defs,
    get_verbose_labels,
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
    "get_verbose_labels",
]
