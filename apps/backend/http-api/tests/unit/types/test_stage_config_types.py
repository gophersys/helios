"""Tests for stage config request type validation."""
from api.v2.builds.stage_config_types import StageConfigCreateRequest, StageConfigUpdateRequest


class TestStageConfigCreateRequest:
    def test_valid_create(self):
        req, err = StageConfigCreateRequest.from_json({"stage": 1, "name": "Smoke"})
        assert err is None
        assert req.stage == 1
        assert req.name == "Smoke"
        assert req.enabled is False  # disabled by default

    def test_full_create(self):
        req, err = StageConfigCreateRequest.from_json({
            "stage": 5, "name": "FUOTA", "enabled": True,
            "boardRevisionId": "rev-1",
            "watchBranch": "develop",
            "signingKeyId": "key-1",
        })
        assert err is None
        assert req.stage == 5
        assert req.boardRevisionId == "rev-1"
        assert req.watchBranch == "develop"
        assert req.signingKeyId == "key-1"

    def test_optional_fields_default(self):
        req, err = StageConfigCreateRequest.from_json({"stage": 2, "name": "Driver"})
        assert err is None
        assert req.boardRevisionId is None
        assert req.watchBranch is None
        assert req.signingKeyId is None

    def test_missing_stage(self):
        _, err = StageConfigCreateRequest.from_json({"name": "Smoke"})
        assert "Stage" in err

    def test_invalid_stage(self):
        _, err = StageConfigCreateRequest.from_json({"stage": 99, "name": "Bad"})
        assert err is not None

    def test_wrong_name(self):
        _, err = StageConfigCreateRequest.from_json({"stage": 1, "name": "FUOTA"})
        assert "Smoke" in err

    def test_empty_body(self):
        _, err = StageConfigCreateRequest.from_json({})
        assert err is not None


class TestStageConfigUpdateRequest:
    def test_enable_toggle(self):
        req, err = StageConfigUpdateRequest.from_json({"enabled": True})
        assert err is None
        assert req.to_update_data() == {"enabled": True}

    def test_update_branch(self):
        req, err = StageConfigUpdateRequest.from_json({"watchBranch": "develop"})
        assert err is None
        assert req.to_update_data() == {"watchBranch": "develop"}

    def test_update_revision(self):
        req, err = StageConfigUpdateRequest.from_json({"boardRevisionId": "rev-2"})
        assert err is None
        assert req.to_update_data() == {"boardRevisionId": "rev-2"}

    def test_update_signing_key(self):
        req, err = StageConfigUpdateRequest.from_json({"signingKeyId": "key-2"})
        assert err is None
        assert req.to_update_data() == {"signingKeyId": "key-2"}

    def test_no_fields(self):
        _, err = StageConfigUpdateRequest.from_json({})
        assert "No fields" in err
