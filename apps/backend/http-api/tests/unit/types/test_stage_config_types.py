"""Tests for stage config request type validation."""
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

    def test_full_create(self):
        req, err = StageConfigCreateRequest.from_json({
            "stage": 5, "name": "FUOTA", "enabled": True,
            "boardRevisionId": "rev-1",
            "testDirectory": "tests/fuota/", "testMarker": "-m fuota",
            "testTimeout": 600, "priority": 100,
            "blocksMerge": True, "autoProgress": True,
            "requiresBench": True, "maxDurationSec": 900,
            "description": "FUOTA stage",
        })
        assert err is None
        assert req.stage == 5
        assert req.boardRevisionId == "rev-1"
        assert req.autoProgress is True
        assert req.testTimeout == 600

    def test_optional_fields_default(self):
        req, err = StageConfigCreateRequest.from_json({
            "stage": 2, "name": "Silicon",
        })
        assert err is None
        assert req.boardRevisionId is None
        assert req.testDirectory is None
        assert req.autoProgress is False
        assert req.requiresBench is True
        assert req.testTimeout == 900

    def test_missing_stage(self):
        _, err = StageConfigCreateRequest.from_json({"name": "Smoke"})
        assert err is not None
        assert "Stage" in err

    def test_invalid_stage(self):
        _, err = StageConfigCreateRequest.from_json({"stage": 99, "name": "Bad"})
        assert err is not None

    def test_wrong_name_for_stage(self):
        _, err = StageConfigCreateRequest.from_json({"stage": 1, "name": "FUOTA"})
        assert err is not None
        assert "Smoke" in err

    def test_empty_body(self):
        _, err = StageConfigCreateRequest.from_json({})
        assert err is not None


class TestStageConfigUpdateRequest:
    def test_enable_toggle(self):
        req, err = StageConfigUpdateRequest.from_json({"enabled": False})
        assert err is None
        data = req.to_update_data()
        assert data == {"enabled": False}

    def test_update_test_config(self):
        req, err = StageConfigUpdateRequest.from_json({
            "testDirectory": "tests/new/",
            "testMarker": "-m new",
            "testTimeout": 300,
        })
        assert err is None
        data = req.to_update_data()
        assert data["testDirectory"] == "tests/new/"
        assert data["testTimeout"] == 300

    def test_update_revision(self):
        req, err = StageConfigUpdateRequest.from_json({
            "boardRevisionId": "rev-2",
        })
        assert err is None
        data = req.to_update_data()
        assert data["boardRevisionId"] == "rev-2"

    def test_no_fields(self):
        _, err = StageConfigUpdateRequest.from_json({})
        assert err is not None
        assert "No fields" in err
