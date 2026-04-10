"""Validation stage definitions and DEFAULT build matrices.

Stage enum and names are canonical — used everywhere.
Build matrices (_STAGE_BUILDS) are DEFAULT TEMPLATES — copied to the
DB (StageBuildMatrix) when a stage is first enabled. After that,
the DB is the source of truth. Edit via the API or UI, not here.

To change the default matrix for NEW stage enablements, edit here.
To change an existing product's matrix, use the API.

    from corekinect.stages import get_stage_build_defs, Stage
    defs = get_stage_build_defs(Stage.FUOTA)
    cfw_labels = [d.label for d in defs if d.produces_cfw]

The label string ("MFG_BASE", "FUT_VERBOSE_A", etc.) is the key that
connects the build system, backend API, and test framework.

CRITICAL — D-Flag Constraint:
    CoreCloud silently strips the D (debug) flag from FUOTA plan targets.
    A CFW uploaded as "109.0.8.0-BMD" creates a plan target "109.0.8.0-BM"
    (D stripped). The device requests "109.0.8.0-BM" but only the BMD image
    exists — FUOTA delivery NEVER starts.

    Therefore: the D flag MUST NEVER be set in CFW track flags for FUOTA
    builds. "Verbose" (CONFIG_LOG=y) and "quiet" (CONFIG_LOG=n) describe
    the binary config, NOT the CFW track flags. All Alpha FUOTA builds
    use BM track. The ``config_log`` field is independent of the track.

    See: https://corekinect.atlassian.net/wiki/spaces/EN/pages/2704080902
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# Stage enum
# =============================================================================


class StageType(str, Enum):
    """Top-level stage type."""
    VALIDATION = "VALIDATION"
    MANUFACTURING = "MANUFACTURING"


class Stage(str, Enum):
    """Stage identifiers. Used as directory names in test packages."""

    # Validation stages (order 1-5)
    SMOKE = "smoke"
    DRIVER = "driver"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    FUOTA = "fuota"

    # Manufacturing (order 1)
    MANUFACTURING = "manufacturing"


STAGE_NUMBERS: Dict[Stage, int] = {
    Stage.SMOKE: 1,
    Stage.DRIVER: 2,
    Stage.INTEGRATION: 3,
    Stage.REGRESSION: 4,
    Stage.FUOTA: 5,
    Stage.MANUFACTURING: 1,
}

STAGE_TYPES: Dict[Stage, StageType] = {
    Stage.SMOKE: StageType.VALIDATION,
    Stage.DRIVER: StageType.VALIDATION,
    Stage.INTEGRATION: StageType.VALIDATION,
    Stage.REGRESSION: StageType.VALIDATION,
    Stage.FUOTA: StageType.VALIDATION,
    Stage.MANUFACTURING: StageType.MANUFACTURING,
}

STAGE_NAMES: Dict[int, str] = {
    1: "Smoke",
    2: "Driver",
    3: "Integration",
    4: "Regression",
    5: "FUOTA",
}


# =============================================================================
# Build definition
# =============================================================================


@dataclass(frozen=True)
class StageBuildDef:
    """A single firmware build recipe within a validation stage.

    The build service reads fw_type/variant/git_ref to know HOW to build.
    The test framework reads produces_hex/produces_cfw to know WHAT
    artifacts to expect.

    ``config_log`` controls CONFIG_LOG (UART logging) independently of
    CFW track flags — a verbose build (config_log=True) still uses a
    non-debug track (BM, not BMD). See module docstring for why.

    Args:
        variant: "mfg" (mfg shell), "debug" (CONFIG_LOG=y), or
            "release" (CONFIG_LOG=n).
        config_log: True = verbose (UART boot logs visible).
            False = quiet (verify via power current or cloud only).
        produces_cfw: MUST NOT use D-flag in track.
        is_version_bump: Starts BLOCKED until base_label completes.
        base_label: Required when is_version_bump=True.
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
# DRIVER stage — hardware validation (3 builds)
# =============================================================================

_DRIVER_BUILDS: List[StageBuildDef] = [
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
# REGRESSION stage — full regression suite (6 builds)
# =============================================================================

_REGRESSION_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_BASE",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        description="Manufacturing firmware for regression full-cycle validation",
    ),
    StageBuildDef(
        label="MFG_BUMP",
        fw_type="mfg", variant="mfg", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        is_version_bump=True, base_label="MFG_BASE",
        description="Version-bumped MFG for regression FUOTA",
    ),
    StageBuildDef(
        label="APP_DEBUG",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Debug firmware for regression comprehensive validation",
    ),
    StageBuildDef(
        label="APP_RELEASE",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Release firmware for regression power + behavior validation",
    ),
    StageBuildDef(
        label="FUOTA_VERBOSE_A",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        description="Verbose firmware A — regression FUOTA source",
    ),
    StageBuildDef(
        label="FUOTA_VERBOSE_B",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=True, git_ref="main",
        is_version_bump=True, base_label="FUOTA_VERBOSE_A",
        description="Verbose firmware B — regression FUOTA target",
    ),
]


