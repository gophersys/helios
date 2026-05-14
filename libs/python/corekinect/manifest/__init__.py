"""Concord test package manifest library.

Provides typed access to concord.yaml manifests with JSON Schema validation.
Shared between corectl (CLI), corekinect (framework), and the backend (API).
"""

from corekinect.manifest.types import (
    Manifest,
    PackageConfig,
    ProductConfig,
    DeviceConfig,
    TestBedConfig,
    StageConfig,
)
from corekinect.manifest.loader import load_manifest, find_manifest
from corekinect.manifest.schema import validate_manifest, SchemaVersion

__all__ = [
    "Manifest",
    "PackageConfig",
    "ProductConfig",
    "DeviceConfig",
    "TestBedConfig",
    "StageConfig",
    "load_manifest",
    "find_manifest",
    "validate_manifest",
    "SchemaVersion",
]
