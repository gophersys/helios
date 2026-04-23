"""Load and parse concord.yaml manifest files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import yaml

from corekinect.manifest.schema import ValidationError, ValidationResult, validate_manifest
from corekinect.manifest.types import (
    DeviceConfig,
    FixtureConfig,
    Manifest,
    PackageConfig,
    ProductConfig,
)

MANIFEST_FILENAME = "concord.yaml"
LEGACY_MANIFEST_FILENAME = "concord.test.yaml"


def find_manifest(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find concord.yaml by searching upward from start_dir.

    Checks for concord.yaml first (v2), then concord.test.yaml (v1 legacy).
    Returns the path if found, None otherwise.
    """
    search_dir = Path(start_dir) if start_dir else Path.cwd()
    search_dir = search_dir.resolve()

    for parent in [search_dir, *search_dir.parents]:
        v2_path = parent / MANIFEST_FILENAME
        if v2_path.is_file():
            return v2_path

        v1_path = parent / LEGACY_MANIFEST_FILENAME
        if v1_path.is_file():
            return v1_path

        # Stop at repo root
        if (parent / ".git").exists():
            break

    return None


def load_manifest(
    path: Optional[Path] = None,
    validate: bool = True,
) -> Tuple[Manifest, ValidationResult]:
    """Load and optionally validate a concord.yaml manifest.

    Args:
        path: Path to the manifest file. If None, searches from cwd.
        validate: Whether to run JSON Schema validation.

    Returns:
        Tuple of (Manifest, ValidationResult).

    Raises:
        FileNotFoundError: If no manifest file is found.
        yaml.YAMLError: If the file is not valid YAML.
    """
    if path is None:
        found = find_manifest()
        if found is None:
            raise FileNotFoundError(
                f"No {MANIFEST_FILENAME} found. "
                f"Run 'corectl test init' to create one, or specify --path."
            )
        path = found

    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        result = ValidationResult(
            errors=[ValidationError("(root)", "Manifest must be a YAML mapping")],
            warnings=[],
        )
        # Return a dummy manifest — caller should check result.valid
        return _empty_manifest(), result

    if validate:
        result = validate_manifest(raw)
    else:
        result = ValidationResult(errors=[], warnings=[])

    if result.valid:
        manifest = Manifest.from_dict(raw)
    else:
        manifest = _empty_manifest()

    return manifest, result


def load_manifest_raw(path: Path) -> dict:
    """Load a manifest as a raw dict without validation or parsing.

    Useful for migration tools that need to read v1 manifests.
    """
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def _empty_manifest() -> Manifest:
    """Return an empty manifest for error cases."""
    return Manifest(
        schema_version="0.0",
        package=PackageConfig(type="validation", version="0.0.0", framework=">=0.0.0"),
        product=ProductConfig(slug="", board="", device=DeviceConfig()),
        fixture=FixtureConfig(controller="", profile=""),
    )
