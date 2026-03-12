"""Stub module for stage builds - required for test suite to run."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ValidationStage(str, Enum):
    """Validation stage enumeration."""
    STAGE_1 = "stage_1"
    STAGE_2 = "stage_2"
    STAGE_3 = "stage_3"
    STAGE_4 = "stage_4"
    STAGE_5 = "stage_5"
    SMOKE = "smoke"
    SILICON = "silicon"
    INTEGRATION = "integration"
    NIGHTLY = "nightly"
    FUOTA = "fuota"


@dataclass
class StageBuildDef:
    """Stage build definition."""
    stage: ValidationStage
    name: str
    description: Optional[str] = None


def get_stage_build_defs(product_id: str) -> List[StageBuildDef]:
    """Get stage build definitions for a product."""
    return []
