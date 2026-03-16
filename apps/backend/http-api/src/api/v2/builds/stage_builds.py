"""Stage build definitions — defines what firmware builds each validation stage needs.

Each validation stage requires specific firmware variants to be built before
testing can begin. This module is the single source of truth for those requirements.

The pipeline creator (pipelines.py) calls get_stage_build_defs(stage) and uses
the returned StageBuildDef list to create BuildJob records in the database.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ValidationStage(str, Enum):
    """Validation pipeline stages."""
    SMOKE = "smoke"
    SILICON = "silicon"
    INTEGRATION = "integration"
    NIGHTLY = "nightly"
    FUOTA = "fuota"


@dataclass
class StageBuildDef:
    """Definition of a single firmware build within a validation stage.

    Attributes:
        label: Matrix label (e.g. MFG_BASE, FUT_DEBUG_A). Unique within a stage.
        fw_type: Firmware type — "mfg" (manufacturing), "app" (production), "driver_test".
        variant: Build variant — "debug", "release", "mfg".
        git_ref: Which git ref to build — "pr" (PR branch), "main" (mainline), "merge" (merged).
        is_version_bump: If True, this build uses a bumped version (starts BLOCKED until base completes).
        base_label: Label of the base build this depends on (for version bump linking).
    """
    label: str
    fw_type: str
    variant: str
    git_ref: str = "pr"
    is_version_bump: bool = False
    base_label: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────
#  FUOTA stage — full OTA update cycle test
#
#  8 builds total:
#    MFG_BASE / MFG_BUMP        — Manufacturing firmware (flash via J-Link)
#    FUT_DEBUG_A / FUT_DEBUG_B   — Debug app firmware (FUOTA delivery, A→B transition)
#    FUT_RELEASE_A / FUT_RELEASE_B — Release app firmware (FUOTA delivery, A→B transition)
#    MAIN_BASELINE               — Mainline app firmware (regression baseline)
#    MAIN_MERGED                 — Merged PR firmware (post-merge verification)
#
#  Version bump builds (B variants, MFG_BUMP) start BLOCKED. When their
#  base build completes, the build worker bumps the build number and
#  compiles a second variant for the A→B FUOTA transition test.
# ──────────────────────────────────────────────────────────────────────
_FUOTA_BUILDS: List[StageBuildDef] = [
    # Manufacturing firmware — flashed via J-Link before FUOTA tests
    StageBuildDef(label="MFG_BASE",       fw_type="mfg", variant="mfg",     git_ref="pr"),
    StageBuildDef(label="MFG_BUMP",       fw_type="mfg", variant="mfg",     git_ref="pr",
                  is_version_bump=True, base_label="MFG_BASE"),

    # Debug firmware — FUOTA-delivered, tests A→B version transition
    StageBuildDef(label="FUT_DEBUG_A",    fw_type="app", variant="debug",   git_ref="pr"),
    StageBuildDef(label="FUT_DEBUG_B",    fw_type="app", variant="debug",   git_ref="pr",
                  is_version_bump=True, base_label="FUT_DEBUG_A"),

    # Release firmware — FUOTA-delivered, production-like build
    StageBuildDef(label="FUT_RELEASE_A",  fw_type="app", variant="release", git_ref="pr"),
    StageBuildDef(label="FUT_RELEASE_B",  fw_type="app", variant="release", git_ref="pr",
                  is_version_bump=True, base_label="FUT_RELEASE_A"),

    # Mainline builds — regression check
    StageBuildDef(label="MAIN_BASELINE",  fw_type="app", variant="debug",   git_ref="main"),
    StageBuildDef(label="MAIN_MERGED",    fw_type="app", variant="debug",   git_ref="merge"),
]

# ──────────────────────────────────────────────────────────────────────
#  SMOKE stage — quick sanity check (boot + basic comms)
# ──────────────────────────────────────────────────────────────────────
_SMOKE_BUILDS: List[StageBuildDef] = [
    StageBuildDef(label="MFG_BASE",   fw_type="mfg", variant="mfg",   git_ref="pr"),
    StageBuildDef(label="APP_DEBUG",  fw_type="app", variant="debug", git_ref="pr"),
]

# ──────────────────────────────────────────────────────────────────────
#  SILICON stage — hardware validation (power, peripherals, sensors)
# ──────────────────────────────────────────────────────────────────────
_SILICON_BUILDS: List[StageBuildDef] = [
    StageBuildDef(label="MFG_BASE",    fw_type="mfg", variant="mfg",   git_ref="pr"),
    StageBuildDef(label="APP_DEBUG",   fw_type="app", variant="debug", git_ref="pr"),
    StageBuildDef(label="APP_RELEASE", fw_type="app", variant="release", git_ref="pr"),
]

# ──────────────────────────────────────────────────────────────────────
#  INTEGRATION stage — end-to-end with cloud connectivity
# ──────────────────────────────────────────────────────────────────────
_INTEGRATION_BUILDS: List[StageBuildDef] = [
    StageBuildDef(label="MFG_BASE",    fw_type="mfg", variant="mfg",     git_ref="pr"),
    StageBuildDef(label="APP_DEBUG",   fw_type="app", variant="debug",   git_ref="pr"),
    StageBuildDef(label="APP_RELEASE", fw_type="app", variant="release", git_ref="pr"),
    StageBuildDef(label="MAIN_BASE",   fw_type="app", variant="debug",   git_ref="main"),
]

# ──────────────────────────────────────────────────────────────────────
#  NIGHTLY stage — full regression suite
# ──────────────────────────────────────────────────────────────────────
_NIGHTLY_BUILDS: List[StageBuildDef] = [
    StageBuildDef(label="MFG_BASE",       fw_type="mfg", variant="mfg",     git_ref="main"),
    StageBuildDef(label="MFG_BUMP",       fw_type="mfg", variant="mfg",     git_ref="main",
                  is_version_bump=True, base_label="MFG_BASE"),
    StageBuildDef(label="APP_DEBUG",      fw_type="app", variant="debug",   git_ref="main"),
    StageBuildDef(label="APP_RELEASE",    fw_type="app", variant="release", git_ref="main"),
    StageBuildDef(label="FUOTA_DEBUG_A",  fw_type="app", variant="debug",   git_ref="main"),
    StageBuildDef(label="FUOTA_DEBUG_B",  fw_type="app", variant="debug",   git_ref="main",
                  is_version_bump=True, base_label="FUOTA_DEBUG_A"),
]


_STAGE_BUILDS = {
    ValidationStage.SMOKE: _SMOKE_BUILDS,
    ValidationStage.SILICON: _SILICON_BUILDS,
    ValidationStage.INTEGRATION: _INTEGRATION_BUILDS,
    ValidationStage.NIGHTLY: _NIGHTLY_BUILDS,
    ValidationStage.FUOTA: _FUOTA_BUILDS,
}


def get_stage_build_defs(stage: ValidationStage) -> List[StageBuildDef]:
    """Get the build definitions required for a validation stage.

    Returns an ordered list of StageBuildDef that the pipeline should create.
    Version bump builds (is_version_bump=True) will start in BLOCKED status
    and unblock when their base build completes.
    """
    return list(_STAGE_BUILDS.get(stage, []))
