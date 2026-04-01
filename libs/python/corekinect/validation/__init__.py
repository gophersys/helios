"""Shared validation platform concepts.

This package defines the canonical stage and build definitions used by
both the build service (backend) and the test framework. It is the
single source of truth for what firmware builds each validation stage
requires and what artifacts each build produces.

Consumers:
    - Build service (apps/backend/http-api/) — creates BuildJobs from stage defs
    - Test framework (libs/python/corekinect/test/) — validates assets match defs
    - CLI tooling (cktest) — scaffolds test packages from stage defs
"""

from .stage_defs import (
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
    "get_verbose_labels",
]
