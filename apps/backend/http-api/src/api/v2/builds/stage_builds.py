"""Stage build definitions — re-exports from shared module.

The canonical definitions live at libs/python/corekinect/validation/stage_defs.py.
This module re-exports them for backward compatibility within the http-api.
"""

from corekinect.stages import (
    Stage,
    StageBuildDef,
    get_stage_build_defs,
    get_required_labels,
)

# Backward compat alias — old code uses ValidationStage
ValidationStage = Stage

__all__ = [
    "Stage",
    "ValidationStage",
    "StageBuildDef",
    "get_stage_build_defs",
    "get_required_labels",
]
