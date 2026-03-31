"""Validation stage definitions.

The Concord platform defines 5 validation stages, each with
a specific purpose, hardware requirement, and timing budget.

Usage:
    from corekinect.test.stages import Stage, STAGE_NUMBERS

    if config.stage == Stage.FUOTA:
        # FUOTA-specific logic
"""

from enum import Enum
from typing import Dict


class Stage(str, Enum):
    """Validation stage identifiers."""

    SMOKE = "smoke"  # Stage 1: Software tests on native_sim, no hardware
    SILICON = "silicon"  # Stage 2: Driver HW tests on dev kits + MTIB
    INTEGRATION = "integration"  # Stage 3: Subsystem integration, product board
    NIGHTLY = "nightly"  # Stage 4: Comprehensive black-box validation
    FUOTA = "fuota"  # Stage 5: OTA firmware update verification, blocks merge


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
