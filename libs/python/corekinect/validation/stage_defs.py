"""Canonical stage and build definitions for the Concord validation platform.

THIS IS THE SINGLE SOURCE OF TRUTH for what firmware builds each
validation stage requires. Both the build service and the test framework
import from here. No other module should define stage build matrices.

Consumers:
    Build service (apps/backend/http-api/):
        from corekinect.validation.stage_defs import get_stage_build_defs, Stage
        defs = get_stage_build_defs(Stage.FUOTA)
        for d in defs:
            create_build_job(label=d.label, fw_type=d.fw_type, ...)

    Test framework (libs/python/corekinect/test/):
        from corekinect.validation.stage_defs import get_required_labels, Stage
        required = get_required_labels(Stage.FUOTA)
        # ["MFG_BASE", "MFG_BUMP", "FUT_DEBUG_A", ...]

    Test code (apps/validation/{product}/):
        from corekinect.validation.stage_defs import get_stage_build_defs, Stage
        defs = get_stage_build_defs(Stage.FUOTA)
        cfw_labels = [d.label for d in defs if d.produces_cfw]

Architecture:
    Each stage defines a list of StageBuildDef objects. Each def specifies:
    - label: unique identifier within the stage (e.g., "MFG_BASE")
    - fw_type: firmware type ("mfg", "app", "driver_test")
    - variant: build variant ("debug", "release", "mfg")
    - produces_hex: whether this build produces plaintext hex files
    - produces_cfw: whether this build produces encrypted CFW files
    - git_ref: which git ref to build from ("pr", "main", "merge")
    - is_version_bump: if True, this build starts BLOCKED until base completes
    - base_label: label of the build this depends on (for version bumps)
    - description: human-readable purpose of this build

    The label is the key that connects the build system, backend API,
    and test framework. The same label ("MFG_BASE") appears in:
    - BuildJob.matrixLabel in the database
    - StageAssets.by_label("MFG_BASE") in test code
    - Pipeline API response builds[].matrixLabel
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# Stage enum
# =============================================================================


class Stage(str, Enum):
    """Validation stage identifiers.

    Each stage has a specific purpose, hardware requirement, and timing budget.
    The stage name is used as the pipeline's matrix_mode and as directory
    names in product test packages.
    """

    SMOKE = "smoke"              # Stage 1: Software tests, no hardware
    SILICON = "silicon"          # Stage 2: Driver HW tests, dev kits
    INTEGRATION = "integration"  # Stage 3: Subsystem integration, product board
    NIGHTLY = "nightly"          # Stage 4: Comprehensive black-box validation
    FUOTA = "fuota"              # Stage 5: OTA firmware update, blocks merge


STAGE_NUMBERS: Dict[Stage, int] = {
    Stage.SMOKE: 1,
    Stage.SILICON: 2,
    Stage.INTEGRATION: 3,
    Stage.NIGHTLY: 4,
    Stage.FUOTA: 5,
}

STAGE_NAMES: Dict[int, str] = {
    1: "Smoke",
    2: "Silicon",
    3: "Integration",
    4: "Nightly",
    5: "FUOTA",
}


# =============================================================================
# Build definition
# =============================================================================


@dataclass(frozen=True)
class StageBuildDef:
    """Definition of a single firmware build within a validation stage.

    This is a recipe + artifact declaration. The build service uses
    fw_type/variant/git_ref to know HOW to build. The test framework
    uses produces_hex/produces_cfw to know WHAT artifacts to expect.

    Args:
        label: Matrix label, unique within a stage (e.g., "MFG_BASE").
        fw_type: Firmware type — "mfg", "app", or "driver_test".
        variant: Build variant — "debug", "release", or "mfg".
        produces_hex: Whether this build produces plaintext hex files
            for J-Link flashing.
        produces_cfw: Whether this build produces encrypted CFW files
            for FUOTA delivery.
        git_ref: Which git ref to build — "pr" (PR branch), "main"
            (mainline), or "merge" (post-merge).
        is_version_bump: If True, this build uses a bumped version
            number. Starts in BLOCKED status until base_label completes.
        base_label: Label of the build this depends on (for version
            bump linking). Required when is_version_bump=True.
        description: Human-readable explanation of why this build exists.
    """

    label: str
    fw_type: str
    variant: str
    produces_hex: bool = True
    produces_cfw: bool = False
    git_ref: str = "pr"
    is_version_bump: bool = False
    base_label: Optional[str] = None
    description: str = ""


# =============================================================================
# FUOTA stage — full OTA update cycle test (8 builds)
#
# Tests the complete FUOTA lifecycle:
#   1. Flash MFG firmware via J-Link (MFG_BASE)
#   2. Re-personalize with bumped MFG (MFG_BUMP)
#   3. FUOTA delivery: debug A→B transition (FUT_DEBUG_A → FUT_DEBUG_B)
#   4. FUOTA delivery: release A→B transition (FUT_RELEASE_A → FUT_RELEASE_B)
#   5. Regression: compare against mainline (MAIN_BASELINE)
#   6. Post-merge: verify merged code (MAIN_MERGED)
#
# Version bump builds (B variants, MFG_BUMP) start BLOCKED. When their
# base build completes, the build worker bumps the build number and
# compiles a second variant for the A→B FUOTA transition test.
# =============================================================================

_FUOTA_BUILDS: List[StageBuildDef] = [
    # Manufacturing firmware — flashed via J-Link before FUOTA tests
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", git_ref="pr",
        produces_hex=True, produces_cfw=True,
        description="Manufacturing firmware for J-Link flash + MFG-to-MFG FUOTA source",
    ),
    StageBuildDef(
        label="MFG_BUMP",
        fw_type="mfg", variant="mfg", git_ref="pr",
        produces_hex=True, produces_cfw=True,
        is_version_bump=True, base_label="MFG_BASE",
        description="Version-bumped MFG for MFG-to-MFG FUOTA target",
    ),

    # Debug firmware — FUOTA-delivered, tests A→B version transition
    StageBuildDef(
        label="FUT_DEBUG_A",
        fw_type="app", variant="debug", git_ref="pr",
        produces_hex=True, produces_cfw=True,
        description="Debug firmware version A — FUOTA source",
    ),
    StageBuildDef(
        label="FUT_DEBUG_B",
        fw_type="app", variant="debug", git_ref="pr",
        produces_hex=True, produces_cfw=True,
        is_version_bump=True, base_label="FUT_DEBUG_A",
        description="Debug firmware version B — FUOTA target (A→B transition)",
    ),

    # Release firmware — FUOTA-delivered, production-like build
    StageBuildDef(
        label="FUT_RELEASE_A",
        fw_type="app", variant="release", git_ref="pr",
        produces_hex=True, produces_cfw=True,
        description="Release firmware version A — FUOTA source",
    ),
    StageBuildDef(
        label="FUT_RELEASE_B",
        fw_type="app", variant="release", git_ref="pr",
        produces_hex=True, produces_cfw=True,
        is_version_bump=True, base_label="FUT_RELEASE_A",
        description="Release firmware version B — FUOTA target (A→B transition)",
    ),

    # Mainline builds — regression check
    StageBuildDef(
        label="MAIN_BASELINE",
        fw_type="app", variant="debug", git_ref="main",
        produces_hex=True, produces_cfw=False,
        description="Mainline debug build — regression baseline",
    ),
    StageBuildDef(
        label="MAIN_MERGED",
        fw_type="app", variant="debug", git_ref="merge",
        produces_hex=True, produces_cfw=False,
        description="Post-merge build — verify merged code compiles and boots",
    ),
]


# =============================================================================
# SMOKE stage — quick sanity check (2 builds)
# =============================================================================

_SMOKE_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Manufacturing firmware for basic boot + connectivity check",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Debug application firmware for smoke tests",
    ),
]


# =============================================================================
# SILICON stage — hardware validation (3 builds)
# =============================================================================

_SILICON_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Manufacturing firmware for hardware driver tests",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Debug firmware for driver-level hardware validation",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Release firmware — production-like behavior validation",
    ),
]


# =============================================================================
# INTEGRATION stage — end-to-end with cloud (4 builds)
# =============================================================================

_INTEGRATION_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Manufacturing firmware for integration boot + personalization",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Debug firmware for harness-instrumented integration tests",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", git_ref="pr",
        produces_hex=True, produces_cfw=False,
        description="Release firmware for production-path integration validation",
    ),
    StageBuildDef(
        label="MAIN_BASE",
        fw_type="app", variant="debug", git_ref="main",
        produces_hex=True, produces_cfw=False,
        description="Mainline debug build — regression baseline for integration",
    ),
]


# =============================================================================
# NIGHTLY stage — full regression suite (6 builds)
# =============================================================================

_NIGHTLY_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", git_ref="main",
        produces_hex=True, produces_cfw=True,
        description="Manufacturing firmware for nightly full-cycle validation",
    ),
    StageBuildDef(
        label="MFG_BUMP",
        fw_type="mfg", variant="mfg", git_ref="main",
        produces_hex=True, produces_cfw=True,
        is_version_bump=True, base_label="MFG_BASE",
        description="Version-bumped MFG for nightly FUOTA regression",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", git_ref="main",
        produces_hex=True, produces_cfw=False,
        description="Debug firmware for nightly comprehensive validation",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", git_ref="main",
        produces_hex=True, produces_cfw=False,
        description="Release firmware for nightly power + behavior validation",
    ),
    StageBuildDef(
        label="FUOTA_DEBUG_A",
        fw_type="app", variant="debug", git_ref="main",
        produces_hex=True, produces_cfw=True,
        description="Debug firmware version A — nightly FUOTA regression source",
    ),
    StageBuildDef(
        label="FUOTA_DEBUG_B",
        fw_type="app", variant="debug", git_ref="main",
        produces_hex=True, produces_cfw=True,
        is_version_bump=True, base_label="FUOTA_DEBUG_A",
        description="Debug firmware version B — nightly FUOTA regression target",
    ),
]


# =============================================================================
# Stage → builds mapping
# =============================================================================

_STAGE_BUILDS: Dict[Stage, List[StageBuildDef]] = {
    Stage.SMOKE: _SMOKE_BUILDS,
    Stage.SILICON: _SILICON_BUILDS,
    Stage.INTEGRATION: _INTEGRATION_BUILDS,
    Stage.NIGHTLY: _NIGHTLY_BUILDS,
    Stage.FUOTA: _FUOTA_BUILDS,
}


# =============================================================================
# Public API
# =============================================================================


def get_stage_build_defs(stage: Stage) -> List[StageBuildDef]:
    """Get the build definitions required for a validation stage.

    Returns an ordered list of StageBuildDef. Version bump builds
    (is_version_bump=True) start in BLOCKED status and unblock
    when their base build completes.

    Args:
        stage: Validation stage.

    Returns:
        List of build definitions for the stage.

    Raises:
        KeyError: If stage is not recognized.
    """
    if stage not in _STAGE_BUILDS:
        raise KeyError(
            f"Unknown stage: {stage}. Valid: {[s.value for s in Stage]}"
        )
    return list(_STAGE_BUILDS[stage])


def get_required_labels(stage: Stage) -> List[str]:
    """Get just the label names required for a stage.

    Convenience wrapper for test framework validation.

    Args:
        stage: Validation stage.

    Returns:
        Sorted list of label strings.
    """
    return sorted(d.label for d in get_stage_build_defs(stage))


def get_labels_with_cfw(stage: Stage) -> List[str]:
    """Get labels that produce encrypted CFW files.

    Used by the test framework to know which builds can be
    used for FUOTA delivery.

    Args:
        stage: Validation stage.

    Returns:
        Sorted list of labels that have produces_cfw=True.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if d.produces_cfw
    )


def get_labels_with_hex(stage: Stage) -> List[str]:
    """Get labels that produce plaintext hex files.

    Used by the test framework to know which builds can be
    flashed via J-Link.

    Args:
        stage: Validation stage.

    Returns:
        Sorted list of labels that have produces_hex=True.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if d.produces_hex
    )


def get_build_def(stage: Stage, label: str) -> Optional[StageBuildDef]:
    """Get a specific build definition by label.

    Args:
        stage: Validation stage.
        label: Build label (e.g., "MFG_BASE").

    Returns:
        The StageBuildDef, or None if not found.
    """
    for d in get_stage_build_defs(stage):
        if d.label == label:
            return d
    return None
