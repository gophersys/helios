"""Tests for the concord.yaml manifest library.

Covers types.py (dataclass construction and properties), schema.py (JSON Schema
validation, version handling, semantic checks), and loader.py (YAML file loading,
manifest discovery, raw loading).
"""

import copy
import textwrap

import pytest
import yaml

from corekinect.manifest.types import (
    DeviceConfig,
    FixtureConfig,
    Manifest,
    PackageConfig,
    ProductConfig,
    StageConfig,
    StepConfig,
)
from corekinect.manifest.schema import (
    CURRENT_SCHEMA,
    MINIMUM_SCHEMA,
    SchemaVersion,
    ValidationResult,
    check_schema_compatibility,
    validate_manifest,
)
from corekinect.manifest.loader import (
    MANIFEST_FILENAME,
    find_manifest,
    load_manifest,
    load_manifest_raw,
)


# ---------------------------------------------------------------------------
# Fixture data: reusable manifest dicts
# ---------------------------------------------------------------------------

def _validation_dict() -> dict:
    """Full validation manifest dict matching the v1.0 schema."""
    return {
        "schema": "1.0",
        "package": {
            "type": "validation",
            "version": "1.0.0",
            "framework": ">=0.3.0",
        },
        "product": {
            "slug": "alpha",
            "board": "alpha_b0",
            "device": {
                "type_id": 42,
                "variant_id": 7,
            },
        },
        "fixture": {
            "design": "Alpha B0 Validation Fixture",
            "revision": "1.0",
            "controller": "fixtures.alpha_b0.controller.AlphaB0Fixture",
            "profile": "fixtures/alpha_b0/fixture.yaml",
            "multi_slot": False,
        },
        "stages": {
            "smoke": {
                "directory": "tests/smoke",
                "timeout_s": 120,
                "hardware": ["power", "uart"],
                "markers": ["health_check"],
            },
            "integration": {
                "directory": "tests/integration",
                "timeout_s": 600,
                "hardware": ["power", "uart", "button"],
                "markers": ["slow"],
            },
        },
    }


def _manufacturing_dict() -> dict:
    """Full manufacturing manifest dict matching the v1.0 schema."""
    return {
        "schema": "1.0",
        "package": {
            "type": "manufacturing",
            "version": "2.1.0",
            "framework": ">=0.3.0",
        },
        "product": {
            "slug": "alpha",
            "board": "alpha_b0",
            "device": {
                "type_id": 42,
                "variant_id": 7,
            },
        },
        "fixture": {
            "design": "Alpha B0 Manufacturing Fixture",
            "revision": "1.0",
            "controller": "fixtures.alpha_b0.controller.AlphaB0Fixture",
            "profile": "fixtures/alpha_b0/fixture.yaml",
            "multi_slot": True,
        },
        "steps": [
            {
                "name": "Electrical",
                "module": "tests.manufacturing.test_electrical",
                "timeout_s": 30,
                "hardware": ["power"],
            },
            {
                "name": "Flash Firmware",
                "module": "tests.manufacturing.test_flash",
                "timeout_s": 120,
                "hardware": ["power", "jlink"],
            },
            {
                "name": "POST",
                "module": "tests.manufacturing.test_post",
                "timeout_s": 300,
                "hardware": ["power", "uart"],
            },
        ],
    }


def _minimal_validation_dict() -> dict:
    """Validation manifest with no device, no hardware, no markers."""
    return {
        "schema": "1.0",
        "package": {
            "type": "validation",
            "version": "0.1.0",
            "framework": ">=0.1.0",
        },
        "product": {
            "slug": "beta",
            "board": "beta_a0",
        },
        "fixture": {
            "design": "Beta A0 Validation Fixture",
            "revision": "1.0",
            "controller": "fixtures.beta.Controller",
            "profile": "fixtures/beta/profile.yaml",
        },
        "stages": {
            "smoke": {
                "directory": "tests/smoke",
                "timeout_s": 60,
            },
        },
    }


def _write_manifest(path, data):
    """Helper to write a YAML manifest to disk."""
    path.write_text(yaml.dump(data, default_flow_style=False))


# ===================================================================
# types.py tests
# ===================================================================