# =============================================================================
# MANUFACTURING stage — production line test (1 build)
#
# Firmware flashed via J-Link during manufacturing POST. A single MFG_BASE
# build produces both app (nRF52840) and comms (nRF9151) hex targets.
# Tests: electrical (power rail validation), fw_flash (J-Link + AP protect),
# post (boot, chip IDs, BMS, charger, GPS, modem, personalization, IPC rekey).
# =============================================================================

_MANUFACTURING_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="MFG_APP_DEBUG",
        fw_type="app", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Application processor firmware — debug variant (nRF52840)",
    ),
    StageBuildDef(
        label="MFG_APP_RELEASE",
        fw_type="app", variant="release", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Application processor firmware — release variant (nRF52840)",
    ),
    StageBuildDef(
        label="MFG_COMMS_DEBUG",
        fw_type="comms", variant="debug", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Communications processor firmware — debug variant (nRF9151)",
    ),
    StageBuildDef(
        label="MFG_COMMS_RELEASE",
        fw_type="comms", variant="release", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Communications processor firmware — release variant (nRF9151)",
    ),
    StageBuildDef(
        label="MODEM_FW",
        fw_type="modem", variant="release", config_log=False,
        produces_hex=False, produces_cfw=False, git_ref="main",
        description="Modem firmware package (.zip) for nRF91 series",
    ),
]


# =============================================================================
# Stage → builds mapping
# =============================================================================

_STAGE_BUILDS: Dict[Stage, List[StageBuildDef]] = {
    Stage.SMOKE: _SMOKE_BUILDS,
    Stage.DRIVER: _DRIVER_BUILDS,
    Stage.INTEGRATION: _INTEGRATION_BUILDS,
    Stage.REGRESSION: _REGRESSION_BUILDS,
    Stage.FUOTA: _FUOTA_BUILDS,
    Stage.MANUFACTURING: _MANUFACTURING_BUILDS,
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

    # Driver: needs GPIO access for driver testing
    Stage.DRIVER: ["power", "button", "jlink"],

    # Integration: needs harness connectivity + basic peripherals
    Stage.INTEGRATION: ["power", "button", "jlink"],

    # Regression: comprehensive — needs most fixture capabilities
    # Individual tests skip if specific capabilities are missing
    Stage.REGRESSION: ["power", "button", "peltier"],

    # FUOTA: needs J-Link for initial flash + power for boot verification
    Stage.FUOTA: ["power", "jlink"],

    # Manufacturing: needs J-Link for firmware flash + power for boot/electrical
    Stage.MANUFACTURING: ["power", "jlink"],
}


# =============================================================================
# Public API
# =============================================================================


def get_stage_build_defs(stage: Stage) -> List[StageBuildDef]:
    """Return DEFAULT build definitions for a stage.

    These are templates for seeding new stage configs. The runtime
    build matrix comes from the StageBuildMatrix DB table, not here.

    Version bump builds start BLOCKED and unblock when their base
    build completes.

    Raises:
        KeyError: If stage is not recognized.
    """
    if stage not in _STAGE_BUILDS:
        raise KeyError(
            f"Unknown stage: {stage}. Valid: {[s.value for s in Stage]}"
        )
    return list(_STAGE_BUILDS[stage])


def get_required_labels(stage: Stage) -> List[str]:
    """Return sorted label names required for a stage."""
    return sorted(d.label for d in get_stage_build_defs(stage))


def get_labels_with_cfw(stage: Stage) -> List[str]:
    """Return labels that produce encrypted CFW files (for FUOTA delivery).

    All returned CFWs use non-debug track flags per the D-flag constraint.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if d.produces_cfw
    )


def get_labels_with_hex(stage: Stage) -> List[str]:
    """Return labels that produce plaintext hex files (for J-Link flashing)."""
    return sorted(
        d.label for d in get_stage_build_defs(stage) if d.produces_hex
    )


def get_build_def(stage: Stage, label: str) -> Optional[StageBuildDef]:
    """Return a specific build definition by label, or None if not found."""
    for d in get_stage_build_defs(stage):
        if d.label == label:
            return d
    return None


def get_verbose_labels(stage: Stage) -> List[str]:
    """Return labels with UART logging enabled (config_log=True).

    These builds emit UART boot output that BootVersionDetector can
    capture for version verification.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if d.config_log
    )


def get_quiet_labels(stage: Stage) -> List[str]:
    """Return labels with UART logging disabled (config_log=False).

    Verification must use power current or cloud check-in instead.
    """
    return sorted(
        d.label for d in get_stage_build_defs(stage) if not d.config_log
    )


def get_stage_capabilities(stage: Stage) -> List[str]:
    """Return minimum fixture capabilities required for a stage.

    The backend uses this for fixture scheduling. Individual tests may
    require extra capabilities and skip gracefully if missing.
    """
    return list(_STAGE_CAPABILITIES.get(stage, []))
