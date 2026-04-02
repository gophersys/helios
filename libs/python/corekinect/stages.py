"""Canonical stage and build definitions for the Concord validation platform.

THIS IS THE SINGLE SOURCE OF TRUTH for what firmware builds each
validation stage requires. Both the build service and the test framework
import from here. No other module should define stage build matrices.

Consumers:
    Build service (apps/backend/http-api/):
        from corekinect.stages import get_stage_build_defs, Stage
        defs = get_stage_build_defs(Stage.FUOTA)
        for d in defs:
            create_build_job(label=d.label, fw_type=d.fw_type, ...)

    Test framework (libs/python/corekinect/test/):
        from corekinect.stages import get_required_labels, Stage
        required = get_required_labels(Stage.FUOTA)
        # ["FUT_QUIET_A", "FUT_QUIET_B", "FUT_VERBOSE_A", ...]

    Test code (apps/validation/{product}/):
        from corekinect.stages import get_stage_build_defs, Stage
        defs = get_stage_build_defs(Stage.FUOTA)
        cfw_labels = [d.label for d in defs if d.produces_cfw]

Architecture:
    Each stage defines a list of StageBuildDef objects. Each def specifies:
    - label: unique identifier within the stage (e.g., "MFG_BASE")
    - fw_type: firmware type ("mfg", "app", "driver_test")
    - variant: build variant ("debug", "release", "mfg")
    - config_log: whether UART logging is enabled (CONFIG_LOG Kconfig)
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

CRITICAL — D-Flag Constraint:
    CoreCloud silently strips the D (debug) flag from FUOTA plan targets.
    A CFW uploaded as "109.0.8.0-BMD" creates a plan target "109.0.8.0-BM"
    (D stripped). The device requests "109.0.8.0-BM" but only the BMD image
    exists — FUOTA delivery NEVER starts.

    Therefore:
    - The D flag MUST NEVER be set in CFW track flags for FUOTA builds.
    - "Verbose" (CONFIG_LOG=y) and "quiet" (CONFIG_LOG=n) describe the
      BINARY configuration, NOT the CFW track flags.
    - All Alpha validation FUOTA builds use BM track (Bench + Manufacturing).
    - The `config_log` field controls the binary config independently of
      the CFW track.

    See: https://corekinect.atlassian.net/wiki/spaces/EN/pages/2704080902
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

    The ``config_log`` field controls whether UART logging is enabled
    in the built binary (CONFIG_LOG Kconfig). This is INDEPENDENT of
    the CFW track flags — a verbose build (config_log=True) can and
    should use a non-debug CFW track (e.g., BM instead of BMD).

    See the module docstring for the D-flag constraint explanation.

    Args:
        label: Matrix label, unique within a stage (e.g., "MFG_BASE").
        fw_type: Firmware type — "mfg", "app", or "driver_test".
        variant: Build variant — controls binary configuration.
            "mfg" = manufacturing firmware with mfg shell.
            "debug" = application firmware with CONFIG_LOG=y.
            "release" = application firmware with CONFIG_LOG=n.
        config_log: Whether UART logging is enabled (CONFIG_LOG=y).
            True = "verbose" — UART boot logs visible, version
            detectable via BootVersionDetector.
            False = "quiet" — no UART output, verification via
            power current or cloud check-in only.
        produces_hex: Whether this build produces plaintext hex files
            for J-Link flashing.
        produces_cfw: Whether this build produces encrypted CFW files
            for FUOTA delivery. MUST NOT use D-flag in track.
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
    config_log: bool = True
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
#   2. MFG-to-MFG FUOTA (MFG_BASE → MFG_BUMP)
#   3. MFG-to-App FUOTA with UART (MFG_BASE → FUT_VERBOSE_A)
#   4. App-to-App FUOTA with UART (FUT_VERBOSE_A → FUT_VERBOSE_B)
#   5. MFG-to-App FUOTA without UART (MFG_BASE → FUT_QUIET_A)
#   6. App-to-App FUOTA without UART (FUT_QUIET_A → FUT_QUIET_B)
#
# "Verbose" = CONFIG_LOG=y (UART boot logs visible for version verification)
# "Quiet" = CONFIG_LOG=n (no UART, verification via current or cloud only)
#
# ALL builds use BM track (Bench + Manufacturing). The D-flag is NEVER
# set because CoreCloud strips it, causing version mismatch. See module
# docstring for details.
#
# Version bump builds (B variants, MFG_BUMP) start BLOCKED. When their
# base build completes, the build worker bumps the build number and
# compiles a second variant for the A→B FUOTA transition test.
# =============================================================================

_FUOTA_BUILDS: List[StageBuildDef] = [
    # ── Manufacturing firmware ──
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="Manufacturing firmware — J-Link flash + MFG-to-MFG FUOTA source",
    ),
    StageBuildDef(
        label="MFG_BUMP",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="pr",
        is_version_bump=True, base_label="MFG_BASE",
        description="Version-bumped MFG — MFG-to-MFG FUOTA target",
    ),

    # ── Verbose firmware (CONFIG_LOG=y, UART visible) ──
    StageBuildDef(
        label="FUT_VERBOSE_A",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="Verbose app firmware A — FUOTA source, UART verification",
    ),
    StageBuildDef(
        label="FUT_VERBOSE_B",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="pr",
        is_version_bump=True, base_label="FUT_VERBOSE_A",
        description="Verbose app firmware B — FUOTA target (A→B), UART verification",
    ),

    # ── Quiet firmware (CONFIG_LOG=n, no UART) ──
    StageBuildDef(
        label="FUT_QUIET_A",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="Quiet app firmware A — FUOTA source, cloud-only verification",
    ),
    StageBuildDef(
        label="FUT_QUIET_B",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=True, git_ref="pr",
        is_version_bump=True, base_label="FUT_QUIET_A",
        description="Quiet app firmware B — FUOTA target (A→B), cloud-only verification",
    ),

    # ── Mainline regression builds (hex only, no FUOTA) ──
    StageBuildDef(
        label="MAIN_BASELINE",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Mainline debug build — regression baseline (boot check only)",
    ),
    StageBuildDef(
        label="MAIN_MERGED",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="merge",
        description="Post-merge build — verify merged code compiles and boots",
    ),
]


# =============================================================================
# SMOKE stage — quick sanity check (2 builds)
# =============================================================================

_SMOKE_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Manufacturing firmware for basic boot + connectivity check",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Debug application firmware for smoke tests",
    ),
]


# =============================================================================
# SILICON stage — hardware validation (3 builds)
# =============================================================================

_SILICON_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Manufacturing firmware for hardware driver tests",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Debug firmware for driver-level hardware validation",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Release firmware — production-like behavior validation",
    ),
]


# =============================================================================
# INTEGRATION stage — end-to-end with cloud (4 builds)
# =============================================================================

_INTEGRATION_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Manufacturing firmware for integration boot + personalization",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Debug firmware for harness-instrumented integration tests",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="pr",
        description="Release firmware for production-path integration validation",
    ),
    StageBuildDef(
        label="MAIN_BASE",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Mainline debug build — regression baseline for integration",
    ),
]


# =============================================================================
# NIGHTLY stage — full regression suite (6 builds)
# =============================================================================

_NIGHTLY_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        description="Manufacturing firmware for nightly full-cycle validation",
    ),
    StageBuildDef(
        label="MFG_BUMP",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        is_version_bump=True, base_label="MFG_BASE",
        description="Version-bumped MFG for nightly FUOTA regression",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Debug firmware for nightly comprehensive validation",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Release firmware for nightly power + behavior validation",
    ),
    StageBuildDef(
        label="FUOTA_VERBOSE_A",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        description="Verbose firmware A — nightly FUOTA regression source",
    ),
    StageBuildDef(
        label="FUOTA_VERBOSE_B",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        is_version_bump=True, base_label="FUOTA_VERBOSE_A",
        description="Verbose firmware B — nightly FUOTA regression target",
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
# Stage → required capabilities
#
# Minimum capabilities a fixture MUST have to run a stage. The backend
# uses this for scheduling — it won't assign a fixture that lacks
# critical capabilities unless strict_mode is disabled.
#
# Individual tests within a stage may require additional capabilities
# beyond the stage minimum (e.g., a GNSS test needs GNSS_SIMULATOR).
# Those tests skip gracefully if the extra capability is missing.
#
# In strict_mode, the backend waits for a fixture with ALL capabilities
# listed in the stage's full_capabilities set (stage minimum + all
# test-level requirements). In normal mode, it assigns the best
# available fixture and lets tests skip what they can't run.
# =============================================================================

_STAGE_CAPABILITIES: Dict[Stage, List[str]] = {
    # Smoke: just needs MTIB connectivity (power + basic I/O)
    Stage.SMOKE: ["power"],

    # Silicon: needs GPIO access for driver testing
    Stage.SILICON: ["power", "button", "jlink"],

    # Integration: needs harness connectivity + basic peripherals
    Stage.INTEGRATION: ["power", "button", "jlink"],

    # Nightly: comprehensive — needs most fixture capabilities
    # Individual tests skip if specific capabilities are missing
    Stage.NIGHTLY: ["power", "button", "peltier"],

    # FUOTA: needs J-Link for initial flash + power for boot verification
    Stage.FUOTA: ["power", "jlink"],
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
    used for FUOTA delivery. All returned CFWs MUST use
    non-debug track flags (no D-flag) per the CoreCloud constraint.

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


def get_verbose_labels(stage: Stage) -> List[str]:
    """Get labels that have UART logging enabled (config_log=True).

    These builds produce UART boot output that can be captured
    by BootVersionDetector for version verification.

    Args:
        stage: Validation stage.

    Returns:
        Sorted list of verbose build labels.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if d.config_log
    )


def get_quiet_labels(stage: Stage) -> List[str]:
    """Get labels that have UART logging disabled (config_log=False).

    These builds produce no UART output. Verification must use
    power current measurement or cloud check-in instead.

    Args:
        stage: Validation stage.

    Returns:
        Sorted list of quiet build labels.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if not d.config_log
    )


def get_stage_capabilities(stage: Stage) -> List[str]:
    """Get minimum required capability names for a stage.

    The backend uses this for fixture scheduling. A fixture must have
    at least these capabilities to run the stage. Individual tests may
    require additional capabilities and will skip gracefully.

    Args:
        stage: Validation stage.

    Returns:
        List of capability name strings (matching Capability enum values).
    """
    return list(_STAGE_CAPABILITIES.get(stage, []))