class TestManifestFromDictValidation:
    """Manifest.from_dict with a full validation manifest."""

    def test_schema_version(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.schema_version == "1.0"

    def test_package_fields(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.package.type == "validation"
        assert m.package.version == "1.0.0"
        assert m.package.framework == ">=0.3.0"

    def test_product_fields(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.product.slug == "alpha"
        assert m.product.board == "alpha_b0"
        assert m.product.device.type_id == 42
        assert m.product.device.variant_id == 7

    def test_fixture_fields(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.fixture.controller == "fixtures.alpha_b0.controller.AlphaB0Fixture"
        assert m.fixture.profile == "fixtures/alpha_b0/fixture.yaml"
        assert m.fixture.multi_slot is False

    def test_stages_parsed(self):
        m = Manifest.from_dict(_validation_dict())
        assert len(m.stages) == 2
        assert "smoke" in m.stages
        assert "integration" in m.stages

    def test_stage_config_fields(self):
        m = Manifest.from_dict(_validation_dict())
        smoke = m.stages["smoke"]
        assert smoke.name == "smoke"
        assert smoke.directory == "tests/smoke"
        assert smoke.timeout_s == 120
        assert smoke.hardware == ["power", "uart"]
        assert smoke.markers == ["health_check"]

    def test_steps_empty_for_validation(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.steps == []


class TestManifestFromDictManufacturing:
    """Manifest.from_dict with a full manufacturing manifest."""

    def test_package_type(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert m.package.type == "manufacturing"

    def test_steps_parsed(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert len(m.steps) == 3

    def test_step_config_fields(self):
        m = Manifest.from_dict(_manufacturing_dict())
        first = m.steps[0]
        assert first.name == "Electrical"
        assert first.module == "tests.manufacturing.test_electrical"
        assert first.timeout_s == 30
        assert first.hardware == ["power"]

    def test_stages_empty_for_manufacturing(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert m.stages == {}

    def test_fixture_multi_slot(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert m.fixture.multi_slot is True


class TestManifestFromDictMinimal:
    """Manifest.from_dict with minimal data (no device, no hardware, no markers)."""

    def test_device_defaults_to_zero(self):
        m = Manifest.from_dict(_minimal_validation_dict())
        assert m.product.device.type_id == 0
        assert m.product.device.variant_id == 0

    def test_hardware_defaults_to_empty(self):
        m = Manifest.from_dict(_minimal_validation_dict())
        smoke = m.stages["smoke"]
        assert smoke.hardware == []

    def test_markers_defaults_to_empty(self):
        m = Manifest.from_dict(_minimal_validation_dict())
        smoke = m.stages["smoke"]
        assert smoke.markers == []

    def test_multi_slot_defaults_to_false(self):
        m = Manifest.from_dict(_minimal_validation_dict())
        assert m.fixture.multi_slot is False


class TestManifestProperties:
    """is_validation, is_manufacturing, stage_names, all_hardware."""

    def test_is_validation_true(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.is_validation is True
        assert m.is_manufacturing is False

    def test_is_manufacturing_true(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert m.is_manufacturing is True
        assert m.is_validation is False

    def test_stage_names_validation(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.stage_names == ["smoke", "integration"]

    def test_stage_names_manufacturing(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert m.stage_names == ["Electrical", "Flash Firmware", "POST"]

    def test_all_hardware_validation(self):
        m = Manifest.from_dict(_validation_dict())
        assert m.all_hardware == ["button", "power", "uart"]

    def test_all_hardware_manufacturing(self):
        m = Manifest.from_dict(_manufacturing_dict())
        assert m.all_hardware == ["jlink", "power", "uart"]

    def test_all_hardware_empty_when_none(self):
        m = Manifest.from_dict(_minimal_validation_dict())
        assert m.all_hardware == []


class TestFrozenDataclasses:
    """Frozen dataclass behavior -- cannot mutate after construction."""

    def test_manifest_frozen(self):
        m = Manifest.from_dict(_validation_dict())
        with pytest.raises(AttributeError):
            m.schema_version = "3.0"

    def test_package_config_frozen(self):
        m = Manifest.from_dict(_validation_dict())
        with pytest.raises(AttributeError):
            m.package.type = "manufacturing"

    def test_product_config_frozen(self):
        m = Manifest.from_dict(_validation_dict())
        with pytest.raises(AttributeError):
            m.product.slug = "other"

    def test_device_config_frozen(self):
        m = Manifest.from_dict(_validation_dict())
        with pytest.raises(AttributeError):
            m.product.device.type_id = 99

    def test_fixture_config_frozen(self):
        m = Manifest.from_dict(_validation_dict())
        with pytest.raises(AttributeError):
            m.fixture.profile = "other.yaml"

    def test_stage_config_frozen(self):
        m = Manifest.from_dict(_validation_dict())
        with pytest.raises(AttributeError):
            m.stages["smoke"].timeout_s = 999

    def test_step_config_frozen(self):
        m = Manifest.from_dict(_manufacturing_dict())
        with pytest.raises(AttributeError):
            m.steps[0].name = "Other"


# ===================================================================
# schema.py tests
# ===================================================================


class TestValidateManifestValid:
    """validate_manifest with valid manifests returns no errors."""

    def test_valid_validation_manifest(self):
        result = validate_manifest(_validation_dict())
        assert result.valid, f"Expected valid, got errors: {result}"

    def test_valid_manufacturing_manifest(self):
        result = validate_manifest(_manufacturing_dict())
        assert result.valid, f"Expected valid, got errors: {result}"


class TestValidateManifestMissingFields:
    """validate_manifest rejects missing required fields."""

    def test_missing_schema(self):
        data = _validation_dict()
        del data["schema"]
        result = validate_manifest(data)
        assert not result.valid
        assert any("schema" in str(e).lower() for e in result.errors)

    def test_missing_package(self):
        data = _validation_dict()
        del data["package"]
        result = validate_manifest(data)
        assert not result.valid
        assert any("package" in str(e).lower() for e in result.errors)

    def test_missing_product(self):
        data = _validation_dict()
        del data["product"]
        result = validate_manifest(data)
        assert not result.valid
        assert any("product" in str(e).lower() for e in result.errors)

    def test_missing_fixture(self):
        data = _validation_dict()
        del data["fixture"]
        result = validate_manifest(data)
        assert not result.valid
        assert any("fixture" in str(e).lower() for e in result.errors)

    def test_missing_stages_for_validation(self):
        data = _validation_dict()
        del data["stages"]
        result = validate_manifest(data)
        assert not result.valid

    def test_missing_steps_for_manufacturing(self):
        data = _manufacturing_dict()
        del data["steps"]
        result = validate_manifest(data)
        assert not result.valid


class TestValidateManifestBadValues:
    """validate_manifest rejects invalid field values."""

    def test_wrong_package_type(self):
        data = _validation_dict()
        data["package"]["type"] = "testing"
        result = validate_manifest(data)
        assert not result.valid

    def test_both_stages_and_steps_is_invalid(self):
        """Both stages and steps in the same manifest is invalid (oneOf)."""
        data = _validation_dict()
        data["steps"] = [
            {"name": "x", "module": "m.x", "timeout_s": 10},
        ]
        result = validate_manifest(data)
        assert not result.valid

    def test_neither_stages_nor_steps_is_invalid(self):
        """A manifest with neither stages nor steps is invalid."""
        data = _validation_dict()
        del data["stages"]
        result = validate_manifest(data)
        assert not result.valid

    def test_extra_root_properties(self):
        data = _validation_dict()
        data["extra_field"] = "not allowed"
        result = validate_manifest(data)
        assert not result.valid

    def test_bad_framework_format(self):
        data = _validation_dict()
        data["package"]["framework"] = ">=abc"
        result = validate_manifest(data)
        assert not result.valid

    def test_directory_path_traversal(self):
        data = _validation_dict()
        data["stages"]["smoke"]["directory"] = "../traversal"
        result = validate_manifest(data)
        assert not result.valid

    def test_profile_not_ending_in_yaml(self):
        data = _validation_dict()
        data["fixture"]["profile"] = "fixtures/profile.json"
        result = validate_manifest(data)
        assert not result.valid

    def test_uppercase_stage_name(self):
        data = _validation_dict()
        data["stages"]["Smoke"] = data["stages"].pop("smoke")
        result = validate_manifest(data)
        assert not result.valid

    def test_zero_timeout(self):
        data = _validation_dict()
        data["stages"]["smoke"]["timeout_s"] = 0
        result = validate_manifest(data)
        assert not result.valid


class TestValidateManifestWarnings:
    """Semantic warnings that do not make the manifest invalid."""

    def test_warns_on_device_type_id_zero(self):
        data = _validation_dict()
        data["product"]["device"]["type_id"] = 0
        result = validate_manifest(data)
        assert result.valid
        assert any("type_id" in str(w) for w in result.warnings)

    def test_warns_on_manufacturing_without_multi_slot(self):
        data = _manufacturing_dict()
        data["fixture"]["multi_slot"] = False
        result = validate_manifest(data)
        assert result.valid
        assert any("multi_slot" in str(w) for w in result.warnings)


class TestSchemaVersionParse:
    """SchemaVersion.parse with valid and invalid inputs."""

    def test_parse_valid(self):
        v = SchemaVersion.parse("2.0")
        assert v.major == 2
        assert v.minor == 0

    def test_parse_higher_version(self):
        v = SchemaVersion.parse("10.3")
        assert v.major == 10
        assert v.minor == 3

    def test_parse_invalid_no_dot(self):
        with pytest.raises(ValueError):
            SchemaVersion.parse("2")

    def test_parse_invalid_too_many_parts(self):
        with pytest.raises(ValueError):
            SchemaVersion.parse("2.0.1")

    def test_parse_invalid_non_numeric(self):
        with pytest.raises(ValueError):
            SchemaVersion.parse("a.b")

    def test_str_roundtrip(self):
        v = SchemaVersion.parse("2.0")
        assert str(v) == "2.0"


class TestSchemaVersionComparison:
    """SchemaVersion comparison operators."""

    def test_eq(self):
        assert SchemaVersion(2, 0) == SchemaVersion(2, 0)

    def test_neq(self):
        assert SchemaVersion(2, 0) != SchemaVersion(2, 1)

    def test_lt_minor(self):
        assert SchemaVersion(2, 0) < SchemaVersion(2, 1)

    def test_lt_major(self):
        assert SchemaVersion(1, 9) < SchemaVersion(2, 0)

    def test_le(self):
        assert SchemaVersion(2, 0) <= SchemaVersion(2, 0)
        assert SchemaVersion(1, 0) <= SchemaVersion(2, 0)

    def test_gt(self):
        assert SchemaVersion(3, 0) > SchemaVersion(2, 9)

    def test_ge(self):
        assert SchemaVersion(2, 0) >= SchemaVersion(2, 0)
        assert SchemaVersion(3, 0) >= SchemaVersion(2, 0)

    def test_not_lt_when_equal(self):
        assert not (SchemaVersion(2, 0) < SchemaVersion(2, 0))

    def test_eq_with_non_schema_version(self):
        assert SchemaVersion(2, 0).__eq__("not a version") is NotImplemented


class TestCheckSchemaCompatibility:
    """check_schema_compatibility with old, current, and future versions."""

    def test_current_version_compatible(self):
        assert check_schema_compatibility(CURRENT_SCHEMA) is None

    def test_old_version_below_minimum(self):
        msg = check_schema_compatibility("0.9")
        assert msg is not None
        assert "below minimum" in msg

    def test_future_version_above_current(self):
        msg = check_schema_compatibility("99.0")
        assert msg is not None
        assert "newer than supported" in msg

    def test_invalid_version_string(self):
        msg = check_schema_compatibility("bad")
        assert msg is not None


class TestValidateManifestSchemaVersion:
    """validate_manifest rejects out-of-range schema versions."""

    def test_rejects_schema_below_minimum(self):
        data = _validation_dict()
        data["schema"] = "0.9"
        result = validate_manifest(data)
        assert not result.valid
        assert any("below minimum" in str(e) for e in result.errors)

    def test_rejects_schema_above_current(self):
        data = _validation_dict()
        data["schema"] = "99.0"
        result = validate_manifest(data)
        assert not result.valid
        assert any("newer than supported" in str(e) for e in result.errors)

    def test_rejects_unparseable_schema(self):
        data = _validation_dict()
        data["schema"] = "garbage"
        result = validate_manifest(data)
        assert not result.valid


# ===================================================================
# loader.py tests
# ===================================================================


class TestLoadManifest:
    """load_manifest from valid and invalid YAML files."""

    def test_load_valid_validation_manifest(self, tmp_path):
        path = tmp_path / MANIFEST_FILENAME
        _write_manifest(path, _validation_dict())
        manifest, result = load_manifest(path=path)
        assert result.valid
        assert manifest.is_validation
        assert manifest.package.version == "1.0.0"

    def test_load_valid_manufacturing_manifest(self, tmp_path):
        path = tmp_path / MANIFEST_FILENAME
        _write_manifest(path, _manufacturing_dict())
        manifest, result = load_manifest(path=path)
        assert result.valid
        assert manifest.is_manufacturing

    def test_load_invalid_yaml_not_a_mapping(self, tmp_path):
        path = tmp_path / MANIFEST_FILENAME
        path.write_text("- this\n- is\n- a list\n")
        manifest, result = load_manifest(path=path)
        assert not result.valid
        assert any("mapping" in str(e).lower() for e in result.errors)

    def test_load_invalid_manifest_missing_fields(self, tmp_path):
        path = tmp_path / MANIFEST_FILENAME
        _write_manifest(path, {"schema": "1.0"})
        manifest, result = load_manifest(path=path)
        assert not result.valid

    def test_load_with_validate_false_skips_validation(self, tmp_path):
        """validate=False skips JSON Schema checks but still parses."""
        data = _validation_dict()
        path = tmp_path / MANIFEST_FILENAME
        _write_manifest(path, data)
        manifest, result = load_manifest(path=path, validate=False)
        assert result.valid  # no errors because validation was skipped
        assert manifest.package.type == "validation"

    def test_load_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_manifest(path=tmp_path / "nonexistent.yaml")


class TestFindManifest:
    """find_manifest discovery behavior."""

    def test_finds_concord_yaml(self, tmp_path):
        manifest_path = tmp_path / MANIFEST_FILENAME
        manifest_path.write_text("schema: '1.0'\n")
        found = find_manifest(tmp_path)
        assert found is not None
        assert found.name == MANIFEST_FILENAME

    def test_returns_none_when_no_manifest(self, tmp_path):
        # Empty directory with a .git sentinel so the search stops here
        (tmp_path / ".git").mkdir()
        found = find_manifest(tmp_path)
        assert found is None

    def test_stops_at_git_boundary(self, tmp_path):
        """Manifest in parent above .git should not be found."""
        # parent/concord.yaml exists
        (tmp_path / MANIFEST_FILENAME).write_text("schema: '1.0'\n")
        # child/.git exists -- search should stop here
        child = tmp_path / "child"
        child.mkdir()
        (child / ".git").mkdir()
        found = find_manifest(child)
        assert found is None

    def test_finds_manifest_in_parent(self, tmp_path):
        """Walks up to parent if child has no manifest and no .git."""
        (tmp_path / MANIFEST_FILENAME).write_text("schema: '1.0'\n")
        child = tmp_path / "subdir"
        child.mkdir()
        found = find_manifest(child)
        assert found is not None
        assert found.name == MANIFEST_FILENAME


class TestLoadManifestRaw:
    """load_manifest_raw returns raw dict."""

    def test_returns_raw_dict(self, tmp_path):
        data = _validation_dict()
        path = tmp_path / MANIFEST_FILENAME
        _write_manifest(path, data)
        raw = load_manifest_raw(path)
        assert isinstance(raw, dict)
        assert raw["schema"] == "1.0"
        assert raw["package"]["type"] == "validation"

    def test_raises_on_non_mapping(self, tmp_path):
        path = tmp_path / MANIFEST_FILENAME
        path.write_text("- a\n- b\n")
        with pytest.raises(ValueError, match="mapping"):
            load_manifest_raw(path)

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_manifest_raw(tmp_path / "no_such_file.yaml")
