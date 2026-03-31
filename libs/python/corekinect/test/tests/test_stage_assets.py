"""Unit tests for stage_assets.py — BuildAsset and StageAssets.

Uses StubArtifactResolver from stubs.py for all tests. No network access,
no MinIO, no API calls.

Run:
    PYTHONPATH=libs/python:libs:libs/protocols pytest libs/python/corekinect/test/tests/test_stage_assets.py -v
"""

import os

import pytest

from corekinect.test.errors import ConfigError
from corekinect.test.stage_assets import (
    BuildAsset,
    STAGE_REQUIRED_LABELS,
    StageAssets,
)
from corekinect.test.tests.stubs import StubArtifactResolver


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def resolver():
    """Fresh StubArtifactResolver with cleanup."""
    r = StubArtifactResolver()
    yield r
    r.cleanup()


@pytest.fixture
def populated_resolver(resolver):
    """Resolver pre-loaded with MFG_BASE and APP_DEBUG builds."""
    resolver.add_build("MFG_BASE", version="0.8.3", variant="mfg", track="BM")
    resolver.add_build("APP_DEBUG", version="0.8.3", variant="debug", track="BM")
    return resolver


@pytest.fixture
def fuota_resolver(resolver):
    """Resolver with all builds required by the fuota stage."""
    resolver.add_build("MFG_BASE", version="0.8.3", variant="mfg", track="BM")
    resolver.add_build("MFG_BUMP", version="0.8.4", variant="mfg", track="BM")
    resolver.add_build("FUT_DEBUG_A", version="0.5.0", variant="debug", track="BM")
    resolver.add_build("FUT_DEBUG_B", version="0.5.1", variant="debug", track="BM")
    resolver.add_build("FUT_RELEASE_A", version="0.5.0", variant="release", track="BM")
    resolver.add_build("FUT_RELEASE_B", version="0.5.1", variant="release", track="BM")
    resolver.add_build("MAIN_BASELINE", version="0.8.2", variant="release", track="BM")
    resolver.add_build("MAIN_MERGED", version="0.8.3", variant="release", track="BM")
    return resolver


# =============================================================================
# BuildAsset tests
# =============================================================================


