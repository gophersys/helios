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

The label string ("mfg_base", "fut_verbose_a", etc.) is the key that
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
    processor: str = ""
    config_log: bool = True
    produces_hex: bool = True
    produces_cfw: bool = False
    git_ref: str = "pr"
    is_version_bump: bool = False
    base_label: Optional[str] = None
    description: str = ""
    filename_pattern: str = ""


# =============================================================================
# FUOTA stage — full OTA update cycle test (7 builds)
#
# Tests the complete FUOTA lifecycle across both processors:
#   1. Flash app debug A, FUOTA to app debug B (verbose, UART verification)
#   2. Flash app release A, FUOTA to app release B (quiet, cloud verification)
#   3. Flash comms debug A, FUOTA to comms debug B
#
# ALL builds use BM track (Bench + Manufacturing). The D-flag is NEVER
# set because CoreCloud strips it, causing version mismatch. See module
# docstring for details.
# =============================================================================

_FUOTA_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="fut_app_base_a", fw_type="app", variant="debug", processor="nrf52840",
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="From version — verbose logging",
    ),
    StageBuildDef(
        label="fut_app_base_b", fw_type="app", variant="debug", processor="nrf52840",
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="To version — verbose logging",
    ),
    StageBuildDef(
        label="fut_app_quiet_a", fw_type="app", variant="release", processor="nrf52840",
        produces_hex=True, produces_cfw=True, config_log=False, git_ref="pr",
        description="From version — no logging",
    ),
    StageBuildDef(
        label="fut_app_quiet_b", fw_type="app", variant="release", processor="nrf52840",
        produces_hex=True, produces_cfw=True, config_log=False, git_ref="pr",
        description="To version — no logging",
    ),
    StageBuildDef(
        label="fut_comms_base_a", fw_type="comms", variant="debug", processor="nrf9151",
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="Comms from version",
    ),
    StageBuildDef(
        label="fut_comms_base_b", fw_type="comms", variant="debug", processor="nrf9151",
        produces_hex=True, produces_cfw=True, git_ref="pr",
        description="Comms to version",
    ),
    StageBuildDef(
        label="modem_fw", fw_type="modem", variant="release", processor="nrf9151",
        produces_hex=False, produces_cfw=False, config_log=False, git_ref="main",
        description="Modem firmware (selected separately)",
    ),
]


# =============================================================================
# SMOKE stage — quick sanity check (3 builds)
# =============================================================================

_SMOKE_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="smoke_app_debug", fw_type="app", variant="debug", processor="nrf52840",
        produces_hex=True, git_ref="pr", description="App processor — debug",
    ),
    StageBuildDef(
        label="smoke_comms_debug", fw_type="comms", variant="debug", processor="nrf9151",
        produces_hex=True, git_ref="pr", description="Comms processor — debug",
    ),
    StageBuildDef(
        label="modem_fw", fw_type="modem", variant="release", processor="nrf9151",
        produces_hex=False, produces_cfw=False, config_log=False, git_ref="main",
        description="Modem firmware (selected separately)",
    ),
]


# =============================================================================
# DRIVER stage — hardware validation (5 builds)
# =============================================================================

_DRIVER_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="driver_app_debug", fw_type="app", variant="debug", processor="nrf52840",
        produces_hex=True, git_ref="pr",
    ),
    StageBuildDef(
        label="driver_app_release", fw_type="app", variant="release", processor="nrf52840",
        produces_hex=True, config_log=False, git_ref="pr",
    ),
    StageBuildDef(
        label="driver_comms_debug", fw_type="comms", variant="debug", processor="nrf9151",
        produces_hex=True, git_ref="pr",
    ),
    StageBuildDef(
        label="driver_comms_release", fw_type="comms", variant="release", processor="nrf9151",
        produces_hex=True, config_log=False, git_ref="pr",
    ),
    StageBuildDef(
        label="modem_fw", fw_type="modem", variant="release", processor="nrf9151",
        produces_hex=False, produces_cfw=False, config_log=False, git_ref="main",
        description="Modem firmware (selected separately)",
    ),
]


# =============================================================================
# INTEGRATION stage — end-to-end with cloud (5 builds)
# =============================================================================

_INTEGRATION_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="int_app_debug", fw_type="app", variant="debug", processor="nrf52840",
        produces_hex=True, git_ref="pr",
    ),
    StageBuildDef(
        label="int_app_release", fw_type="app", variant="release", processor="nrf52840",
        produces_hex=True, config_log=False, git_ref="pr",
    ),
    StageBuildDef(
        label="int_comms_debug", fw_type="comms", variant="debug", processor="nrf9151",
        produces_hex=True, git_ref="pr",
    ),
    StageBuildDef(
        label="int_comms_release", fw_type="comms", variant="release", processor="nrf9151",
        produces_hex=True, config_log=False, git_ref="pr",
    ),
    StageBuildDef(
        label="modem_fw", fw_type="modem", variant="release", processor="nrf9151",
        produces_hex=False, produces_cfw=False, config_log=False, git_ref="main",
        description="Modem firmware (selected separately)",
    ),
]


# =============================================================================
# REGRESSION stage — full regression suite (5 builds)
# =============================================================================

_REGRESSION_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="reg_app_debug", fw_type="app", variant="debug", processor="nrf52840",
        produces_hex=True, produces_cfw=True, git_ref="main",
    ),
    StageBuildDef(
        label="reg_app_release", fw_type="app", variant="release", processor="nrf52840",
        produces_hex=True, produces_cfw=True, config_log=False, git_ref="main",
    ),
    StageBuildDef(
        label="reg_comms_debug", fw_type="comms", variant="debug", processor="nrf9151",
        produces_hex=True, produces_cfw=True, git_ref="main",
    ),
    StageBuildDef(
        label="reg_comms_release", fw_type="comms", variant="release", processor="nrf9151",
        produces_hex=True, produces_cfw=True, config_log=False, git_ref="main",
    ),
    StageBuildDef(
        label="modem_fw", fw_type="modem", variant="release", processor="nrf9151",
        produces_hex=False, produces_cfw=False, config_log=False, git_ref="main",
        description="Modem firmware (selected separately)",
    ),
]


# =============================================================================
# MANUFACTURING stage — production line test (1 build)
#
# Firmware flashed via J-Link during manufacturing POST. A single mfg_base
# build produces both app (nRF52840) and comms (nRF9151) hex targets.
# Tests: electrical (power rail validation), fw_flash (J-Link + AP protect),
# post (boot, chip IDs, BMS, charger, GPS, modem, personalization, IPC rekey).
# =============================================================================

_MANUFACTURING_BUILDS: List[StageBuildDef] = [
    StageBuildDef(
        label="mfg_app_debug",
        fw_type="app", variant="debug", processor="nrf52840", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Application processor firmware — debug variant (nRF52840)",
    ),
    StageBuildDef(
        label="mfg_app_release",
        fw_type="app", variant="release", processor="nrf52840", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Application processor firmware — release variant (nRF52840)",
    ),
    StageBuildDef(
        label="mfg_comms_debug",
        fw_type="comms", variant="debug", processor="nrf9151", config_log=True,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Communications processor firmware — debug variant (nRF9151)",
    ),
    StageBuildDef(
        label="mfg_comms_release",
        fw_type="comms", variant="release", processor="nrf9151", config_log=False,
        produces_hex=True, produces_cfw=False, git_ref="main",
        description="Communications processor firmware — release variant (nRF9151)",
    ),
    StageBuildDef(
        label="modem_fw",
        fw_type="modem", variant="release", processor="nrf9151", config_log=False,
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


