"""JSON Schema validation for concord.yaml manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "concord-manifest"

CURRENT_SCHEMA = "2.0"
MINIMUM_SCHEMA = "2.0"


@dataclass
class SchemaVersion:
    """Schema version with comparison support."""

    major: int
    minor: int

    @classmethod
    def parse(cls, version: str) -> SchemaVersion:
        parts = version.strip().split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid schema version '{version}': expected 'major.minor'")
        return cls(major=int(parts[0]), minor=int(parts[1]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self.major == other.major and self.minor == other.minor

    def __lt__(self, other: SchemaVersion) -> bool:
        if self.major != other.major:
            return self.major < other.major
        return self.minor < other.minor

    def __le__(self, other: SchemaVersion) -> bool:
        return self == other or self < other

    def __gt__(self, other: SchemaVersion) -> bool:
        return not self <= other

    def __ge__(self, other: SchemaVersion) -> bool:
        return not self < other


@dataclass
class ValidationError:
    path: str
    message: str

    def __str__(self) -> str:
        if self.path:
            return f"{self.path}: {self.message}"
        return self.message


@dataclass
class ValidationResult:
    errors: List[ValidationError]
    warnings: List[ValidationError]

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def __str__(self) -> str:
        lines = []
        for e in self.errors:
            lines.append(f"ERROR: {e}")
        for w in self.warnings:
            lines.append(f"WARNING: {w}")
        return "\n".join(lines)


def _load_json_schema(version: str) -> dict:
    """Load the JSON Schema file for a given version."""
    schema_path = SCHEMAS_DIR / f"v{version}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(schema_path) as f:
        return json.load(f)


def validate_manifest(data: dict, schema_version: Optional[str] = None) -> ValidationResult:
    """Validate a manifest dict against the JSON Schema.

    Args:
        data: Parsed YAML dict from concord.yaml.
        schema_version: Override the schema version to validate against.
            If None, uses the 'schema' field from data, or CURRENT_SCHEMA.

    Returns:
        ValidationResult with errors and warnings.
    """
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []

    # Determine schema version
    declared = data.get("schema")
    if declared is None:
        errors.append(ValidationError("schema", "Missing required field 'schema'"))
        return ValidationResult(errors=errors, warnings=warnings)

    version = schema_version or declared

    # Check version compatibility
    try:
        declared_v = SchemaVersion.parse(declared)
        minimum_v = SchemaVersion.parse(MINIMUM_SCHEMA)
        current_v = SchemaVersion.parse(CURRENT_SCHEMA)

        if declared_v < minimum_v:
            errors.append(
                ValidationError(
                    "schema",
                    f"Schema version {declared} is below minimum supported ({MINIMUM_SCHEMA}). "
                    f"Run 'corectl test migrate' to upgrade.",
                )
            )
            return ValidationResult(errors=errors, warnings=warnings)

        if declared_v > current_v:
            errors.append(
                ValidationError(
                    "schema",
                    f"Schema version {declared} is newer than supported ({CURRENT_SCHEMA}). "
                    f"Update your tools.",
                )
            )
            return ValidationResult(errors=errors, warnings=warnings)

        if declared_v < current_v:
            warnings.append(
                ValidationError(
                    "schema",
                    f"Schema version {declared} is outdated. Current is {CURRENT_SCHEMA}. "
                    f"Consider running 'corectl test migrate'.",
                )
            )
    except ValueError as e:
        errors.append(ValidationError("schema", str(e)))
        return ValidationResult(errors=errors, warnings=warnings)

    # Load and validate against JSON Schema
    try:
        import jsonschema

        json_schema = _load_json_schema(version)
        validator = jsonschema.Draft202012Validator(json_schema)

        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(ValidationError(path, error.message))
    except ImportError:
        # jsonschema not installed — do basic field checks
        warnings.append(
            ValidationError(
                "",
                "jsonschema package not installed. Falling back to basic validation.",
            )
        )
        errors.extend(_basic_validate(data))
    except FileNotFoundError as e:
        errors.append(ValidationError("schema", str(e)))

    # Semantic checks (beyond JSON Schema)
    if not errors:
        warnings.extend(_semantic_checks(data))

    return ValidationResult(errors=errors, warnings=warnings)


def _basic_validate(data: dict) -> List[ValidationError]:
    """Minimal validation when jsonschema is not available."""
    errors = []

    for field in ("schema", "package", "product", "fixture"):
        if field not in data:
            errors.append(ValidationError(field, f"Missing required field '{field}'"))

    if "package" in data:
        pkg = data["package"]
        for field in ("type", "version", "framework"):
            if field not in pkg:
                errors.append(ValidationError(f"package.{field}", f"Missing required field"))
        if pkg.get("type") not in ("validation", "manufacturing"):
            errors.append(
                ValidationError("package.type", "Must be 'validation' or 'manufacturing'")
            )

    if "product" in data:
        prod = data["product"]
        for field in ("slug", "board"):
            if field not in prod:
                errors.append(ValidationError(f"product.{field}", f"Missing required field"))

    if "fixture" in data:
        fix = data["fixture"]
        for field in ("controller", "profile"):
            if field not in fix:
                errors.append(ValidationError(f"fixture.{field}", f"Missing required field"))

    pkg_type = data.get("package", {}).get("type")
    if pkg_type == "validation" and "stages" not in data:
        errors.append(ValidationError("stages", "Required for validation packages"))
    if pkg_type == "manufacturing" and "stages" not in data and "steps" not in data:
        errors.append(ValidationError("stages", "Required for manufacturing packages (use 'stages' dict or 'steps' list)"))

    return errors


def _semantic_checks(data: dict) -> List[ValidationError]:
    """Checks that go beyond JSON Schema structure validation."""
    warnings = []

    product = data.get("product", {})
    device = product.get("device", {})
    if device.get("type_id", 0) == 0:
        warnings.append(
            ValidationError("product.device.type_id", "Device type ID is 0 (unset)")
        )
    if device.get("variant_id", 0) == 0:
        warnings.append(
            ValidationError("product.device.variant_id", "Device variant ID is 0 (unset)")
        )

    pkg_type = data.get("package", {}).get("type")
    if pkg_type == "manufacturing" and not data.get("fixture", {}).get("multi_slot"):
        warnings.append(
            ValidationError(
                "fixture.multi_slot",
                "Manufacturing packages typically use multi-slot fixtures. "
                "Set fixture.multi_slot: true if this fixture has multiple DUT slots.",
            )
        )

    return warnings


def check_schema_compatibility(declared: str) -> Optional[str]:
    """Check if a schema version is compatible with this installation.

    Returns None if compatible, or an error message if not.
    """
    try:
        declared_v = SchemaVersion.parse(declared)
        minimum_v = SchemaVersion.parse(MINIMUM_SCHEMA)
        current_v = SchemaVersion.parse(CURRENT_SCHEMA)
    except ValueError as e:
        return str(e)

    if declared_v < minimum_v:
        return (
            f"Schema version {declared} is below minimum supported ({MINIMUM_SCHEMA}). "
            f"Run 'corectl test migrate' to upgrade."
        )
    if declared_v > current_v:
        return (
            f"Schema version {declared} is newer than supported ({CURRENT_SCHEMA}). "
            f"Update your tools."
        )
    return None
