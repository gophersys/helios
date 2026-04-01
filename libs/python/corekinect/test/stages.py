"""Validation stage definitions — re-exports from shared module.

The canonical definitions live in ``corekinect.validation.stage_defs``.
This module re-exports them for backward compatibility so existing
imports like ``from corekinect.test.stages import Stage`` still work.

Usage:
    from corekinect.test.stages import Stage, STAGE_NUMBERS

    if config.stage == Stage.FUOTA:
        # FUOTA-specific logic
"""

# Re-export everything from the shared source of truth
from corekinect.validation.stage_defs import (  # noqa: F401
    Stage,
    STAGE_NAMES,
    STAGE_NUMBERS,
    StageBuildDef,
    get_build_def,
    get_labels_with_cfw,
    get_labels_with_hex,
    get_required_labels,
    get_stage_build_defs,
)
