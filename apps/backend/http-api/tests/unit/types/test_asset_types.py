"""Unit tests for asset types validation in src/api/v2/assets/types.py."""


# ── AssetSetCreateRequest ─────────────────────────────


def test_asset_set_create_valid():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {
        "version": "1.2.3",
        "variant": "release",
        "source": "BUILD_SERVICE",
        "stage": 3,
        "commitSha": "abc123",
        "branch": "main",
        "notes": "First build",
    }
    req, err = AssetSetCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "1.2.3"
    assert req.variant == "release"
    assert req.source == "BUILD_SERVICE"
    assert req.stage == 3
    assert req.commitSha == "abc123"
    assert req.branch == "main"
    assert req.notes == "First build"


def test_asset_set_create_minimal():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "0.1.0"}
    req, err = AssetSetCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "0.1.0"
    assert req.variant == "debug"
    assert req.source == "MANUAL_UPLOAD"
    assert req.stage is None
    assert req.commitSha is None


def test_asset_set_create_missing_version():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"variant": "debug"}
    req, err = AssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_asset_set_create_empty_version():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "   "}
    req, err = AssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_asset_set_create_empty_body():
    from src.api.v2.assets.types import AssetSetCreateRequest

    req, err = AssetSetCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = AssetSetCreateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_asset_set_create_invalid_source():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "1.0.0", "source": "GITHUB"}
    req, err = AssetSetCreateRequest.from_json(data)

    assert req is None
    assert "Invalid source" in err


def test_asset_set_create_invalid_stage_too_low():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "1.0.0", "stage": 0}
    req, err = AssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Stage must be an integer between 1 and 5"


def test_asset_set_create_invalid_stage_too_high():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "1.0.0", "stage": 6}
    req, err = AssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Stage must be an integer between 1 and 5"


def test_asset_set_create_stage_not_int():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "1.0.0", "stage": "three"}
    req, err = AssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Stage must be an integer between 1 and 5"


def test_asset_set_create_source_case_insensitive():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "1.0.0", "source": "build_service"}
    req, err = AssetSetCreateRequest.from_json(data)

    assert err is None
    assert req.source == "BUILD_SERVICE"


def test_asset_set_create_whitespace_optional_fields_become_none():
    from src.api.v2.assets.types import AssetSetCreateRequest

    data = {"version": "1.0.0", "commitSha": "  ", "branch": "  ", "notes": "  "}
    req, err = AssetSetCreateRequest.from_json(data)

    assert err is None
    assert req.commitSha is None
    assert req.branch is None
    assert req.notes is None


# ── ExternalAssetSetCreateRequest ─────────────────────


def test_external_asset_set_create_valid():
    from src.api.v2.assets.types import ExternalAssetSetCreateRequest

    data = {
        "version": "2.0.0",
        "externalBuildId": "ext-build-42",
        "variant": "release",
        "stage": 5,
    }
    req, err = ExternalAssetSetCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "2.0.0"
    assert req.externalBuildId == "ext-build-42"
    assert req.variant == "release"
    assert req.stage == 5


def test_external_asset_set_create_missing_version():
    from src.api.v2.assets.types import ExternalAssetSetCreateRequest

    data = {"externalBuildId": "ext-1"}
    req, err = ExternalAssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_external_asset_set_create_missing_external_build_id():
    from src.api.v2.assets.types import ExternalAssetSetCreateRequest

    data = {"version": "1.0.0"}
    req, err = ExternalAssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "externalBuildId is required"


def test_external_asset_set_create_empty_body():
    from src.api.v2.assets.types import ExternalAssetSetCreateRequest

    req, err = ExternalAssetSetCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = ExternalAssetSetCreateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_external_asset_set_create_invalid_stage():
    from src.api.v2.assets.types import ExternalAssetSetCreateRequest

    data = {"version": "1.0.0", "externalBuildId": "ext-1", "stage": 0}
    req, err = ExternalAssetSetCreateRequest.from_json(data)

    assert req is None
    assert err == "Stage must be an integer between 1 and 5"


def test_external_asset_set_create_minimal():
    from src.api.v2.assets.types import ExternalAssetSetCreateRequest

    data = {"version": "1.0.0", "externalBuildId": "ext-1"}
    req, err = ExternalAssetSetCreateRequest.from_json(data)

    assert err is None
    assert req.variant == "debug"
    assert req.stage is None
    assert req.boardRevisionId is None
