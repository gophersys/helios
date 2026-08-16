"""Typed dataclasses for concord.yaml manifest v1.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DeviceConfig:
    """CoreOps device-type identifiers used to claim and route a DUT."""

    type_id: int = 0
    variant_id: int = 0


@dataclass(frozen=True)
class PackageConfig:
    """Test-package metadata: kind, version, framework version constraint,
    and test framework dispatch.

    ``framework`` is a *corekinect version constraint* (kept for back-
    compat with the existing manifest schema). ``test_framework`` is the
    new dispatch field that selects pytest vs ztest at runner-Job
    creation time. Default is ``"pytest"`` so any concord.yaml predating
    the dispatch keeps the same behaviour."""

    type: str  # "validation" or "manufacturing"
    version: str  # semver e.g. "1.0.0"
    framework: str  # version constraint e.g. ">=0.3.0"
    test_framework: str = "pytest"  # "pytest" or "ztest"


@dataclass(frozen=True)
class ProductConfig:
    """Product identity: slug + board revision + CoreOps device IDs."""

    slug: str
    board: str
    device: DeviceConfig = field(default_factory=DeviceConfig)


@dataclass(frozen=True)
class TestBedConfig:
    __test__ = False  # not a pytest test class
    """Pointer to the test app's Python ``TestBed`` class.

    Format: ``dotted.module.path:ClassName`` (e.g.
    ``testbeds.alpha_b0.testbed:AlphaB0TestBed``). The class is the
    single source of truth for the fixture's DUT-side wiring; the
    backend AST-extracts ``name`` and ``revision`` from the class at
    upload time so the manifest doesn't need to repeat them.
    """

    module: str
    multi_slot: bool = False

    @property
    def module_path(self) -> str:
        """Dotted module portion of ``module`` (before the ``:``)."""
        return self.module.split(":", 1)[0]

    @property
    def class_name(self) -> str:
        """Class name portion of ``module`` (after the ``:``)."""
        parts = self.module.split(":", 1)
        return parts[1] if len(parts) == 2 else ""

    @property
    def file_path(self) -> str:
        """Relative file path within the tar.gz, derived from ``module_path``.

        ``testbeds.alpha_b0.testbed`` → ``testbeds/alpha_b0/testbed.py``.
        """
        return self.module_path.replace(".", "/") + ".py"


@dataclass(frozen=True)
class StageConfig:
    """A validation stage (unordered, independently triggerable)."""

    name: str  # stage key from YAML (e.g. "smoke")
    directory: str  # relative test directory
    timeout_s: int
    markers: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Manifest:
    """Parsed and validated concord.yaml manifest."""

    schema_version: str  # "1.0"
    package: PackageConfig
    product: ProductConfig
    testbed: TestBedConfig
    stages: Dict[str, StageConfig] = field(default_factory=dict)

    @property
    def is_validation(self) -> bool:
        return self.package.type == "validation"

    @property
    def is_manufacturing(self) -> bool:
        return self.package.type == "manufacturing"

    @property
    def stage_names(self) -> List[str]:
        return list(self.stages.keys())

    @classmethod
    def from_dict(cls, data: dict) -> Manifest:
        """Construct a Manifest from a parsed YAML dict.

        Assumes the dict has already passed JSON Schema validation.
        """
        pkg = data["package"]
        prod = data["product"]
        fix = data["testbed"]

        device_data = prod.get("device", {})
        device = DeviceConfig(
            type_id=device_data.get("type_id", 0),
            variant_id=device_data.get("variant_id", 0),
        )

        stages: Dict[str, StageConfig] = {}
        for name, cfg in data.get("stages", {}).items():
            stages[name] = StageConfig(
                name=name,
                directory=cfg["directory"],
                timeout_s=cfg["timeout_s"],
                markers=cfg.get("markers", []),
            )

        return cls(
            schema_version=data["schema"],
            package=PackageConfig(
                type=pkg["type"],
                version=pkg["version"],
                framework=pkg["framework"],
                test_framework=pkg.get("test_framework", "pytest"),
            ),
            product=ProductConfig(
                slug=prod["slug"],
                board=prod["board"],
                device=device,
            ),
            testbed=TestBedConfig(
                module=fix["module"],
                multi_slot=fix.get("multi_slot", False),
            ),
            stages=stages,
        )
