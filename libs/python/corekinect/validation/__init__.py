"""Shared validation platform concepts — re-exports from top-level.

The canonical definitions now live at ``corekinect.stages``.
This package re-exports them for backward compatibility so existing
imports like ``from corekinect.validation import Stage`` still work.

Consumers:
    - Build service (apps/backend/http-api/) -- creates BuildJobs from stage defs
    - Test framework (libs/python/corekinect/test/) -- validates assets match defs
    - CLI tooling (cktest) -- scaffolds test packages from stage defs
"""

from corekinect.stages import (  # noqa: F401
    Stage,
    StageBuildDef,
    STAGE_NUMBERS,
    STAGE_NAMES,
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
    "STAGE_NUMBERS",
    "STAGE_NAMES",
    "get_build_def",
    "get_labels_with_cfw",
    "get_labels_with_hex",
    "get_quiet_labels",
    "get_required_labels",
    "get_stage_build_defs",
    "get_stage_capabilities",
    "get_verbose_labels",
]
