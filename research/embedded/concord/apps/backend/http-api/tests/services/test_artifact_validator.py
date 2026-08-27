"""Tests for services/builds/artifact_validator.py — build run artifact validation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_obj
from src.services.builds.artifact_validator import (
    validate_build_run_artifacts,
    format_missing_artifacts_message,
    _parse_build_matrix,
    _parse_product_targets,
    _check_build_artifacts,
    _has_artifact_by_pattern,
)


# ---------------------------------------------------------------------------
# _parse_build_matrix
# ---------------------------------------------------------------------------

class TestParseBuildMatrix:
    def test_returns_none_when_no_attr(self):
        config = make_obj()
        assert _parse_build_matrix(config) is None

    def test_returns_none_when_empty(self):
        config = make_obj(buildMatrix=None)
        assert _parse_build_matrix(config) is None

    def test_returns_list_directly(self):
        matrix = [{"role": "app"}]
        config = make_obj(buildMatrix=matrix)
        assert _parse_build_matrix(config) == matrix

    def test_parses_json_string(self):
        matrix = [{"role": "comms"}]
        config = make_obj(buildMatrix=json.dumps(matrix))
        assert _parse_build_matrix(config) == matrix

    def test_invalid_json_returns_none(self):
        config = make_obj(buildMatrix="not-json{")
        assert _parse_build_matrix(config) is None

    def test_json_non_list_returns_none(self):
        config = make_obj(buildMatrix='{"key": "val"}')
        assert _parse_build_matrix(config) is None

    def test_non_string_non_list_returns_none(self):
        config = make_obj(buildMatrix=42)
        assert _parse_build_matrix(config) is None


# ---------------------------------------------------------------------------
# _parse_product_targets
# ---------------------------------------------------------------------------

class TestParseProductTargets:
    def test_returns_none_when_no_product(self):
        assert _parse_product_targets(None) is None

    def test_returns_none_when_no_build_config(self):
        product = make_obj(buildConfig=None)
        assert _parse_product_targets(product) is None

    def test_returns_none_when_no_build_config_attr(self):
        product = make_obj()
        assert _parse_product_targets(product) is None

    def test_parses_dict_build_config(self):
        targets = [{"role": "app", "processor": "nrf52840"}]
        product = make_obj(buildConfig={"targets": targets})
        assert _parse_product_targets(product) == targets

    def test_parses_json_string_build_config(self):
        targets = [{"role": "comms", "processor": "nrf9151"}]
        product = make_obj(buildConfig=json.dumps({"targets": targets}))
        assert _parse_product_targets(product) == targets

    def test_invalid_json_returns_none(self):
        product = make_obj(buildConfig="bad{json")
        assert _parse_product_targets(product) is None

    def test_empty_targets_returns_none(self):
        product = make_obj(buildConfig={"targets": []})
        assert _parse_product_targets(product) is None

    def test_no_targets_key_returns_none(self):
        product = make_obj(buildConfig={"other": "data"})
        assert _parse_product_targets(product) is None


# ---------------------------------------------------------------------------
# _has_artifact_by_pattern
# ---------------------------------------------------------------------------

class TestHasArtifactByPattern:
    def test_matches_role_in_name(self):
        artifacts = [make_obj(name="0.8.3_release_app_nrf52840.hex")]
        assert _has_artifact_by_pattern(artifacts, "app", "nrf52840", "plaintextHex", ".hex") is True

    def test_matches_processor_in_name(self):
        artifacts = [make_obj(name="0.8.3_nrf52840.hex")]
        assert _has_artifact_by_pattern(artifacts, "unknown", "nrf52840", "plaintextHex", ".hex") is True

    def test_no_match_wrong_extension(self):
        artifacts = [make_obj(name="0.8.3_app.cfw")]
        assert _has_artifact_by_pattern(artifacts, "app", "nrf52840", "plaintextHex", ".hex") is False

    def test_no_match_no_role_or_processor(self):
        artifacts = [make_obj(name="firmware.hex")]
        assert _has_artifact_by_pattern(artifacts, "app", "nrf52840", "plaintextHex", ".hex") is False

    def test_empty_artifacts(self):
        assert _has_artifact_by_pattern([], "app", "nrf52840", "plaintextHex", ".hex") is False

    def test_artifact_with_no_name(self):
        artifacts = [make_obj(name=None)]
        assert _has_artifact_by_pattern(artifacts, "app", "nrf52840", "plaintextHex", ".hex") is False


# ---------------------------------------------------------------------------
# _check_build_artifacts
# ---------------------------------------------------------------------------

class TestCheckBuildArtifacts:
    _targets = [{"role": "app", "processor": "nrf52840"}, {"role": "comms", "processor": "nrf9151"}]

    def test_no_build_returns_all_missing(self):
        result = _check_build_artifacts("MFG", None, self._targets, requires_cfw=False)
        assert result["complete"] is False
        assert result["buildId"] is None
        missing = result["_missing"]
        # 2 hex + 1 manifest
        assert len(missing) == 3

    def test_no_build_with_cfw_returns_extra_missing(self):
        result = _check_build_artifacts("MFG", None, self._targets, requires_cfw=True)
        missing = result["_missing"]
        # 2 hex + 2 cfw + 1 manifest
        assert len(missing) == 5

    def test_failed_build_returns_all_missing(self):
        build = make_obj(id="b-1", status="FAILED", artifacts=[])
        result = _check_build_artifacts("RELEASE", build, self._targets, requires_cfw=False)
        assert result["complete"] is False
        assert result["status"] == "FAILED"

    def test_success_build_with_all_artifacts(self):
        artifacts = [
            make_obj(role="app", artifactType="plaintextHex", name="app.hex"),
            make_obj(role="comms", artifactType="plaintextHex", name="comms.hex"),
            make_obj(role=None, artifactType="manifest", name="build.json"),
        ]
        build = make_obj(id="b-1", status="SUCCESS", artifacts=artifacts)
        result = _check_build_artifacts("RELEASE", build, self._targets, requires_cfw=False)
        assert result["complete"] is True
        assert result["_missing"] == []
        assert result["artifacts"]["manifest"] is True

    def test_success_build_missing_hex(self):
        artifacts = [
            make_obj(role="comms", artifactType="plaintextHex", name="comms.hex"),
            make_obj(role=None, artifactType="manifest", name="build.json"),
        ]
        build = make_obj(id="b-1", status="SUCCESS", artifacts=artifacts)
        result = _check_build_artifacts("RELEASE", build, self._targets, requires_cfw=False)
        assert result["complete"] is False
        assert any(m["role"] == "app" for m in result["_missing"])

    def test_success_build_missing_cfw_when_required(self):
        artifacts = [
            make_obj(role="app", artifactType="plaintextHex", name="app.hex"),
            make_obj(role="comms", artifactType="plaintextHex", name="comms.hex"),
            make_obj(role=None, artifactType="manifest", name="build.json"),
        ]
        build = make_obj(id="b-1", status="SUCCESS", artifacts=artifacts)
        result = _check_build_artifacts("RELEASE", build, self._targets, requires_cfw=True)
        assert result["complete"] is False
        cfw_missing = [m for m in result["_missing"] if m["artifactType"] == "encryptedCfw"]
        assert len(cfw_missing) == 2

    def test_cached_build_treated_as_success(self):
        artifacts = [
            make_obj(role="app", artifactType="plaintextHex", name="app.hex"),
            make_obj(role="comms", artifactType="plaintextHex", name="comms.hex"),
            make_obj(role=None, artifactType="manifest", name="build.json"),
        ]
        build = make_obj(id="b-1", status="CACHED", artifacts=artifacts)
        result = _check_build_artifacts("RELEASE", build, self._targets, requires_cfw=False)
        assert result["complete"] is True

    def test_manifest_detected_by_name_pattern(self):
        artifacts = [
            make_obj(role="app", artifactType="plaintextHex", name="app.hex"),
            make_obj(role="comms", artifactType="plaintextHex", name="comms.hex"),
            make_obj(role=None, artifactType=None, name="build.json"),
        ]
        build = make_obj(id="b-1", status="SUCCESS", artifacts=artifacts)
        result = _check_build_artifacts("RELEASE", build, self._targets, requires_cfw=False)
        assert result["artifacts"]["manifest"] is True


# ---------------------------------------------------------------------------
# validate_build_run_artifacts (integration)
# ---------------------------------------------------------------------------

class TestValidateBuildRunArtifacts:
    def test_build_run_not_found(self):
        db = MagicMock()
        db.buildrun.find_unique.return_value = None
        result = validate_build_run_artifacts(db, "missing-id")
        assert result["valid"] is True
        assert result["builds"] == []

    def test_no_stage_config(self):
        build_run = make_obj(stageConfigId=None, builds=[], product=None)
        db = MagicMock()
        db.buildrun.find_unique.return_value = build_run
        result = validate_build_run_artifacts(db, "run-1")
        assert result["valid"] is True

    def test_no_build_matrix(self):
        build_run = make_obj(stageConfigId="sc-1", builds=[], product=None)
        stage_config = make_obj(buildMatrix=None, requiresFuota=False, stage=2)
        db = MagicMock()
        db.buildrun.find_unique.return_value = build_run
        db.productstageconfig.find_unique.return_value = stage_config
        result = validate_build_run_artifacts(db, "run-1")
        assert result["valid"] is True

    def test_no_product_targets(self):
        build_run = make_obj(stageConfigId="sc-1", builds=[], product=make_obj(buildConfig=None))
        stage_config = make_obj(buildMatrix=[{"role": "app"}], requiresFuota=False, stage=2)
        db = MagicMock()
        db.buildrun.find_unique.return_value = build_run
        db.productstageconfig.find_unique.return_value = stage_config
        result = validate_build_run_artifacts(db, "run-1")
        assert result["valid"] is True

    def test_full_validation_pass(self):
        artifacts = [
            make_obj(role="app", artifactType="plaintextHex", name="app.hex"),
            make_obj(role=None, artifactType="manifest", name="build.json"),
        ]
        build = make_obj(id="b-1", status="SUCCESS", artifacts=artifacts, matrixLabel="app")
        product = make_obj(buildConfig={"targets": [{"role": "app", "processor": "nrf52840"}]})
        build_run = make_obj(stageConfigId="sc-1", builds=[build], product=product)
        stage_config = make_obj(
            buildMatrix=[{"role": "app", "label": "app"}],
            requiresFuota=False,
            stage=2,
        )
        db = MagicMock()
        db.buildrun.find_unique.return_value = build_run
        db.productstageconfig.find_unique.return_value = stage_config
        result = validate_build_run_artifacts(db, "run-1")
        assert result["valid"] is True
        assert len(result["missing"]) == 0

    def test_full_validation_fail_missing_build(self):
        product = make_obj(buildConfig={"targets": [{"role": "app", "processor": "nrf52840"}]})
        build_run = make_obj(stageConfigId="sc-1", builds=[], product=product)
        stage_config = make_obj(
            buildMatrix=[{"role": "app", "label": "app"}],
            requiresFuota=False,
            stage=2,
        )
        db = MagicMock()
        db.buildrun.find_unique.return_value = build_run
        db.productstageconfig.find_unique.return_value = stage_config
        result = validate_build_run_artifacts(db, "run-1")
        assert result["valid"] is False
        assert len(result["missing"]) > 0

    def test_requires_cfw_for_stage_4_plus(self):
        artifacts = [
            make_obj(role="app", artifactType="plaintextHex", name="app.hex"),
            make_obj(role=None, artifactType="manifest", name="build.json"),
        ]
        build = make_obj(id="b-1", status="SUCCESS", artifacts=artifacts, matrixLabel="app")
        product = make_obj(buildConfig={"targets": [{"role": "app", "processor": "nrf52840"}]})
        build_run = make_obj(stageConfigId="sc-1", builds=[build], product=product)
        stage_config = make_obj(
            buildMatrix=[{"role": "app", "label": "app"}],
            requiresFuota=False,
            stage=4,
        )
        db = MagicMock()
        db.buildrun.find_unique.return_value = build_run
        db.productstageconfig.find_unique.return_value = stage_config
        result = validate_build_run_artifacts(db, "run-1")
        # Missing CFW for stage >= 4
        assert result["valid"] is False
        cfw_missing = [m for m in result["missing"] if m["artifactType"] == "encryptedCfw"]
        assert len(cfw_missing) >= 1


# ---------------------------------------------------------------------------
# format_missing_artifacts_message
# ---------------------------------------------------------------------------

class TestFormatMissingMessage:
    def test_empty_returns_empty_string(self):
        assert format_missing_artifacts_message([]) == ""

    def test_formats_entries(self):
        missing = [
            {"label": "app", "role": "app", "artifactType": "plaintextHex"},
            {"label": "app", "role": "all", "artifactType": "manifest"},
        ]
        msg = format_missing_artifacts_message(missing)
        assert "Artifact validation failed" in msg
        assert "plaintextHex" in msg
        assert "manifest" in msg
