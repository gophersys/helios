"""Tests for stage config request type validation."""
import pytest
from api.v2.builds.stage_config_types import StageConfigCreateRequest, StageConfigUpdateRequest


class TestStageConfigCreateRequest:
    def test_valid_create(self):
        req, err = StageConfigCreateRequest.from_json({
            "stage": 1,
            "name": "Smoke",
        })
        assert err is None
        assert req.stage == 1
        assert req.name == "Smoke"
        assert req.enabled is True
        assert req.priority == 50

    def test_missing_stage(self):
        _, err = StageConfigCreateRequest.from_json({"name": "Smoke"})
        assert err is not None
        assert "stage" in err.lower()

    def test_invalid_stage_range(self):
        _, err = StageConfigCreateRequest.from_json({"stage": 0, "name": "X"})
        assert err is not None
        _, err = StageConfigCreateRequest.from_json({"stage": 6, "name": "X"})
        assert err is not None

    def test_missing_name(self):
        _, err = StageConfigCreateRequest.from_json({"stage": 1})
        assert err is not None
        assert "name" in err.lower()

    def test_empty_body(self):
        _, err = StageConfigCreateRequest.from_json(None)
        assert err is not None

    def test_full_create(self):
        req, err = StageConfigCreateRequest.from_json({
            "stage": 5,
            "name": "Gate",
            "enabled": True,
            "buildTarget": "alpha_b0",
            "fwRepoUrl": "git@bb:ck/alpha_fw.git",
            "fwRepoBranch": "main",
            "mfgRepoUrl": "git@bb:ck/alpha_mfg_fw.git",
            "buildVariant": "release",
            "configFlags": {"harness": False},
            "testDirectory": "tests/stage5/",
            "testTimeout": 900,
            "priority": 100,
            "blocksMerge": True,
            "requiresFuota": True,
            "requiresBench": True,
            "maxDurationSec": 900,
            "description": "PR gate with FUOTA",
        })
        assert err is None
        assert req.stage == 5
        assert req.priority == 100
        assert req.requiresFuota is True

    def test_optional_fields_default(self):
        req, err = StageConfigCreateRequest.from_json({"stage": 3, "name": "Integration"})
        assert err is None
        assert req.buildScript is None
        assert req.testTimeout == 900
        assert req.blocksMerge is False
        assert req.requiresFuota is False


class TestStageConfigUpdateRequest:
    def test_valid_update(self):
        req, err = StageConfigUpdateRequest.from_json({"enabled": False})
        assert err is None
        assert req.enabled is False

    def test_empty_update(self):
        _, err = StageConfigUpdateRequest.from_json({})
        assert err is not None
        assert "no fields" in err.lower()

    def test_update_priority(self):
        req, err = StageConfigUpdateRequest.from_json({"priority": 100})
        assert err is None
        assert req.priority == 100

    def test_null_body(self):
        _, err = StageConfigUpdateRequest.from_json(None)
        assert err is not None
