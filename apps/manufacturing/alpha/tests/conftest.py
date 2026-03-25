"""Shared fixtures for all manufacturing pytest tests.

Provides the ThetaFixtureConfig (migrated from shared/config.py) and
shared data containers used across test modules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PostTestSharedData:
    """Shared state passed between POST test steps."""
    imei: Optional[str] = None
    iccids: Optional[List[str]] = None


@dataclass
class ElectricalTestSharedData:
    """Shared state passed between electrical test steps."""
    step_count: int = 0


@dataclass
class FwFlashTestSharedData:
    """Shared state for firmware flash test."""
    pass
