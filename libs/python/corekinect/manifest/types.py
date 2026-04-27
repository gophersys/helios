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
    """Test-package metadata: kind, version, and framework version constraint."""

    type: str  # "validation" or "manufacturing"
    version: str  # semver e.g. "1.0.0"
    framework: str  # version constraint e.g. ">=0.3.0"


@dataclass(frozen=True)
class ProductConfig:
    """Product identity: slug + board revision + CoreOps device IDs."""

    slug: str
    board: str
    device: DeviceConfig = field(default_factory=DeviceConfig)


@dataclass(frozen=True)
class FixtureConfig:
    """Hardware-fixture wiring: controller class + profile YAML + slot mode."""

    controller: str  # dotted import path
    profile: str  # relative file path
    design: str = ""  # fixture design name (matches fixture.yaml 'name')
    revision: str = "1.0"  # fixture hardware revision (matches fixture.yaml 'revision')
    multi_slot: bool = False


@dataclass(frozen=True)
class StageConfig:
    """A validation stage (unordered, independently triggerable)."""

    name: str  # stage key from YAML (e.g. "smoke")
    directory: str  # relative test directory
    timeout_s: int
    markers: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class StepConfig:
    """A manufacturing test step (ordered, sequential)."""

    name: str  # display name (e.g. "Electrical")
    module: str  # dotted module path
    timeout_s: int


@dataclass(frozen=True)
class Manifest:
    """Parsed and validated concord.yaml manifest."""

    schema_version: str  # "1.0"
    package: PackageConfig
    product: ProductConfig
    fixture: FixtureConfig
    stages: Dict[str, StageConfig] = field(default_factory=dict)
    steps: List[StepConfig] = field(default_factory=list)

    @property
    def is_validation(self) -> bool:
        return self.package.type == "validation"

    @property
    def is_manufacturing(self) -> bool:
        return self.package.type == "manufacturing"

    @property
    def stage_names(self) -> List[str]:
        """Stage names for validation packages, step names for manufacturing."""
        if self.is_validation:
            return list(self.stages.keys())
        return [s.name for s in self.steps]

    @classmethod
    def from_dict(cls, data: dict) -> Manifest:
        """Construct a Manifest from a parsed YAML dict.

        Assumes the dict has already passed JSON Schema validation.
        """
        pkg = data["package"]
        prod = data["product"]
        fix = data["fixture"]

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

        steps: List[StepConfig] = []
        for cfg in data.get("steps", []):
            steps.append(
                StepConfig(
                    name=cfg["name"],
                    module=cfg["module"],
                    timeout_s=cfg["timeout_s"],
                )
            )

        return cls(
            schema_version=data["schema"],
            package=PackageConfig(
                type=pkg["type"],
                version=pkg["version"],
                framework=pkg["framework"],
            ),
            product=ProductConfig(
                slug=prod["slug"],
                board=prod["board"],
                device=device,
            ),
            fixture=FixtureConfig(
                controller=fix["controller"],
                profile=fix["profile"],
                design=fix.get("design", ""),
                revision=fix.get("revision", "1.0"),
                multi_slot=fix.get("multi_slot", False),
            ),
            stages=stages,
            steps=steps,
        )