class TestBuildAssetHex:
    """Tests for BuildAsset.hex() — plaintext hex resolution."""

    def test_hex_app_returns_existing_file(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        path = asset.hex("app")
        assert os.path.isfile(path)

    def test_hex_comms_returns_different_path(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        app_path = asset.hex("app")
        comms_path = asset.hex("comms")
        assert os.path.isfile(comms_path)
        assert app_path != comms_path

    def test_hex_nonexistent_role_raises_value_error(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        with pytest.raises(ConfigError, match="No plaintext hex"):
            asset.hex("nonexistent_role")


class TestBuildAssetCfw:
    """Tests for BuildAsset.cfw() and cfws()."""

    def test_cfw_app_returns_existing_file(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        path = asset.cfw("app")
        assert os.path.isfile(path)

    def test_cfws_returns_two_paths(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        paths = asset.cfws()
        assert len(paths) == 2
        for p in paths:
            assert os.path.isfile(p)

    def test_cfw_nonexistent_role_raises_value_error(self, resolver):
        # Build with no CFW for a nonexistent role
        resolver.add_build("TEST", version="1.0.0", variant="debug", track="BM")
        asset = BuildAsset(label="TEST", resolver=resolver)
        with pytest.raises(ConfigError, match="No encrypted CFW"):
            asset.cfw("nonexistent_role")


class TestBuildAssetVersion:
    """Tests for version-related accessors."""

    def test_version_returns_string(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        assert asset.version() == "0.8.3"

    def test_version_string_app(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        vs = asset.version_string("app")
        assert vs == "109.0.8.3-BM"

    def test_version_string_comms(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        vs = asset.version_string("comms")
        assert vs == "108.0.8.3-BM"

    def test_version_string_bad_role_raises(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        with pytest.raises(ConfigError, match="No target"):
            asset.version_string("bad_role")


class TestBuildAssetTargetStrings:
    """Tests for target_strings() — all CK version strings."""

    def test_target_strings_returns_list(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        ts = asset.target_strings()
        assert isinstance(ts, list)
        assert len(ts) == 2
        assert "108.0.8.3-BM" in ts
        assert "109.0.8.3-BM" in ts


class TestBuildAssetManifest:
    """Tests for manifest() caching and target access."""

    def test_manifest_returns_build_manifest(self, populated_resolver):
        from corekinect.test.artifact_resolver import BuildManifest

        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        m = asset.manifest()
        assert isinstance(m, BuildManifest)

    def test_manifest_is_cached(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        m1 = asset.manifest()
        m2 = asset.manifest()
        assert m1 is m2

    def test_targets_returns_list(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        targets = asset.targets()
        assert len(targets) == 2

    def test_target_app_found(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        t = asset.target("app")
        assert t.role == "app"
        assert t.app_id == 109

    def test_target_bad_role_raises(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        with pytest.raises(ConfigError, match="No target 'bad'"):
            asset.target("bad")

    def test_app_ids_returns_set(self, populated_resolver):
        asset = BuildAsset(label="MFG_BASE", resolver=populated_resolver)
        ids = asset.app_ids()
        assert ids == {108, 109}


# =============================================================================
# StageAssets tests
# =============================================================================


class TestStageAssetsConstruction:
    """Tests for StageAssets constructor and validation."""

    def test_all_labels_present_no_error(self, populated_resolver):
        # smoke requires MFG_BASE and APP_DEBUG — both present
        assets = StageAssets(populated_resolver, stage="smoke", strict=True)
        assert assets.stage == "smoke"

    def test_missing_label_strict_raises(self, resolver):
        # smoke needs MFG_BASE + APP_DEBUG, only provide MFG_BASE
        resolver.add_build("MFG_BASE", version="0.8.3", variant="mfg", track="BM")
        with pytest.raises(ConfigError, match="missing required builds"):
            StageAssets(resolver, stage="smoke", strict=True)

    def test_missing_label_non_strict_no_error(self, resolver):
        resolver.add_build("MFG_BASE", version="0.8.3", variant="mfg", track="BM")
        assets = StageAssets(resolver, stage="smoke", strict=False)
        missing = assets.missing_labels()
        assert "APP_DEBUG" in missing

    def test_missing_labels_empty_when_all_present(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke", strict=True)
        assert assets.missing_labels() == []


class TestStageAssetsLabelAccess:
    """Tests for by_label and convenience shortcuts."""

    def test_by_label_returns_build_asset(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        ba = assets.by_label("MFG_BASE")
        assert isinstance(ba, BuildAsset)
        assert ba.label == "MFG_BASE"

    def test_by_label_nonexistent_raises_key_error(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        with pytest.raises(KeyError, match="NONEXISTENT"):
            assets.by_label("NONEXISTENT")

    def test_mfg_shortcut(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        mfg = assets.mfg()
        assert mfg.label == "MFG_BASE"

    def test_mfg_bump_shortcut(self, fuota_resolver):
        assets = StageAssets(fuota_resolver, stage="fuota")
        bump = assets.mfg_bump()
        assert bump.label == "MFG_BUMP"
        assert bump.version() == "0.8.4"

    def test_app_debug_shortcut(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        debug = assets.app_debug()
        assert debug.label == "APP_DEBUG"

    def test_app_release_shortcut(self, resolver):
        resolver.add_build("MFG_BASE", version="0.8.3", variant="mfg", track="BM")
        resolver.add_build("APP_DEBUG", version="0.8.3", variant="debug", track="BM")
        resolver.add_build("APP_RELEASE", version="0.8.3", variant="release", track="BM")
        assets = StageAssets(resolver, stage="silicon")
        release = assets.app_release()
        assert release.label == "APP_RELEASE"


class TestStageAssetsModem:
    """Tests for modem_zip() resolution."""

    def test_modem_zip_from_build(self, resolver):
        resolver.add_build(
            "MFG_BASE", version="0.8.3", variant="mfg", track="BM",
            modem_firmware="/tmp/modem.zip",
        )
        resolver.add_build("APP_DEBUG", version="0.8.3", variant="debug", track="BM")
        assets = StageAssets(resolver, stage="smoke")
        path = assets.modem_zip()
        assert path == "/tmp/modem.zip"

    def test_modem_zip_none_when_not_available(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        path = assets.modem_zip()
        assert path is None


class TestStageAssetsLabelsProperty:
    """Tests for labels and required_labels properties."""

    def test_labels_returns_sorted(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        labels = assets.labels
        assert labels == sorted(labels)
        assert "APP_DEBUG" in labels
        assert "MFG_BASE" in labels

    def test_required_labels_returns_stage_labels(self, populated_resolver):
        assets = StageAssets(populated_resolver, stage="smoke")
        required = assets.required_labels
        assert required == STAGE_REQUIRED_LABELS["smoke"]


class TestStageAssetsValidation:
    """Tests for validate() with failed builds."""

    def test_validate_raises_on_failed_build(self, resolver):
        resolver.add_build(
            "MFG_BASE", version="0.8.3", variant="mfg", track="BM",
            status="FAILED",
        )
        resolver.add_build("APP_DEBUG", version="0.8.3", variant="debug", track="BM")
        with pytest.raises(ConfigError, match="failed builds"):
            StageAssets(resolver, stage="smoke", strict=True)

    def test_validate_passes_with_cached_status(self, resolver):
        resolver.add_build(
            "MFG_BASE", version="0.8.3", variant="mfg", track="BM",
            status="CACHED",
        )
        resolver.add_build("APP_DEBUG", version="0.8.3", variant="debug", track="BM")
        # Should not raise
        assets = StageAssets(resolver, stage="smoke", strict=True)
        assert assets.missing_labels() == []


# =============================================================================
# STAGE_REQUIRED_LABELS tests
# =============================================================================


class TestStageRequiredLabels:
    """Tests for the STAGE_REQUIRED_LABELS constant."""

    def test_all_five_stages_have_entries(self):
        expected_stages = {"smoke", "silicon", "integration", "nightly", "fuota"}
        assert set(STAGE_REQUIRED_LABELS.keys()) == expected_stages

    def test_each_stage_has_non_empty_labels(self):
        for stage, labels in STAGE_REQUIRED_LABELS.items():
            assert len(labels) > 0, f"Stage '{stage}' has no required labels"

    def test_fuota_has_eight_labels(self):
        assert len(STAGE_REQUIRED_LABELS["fuota"]) == 8

    def test_smoke_has_two_labels(self):
        assert len(STAGE_REQUIRED_LABELS["smoke"]) == 2
