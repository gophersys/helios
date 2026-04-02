"""Stage and build definitions — re-exports from top-level module.

The canonical definitions now live at ``corekinect.stages``.
This module re-exports them for backward compatibility so existing
imports like ``from corekinect.validation.stage_defs import Stage``
still work.

Usage:
    from corekinect.validation.stage_defs import Stage, get_stage_build_defs

    defs = get_stage_build_defs(Stage.FUOTA)
"""

# Re-export everything from the canonical location
from corekinect.stages import (  # noqa: F401
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

__all__ = [
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
]
