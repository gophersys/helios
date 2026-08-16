"""Tests for stage config request type validation."""
from api.v2.builds.stage_config_types import StageConfigCreateRequest, StageConfigUpdateRequest


class TestStageConfigCreateRequest:
    def test_valid_create(self):
        req, err = StageConfigCreateRequest.from_json({"type": "VALIDATION", "stage": 1, "name": "Smoke"})
        assert err is None
        assert req.type == "VALIDATION"
        assert req.stage == 1
        assert req.name == "Smoke"
        assert req.enabled is False  # disabled by default

    def test_full_create(self):
        req, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 5, "name": "FUOTA", "enabled": True,
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
        req, err = StageConfigCreateRequest.from_json({"type": "VALIDATION", "stage": 2, "name": "Driver"})
        assert err is None
        assert req.boardRevisionId is None
        assert req.watchBranch is None
        assert req.signingKeyId is None

    def test_missing_stage(self):
        _, err = StageConfigCreateRequest.from_json({"type": "VALIDATION", "name": "Smoke"})
        assert "stage" in err.lower()

    def test_invalid_stage(self):
        _, err = StageConfigCreateRequest.from_json({"type": "VALIDATION", "stage": 99, "name": "Bad"})
        assert err is not None

    def test_wrong_name(self):
        """Name is no longer validated against stage — auto-derives if empty, accepts any if provided."""
        req, err = StageConfigCreateRequest.from_json({"type": "VALIDATION", "stage": 1, "name": "FUOTA"})
        # Name is accepted as-is (no longer enforces stage-to-name mapping)
        assert err is None
        assert req.name == "FUOTA"

    def test_empty_body(self):
        _, err = StageConfigCreateRequest.from_json({})
        assert err is not None

    def test_manufacturing_type(self):
        req, err = StageConfigCreateRequest.from_json({"type": "MANUFACTURING", "stage": 1})
        assert err is None
        assert req.type == "MANUFACTURING"
        assert req.name == "Manufacturing"  # auto-derived

    def test_type_defaults_to_validation(self):
        req, err = StageConfigCreateRequest.from_json({"stage": 1, "name": "Smoke"})
        assert err is None
        assert req.type == "VALIDATION"

    # ── assetSources (create) ────────────────────────────

    def test_asset_sources_defaults_to_build_service(self):
        req, err = StageConfigCreateRequest.from_json({"type": "VALIDATION", "stage": 1, "name": "Smoke"})
        assert err is None
        assert req.assetSources == ["BUILD_SERVICE"]

    def test_asset_sources_array(self):
        req, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": ["BUILD_SERVICE", "MANUAL_UPLOAD"],
        })
        assert err is None
        assert req.assetSources == ["BUILD_SERVICE", "MANUAL_UPLOAD"]

    def test_asset_sources_string_auto_wrapped(self):
        req, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": "EXTERNAL_CI",
        })
        assert err is None
        assert req.assetSources == ["EXTERNAL_CI"]

    def test_asset_sources_invalid_rejected(self):
        _, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": ["BUILD_SERVICE", "INVALID_SOURCE"],
        })
        assert err is not None
        assert "INVALID_SOURCE" in err

    def test_asset_sources_not_array_or_string_rejected(self):
        _, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": 42,
        })
        assert err is not None
        assert "array" in err.lower()

    def test_asset_sources_case_insensitive(self):
        req, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": ["build_service"],
        })
        assert err is None
        assert req.assetSources == ["BUILD_SERVICE"]

    def test_asset_sources_empty_array_defaults(self):
        req, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": [],
        })
        assert err is None
        assert req.assetSources == ["BUILD_SERVICE"]

    def test_asset_sources_all_valid_values(self):
        req, err = StageConfigCreateRequest.from_json({
            "type": "VALIDATION", "stage": 1, "name": "Smoke",
            "assetSources": ["BUILD_SERVICE", "MANUAL_UPLOAD", "EXTERNAL_CI"],
        })
        assert err is None
        assert set(req.assetSources) == {"BUILD_SERVICE", "MANUAL_UPLOAD", "EXTERNAL_CI"}


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
        assert req.to_update_data() == {"boardRevision": {"connect": {"id": "rev-2"}}}

    def test_update_revision_disconnect(self):
        req, err = StageConfigUpdateRequest.from_json({"boardRevisionId": None})
        assert err is None
        assert req.to_update_data() == {"boardRevision": {"disconnect": True}}

    def test_update_signing_key(self):
        req, err = StageConfigUpdateRequest.from_json({"signingKeyId": "key-2"})
        assert err is None
        assert req.to_update_data() == {"signingKey": {"connect": {"id": "key-2"}}}

    def test_update_signing_key_disconnect(self):
        req, err = StageConfigUpdateRequest.from_json({"signingKeyId": None})
        assert err is None
        assert req.to_update_data() == {"signingKey": {"disconnect": True}}

    def test_no_fields(self):
        _, err = StageConfigUpdateRequest.from_json({})
        assert "No fields" in err

    # ── assetSources (update) ────────────────────────────

    def test_update_asset_sources_array(self):
        req, err = StageConfigUpdateRequest.from_json({
            "assetSources": ["BUILD_SERVICE", "EXTERNAL_CI"],
        })
        assert err is None
        assert req.assetSources == ["BUILD_SERVICE", "EXTERNAL_CI"]
        update = req.to_update_data()
        assert update["assetSources"] == ["BUILD_SERVICE", "EXTERNAL_CI"]

    def test_update_asset_sources_string_auto_wrapped(self):
        req, err = StageConfigUpdateRequest.from_json({
            "assetSources": "MANUAL_UPLOAD",
        })
        assert err is None
        assert req.assetSources == ["MANUAL_UPLOAD"]

    def test_update_asset_sources_invalid_rejected(self):
        _, err = StageConfigUpdateRequest.from_json({
            "assetSources": ["NOPE"],
        })
        assert err is not None
        assert "NOPE" in err

    def test_update_asset_sources_not_array_rejected(self):
        _, err = StageConfigUpdateRequest.from_json({
            "assetSources": 123,
        })
        assert err is not None
        assert "array" in err.lower()

    def test_update_asset_sources_empty_array_rejected(self):
        _, err = StageConfigUpdateRequest.from_json({
            "assetSources": [],
        })
        assert err is not None
        assert "at least one" in err.lower()

    def test_update_asset_sources_case_insensitive(self):
        req, err = StageConfigUpdateRequest.from_json({
            "assetSources": ["external_ci"],
        })
        assert err is None
        assert req.assetSources == ["EXTERNAL_CI"]

    def test_update_asset_sources_null_allowed(self):
        """Setting assetSources to None clears it via to_update_data."""
        req, err = StageConfigUpdateRequest.from_json({
            "assetSources": None,
            "enabled": True,  # need at least one real field
        })
        assert err is None
        assert req.assetSources is None
        # _has_asset_sources is True because key was present
        update = req.to_update_data()
        assert "assetSources" in update
        assert update["assetSources"] is None

    def test_update_asset_sources_not_included_when_omitted(self):
        """When assetSources key is absent, it is not in to_update_data."""
        req, err = StageConfigUpdateRequest.from_json({"enabled": True})
        assert err is None
        update = req.to_update_data()
        assert "assetSources" not in update
