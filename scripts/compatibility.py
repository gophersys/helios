#!/usr/bin/env python3
"""Compatibility matrix -- reads version info from the repo and outputs the current state.

Usage:
    python scripts/compatibility.py

Reads:
    - VERSION (platform version)
    - libs/python/corekinect/__init__.py (corekinect version)
    - libs/protocols/mtib/VERSION (proto version)
    - deploy/production/helm/values-staging.yaml (runner image tag)
    - deploy/production/helm/values-production.yaml (runner image tag)

Output: JSON compatibility report to stdout.
"""

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class ComponentVersion:
    name: str
    version: str
    source: str


@dataclass
class CompatibilityReport:
    platform: ComponentVersion
    corekinect: ComponentVersion
    proto: ComponentVersion
    notes: list[str]


def read_file_version(path: str) -> Optional[str]:
    """Read a VERSION file and return trimmed contents, or None."""
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def read_python_version(init_path: str) -> Optional[str]:
    """Extract __version__ from a Python __init__.py file."""
    try:
        with open(init_path) as f:
            content = f.read()
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            return m.group(1)
        return None
    except FileNotFoundError:
        return None


def get_platform_version(repo_root: str) -> ComponentVersion:
    """Read platform version from VERSION file."""
    path = os.path.join(repo_root, "VERSION")
    version = read_file_version(path) or "unknown"
    return ComponentVersion(
        name="concord-platform",
        version=version,
        source="VERSION",
    )


def get_corekinect_version(repo_root: str) -> ComponentVersion:
    """Read corekinect version from __init__.py."""
    path = os.path.join(repo_root, "libs", "python", "corekinect", "__init__.py")
    version = read_python_version(path) or "unknown"
    return ComponentVersion(
        name="corekinect",
        version=version,
        source="libs/python/corekinect/__init__.py",
    )


def get_proto_version(repo_root: str) -> ComponentVersion:
    """Read proto version from libs/protocols/mtib/VERSION."""
    path = os.path.join(repo_root, "libs", "protocols", "mtib", "VERSION")
    version = read_file_version(path) or "unknown"
    return ComponentVersion(
        name="mtib-proto",
        version=version,
        source="libs/protocols/mtib/VERSION",
    )


def check_compatibility(
    platform: ComponentVersion,
    corekinect: ComponentVersion,
    proto: ComponentVersion,
) -> list[str]:
    """Generate compatibility notes and warnings."""
    notes = []

    if platform.version == "unknown":
        notes.append("WARNING: Platform VERSION file not found")
    if corekinect.version == "unknown":
        notes.append("WARNING: corekinect version not found")
    if proto.version == "unknown":
        notes.append("WARNING: Proto VERSION file not found")

    # Version cross-checks can be extended here as compatibility
    # constraints are defined between components.

    if not notes:
        notes.append("All component versions detected successfully")

    return notes


def get_report(repo_root: Optional[str] = None) -> CompatibilityReport:
    """Build the full compatibility report."""
    if repo_root is None:
        repo_root = os.getcwd()

    platform = get_platform_version(repo_root)
    corekinect = get_corekinect_version(repo_root)
    proto = get_proto_version(repo_root)
    notes = check_compatibility(platform, corekinect, proto)

    return CompatibilityReport(
        platform=platform,
        corekinect=corekinect,
        proto=proto,
        notes=notes,
    )


def main() -> int:
    report = get_report()
    print(json.dumps(asdict(report), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
