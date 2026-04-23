"""Unit tests for stage_assets.py — BuildAsset and StageAssets.

Uses StubArtifactResolver from stubs.py for all tests. No network access,
no MinIO, no API calls.

Run:
    PYTHONPATH=libs/python:libs:libs/protocols pytest libs/python/corekinect/test/tests/test_stage_assets.py -v
"""

import os

import pytest

from corekinect.errors import ConfigError
from corekinect.stages import Stage, get_required_labels
from corekinect.test.artifact_resolver import BuildManifest
from corekinect.test.stage_assets import (
    BuildAsset,
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
    """Resolver pre-loaded with smoke_app_debug and smoke_comms_debug builds."""
    resolver.add_build("smoke_app_debug", version="0.8.3", variant="debug", track="BM")
    resolver.add_build("smoke_comms_debug", version="0.8.3", variant="debug", track="BM")
    resolver.add_build("modem_fw", version="1.3.6", variant="release", track="BM")
    return resolver


@pytest.fixture
def fuota_resolver(resolver):
    """Resolver with all builds required by the fuota stage."""
    resolver.add_build("fut_app_base_a", version="0.5.0", variant="debug", track="BM")
    resolver.add_build("fut_app_base_b", version="0.5.1", variant="debug", track="BM")
    resolver.add_build("fut_app_quiet_a", version="0.5.0", variant="release", track="BM")
    resolver.add_build("fut_app_quiet_b", version="0.5.1", variant="release", track="BM")
    resolver.add_build("fut_comms_base_a", version="0.5.0", variant="debug", track="BM")
    resolver.add_build("fut_comms_base_b", version="0.5.1", variant="debug", track="BM")
    resolver.add_build("modem_fw", version="1.3.6", variant="release", track="BM")
    return resolver


# =============================================================================
# BuildAsset tests
# =============================================================================


class TestBuildAssetHex:
    """Tests for BuildAsset.hex() — plaintext hex resolution."""

    def test_hex_app_returns_existing_file(self, populated_resolver):
        """Test hex app returns existing file."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        path = asset.hex("app")
        assert os.path.isfile(path)

    def test_hex_comms_returns_different_path(self, populated_resolver):
        """Test hex comms returns different path."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        app_path = asset.hex("app")
        comms_path = asset.hex("comms")
        assert os.path.isfile(comms_path)
        assert app_path != comms_path

    def test_hex_nonexistent_role_raises_value_error(self, populated_resolver):
        """Test hex nonexistent role raises value error."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        with pytest.raises(ConfigError, match="No plaintext hex"):
            asset.hex("nonexistent_role")


class TestBuildAssetCfw:
    """Tests for BuildAsset.cfw() and cfws()."""

    def test_cfw_app_returns_existing_file(self, populated_resolver):
        """Test cfw app returns existing file."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        path = asset.cfw("app")
        assert os.path.isfile(path)

    def test_cfws_returns_two_paths(self, populated_resolver):
        """Test cfws returns two paths."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        paths = asset.cfws()
        assert len(paths) == 2
        for p in paths:
            assert os.path.isfile(p)

    def test_cfw_nonexistent_role_raises_value_error(self, resolver):
        """Test cfw nonexistent role raises value error."""
        # Build with no CFW for a nonexistent role
        resolver.add_build("test", version="1.0.0", variant="debug", track="BM")
        asset = BuildAsset(label="test", resolver=resolver)
        with pytest.raises(ConfigError, match="No encrypted CFW"):
            asset.cfw("nonexistent_role")


class TestBuildAssetVersion:
    """Tests for version-related accessors."""

    def test_version_returns_string(self, populated_resolver):
        """Test version returns string."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        assert asset.version() == "0.8.3"

    def test_version_string_app(self, populated_resolver):
        """Test version string app."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        vs = asset.version_string("app")
        assert vs == "109.0.8.3-BM"

    def test_version_string_comms(self, populated_resolver):
        """Test version string comms."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        vs = asset.version_string("comms")
        assert vs == "108.0.8.3-BM"

    def test_version_string_bad_role_raises(self, populated_resolver):
        """Test version string bad role raises."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        with pytest.raises(ConfigError, match="No target"):
            asset.version_string("bad_role")


class TestBuildAssetTargetStrings:
    """Tests for target_strings() — all CK version strings."""

    def test_target_strings_returns_list(self, populated_resolver):
        """Test target strings returns list."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        ts = asset.target_strings()
        assert isinstance(ts, list)
        assert len(ts) == 2
        assert "108.0.8.3-BM" in ts
        assert "109.0.8.3-BM" in ts


class TestBuildAssetManifest:
    """Tests for manifest() caching and target access."""

    def test_manifest_returns_build_manifest(self, populated_resolver):
        """Test manifest returns build manifest."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        m = asset.manifest()
        assert isinstance(m, BuildManifest)

    def test_manifest_is_cached(self, populated_resolver):
        """Test manifest is cached."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        m1 = asset.manifest()
        m2 = asset.manifest()
        assert m1 is m2

    def test_targets_returns_list(self, populated_resolver):
        """Test targets returns list."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        targets = asset.targets()
        assert len(targets) == 2

    def test_target_app_found(self, populated_resolver):
        """Test target app found."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        t = asset.target("app")
        assert t.role == "app"
        assert t.app_id == 109

    def test_target_bad_role_raises(self, populated_resolver):
        """Test target bad role raises."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        with pytest.raises(ConfigError, match="No target 'bad'"):
            asset.target("bad")

    def test_app_ids_returns_set(self, populated_resolver):
        """Test app ids returns set."""
        asset = BuildAsset(label="smoke_app_debug", resolver=populated_resolver)
        ids = asset.app_ids()
        assert ids == {108, 109}


# =============================================================================
# StageAssets tests
# =============================================================================


class TestStageAssetsConstruction:
    """Tests for StageAssets constructor and validation."""

    def test_all_labels_present_no_error(self, populated_resolver):
        """Test all labels present no error."""
        assets = StageAssets(populated_resolver, stage="smoke", strict=True)
        assert assets.stage == "smoke"

    def test_missing_label_strict_raises(self, resolver):
        """Test missing label strict raises."""
        resolver.add_build("smoke_app_debug", version="0.8.3", variant="debug", track="BM")
        with pytest.raises(ConfigError, match="missing required builds"):
            StageAssets(resolver, stage="smoke", strict=True)

    def test_missing_label_non_strict_no_error(self, resolver):
        """Test missing label non strict no error."""
        resolver.add_build("smoke_app_debug", version="0.8.3", variant="debug", track="BM")
        assets = StageAssets(resolver, stage="smoke", strict=False)
        missing = assets.missing_labels()
        assert "smoke_comms_debug" in missing

    def test_missing_labels_empty_when_all_present(self, populated_resolver):
        """Test missing labels empty when all present."""
        assets = StageAssets(populated_resolver, stage="smoke", strict=True)
        assert assets.missing_labels() == []


class TestStageAssetsLabelAccess:
    """Tests for by_label and convenience shortcuts."""

    def test_by_label_returns_build_asset(self, populated_resolver):
        """Test by label returns build asset."""
        assets = StageAssets(populated_resolver, stage="smoke")
        ba = assets.by_label("smoke_app_debug")
        assert isinstance(ba, BuildAsset)
        assert ba.label == "smoke_app_debug"

    def test_by_label_nonexistent_raises_key_error(self, populated_resolver):
        """Test by label nonexistent raises key error."""
        assets = StageAssets(populated_resolver, stage="smoke")
        with pytest.raises(KeyError, match="nonexistent"):
            assets.by_label("nonexistent")

    def test_hex_resolves_label_and_downloads(self, populated_resolver):
        """Test hex() resolves the correct label and downloads."""
        assets = StageAssets(populated_resolver, stage="smoke")
        path = assets.hex("app", "debug")
        assert os.path.isfile(path)

    def test_hex_pair_returns_both(self, populated_resolver):
        """Test hex_pair() returns app and comms hex paths."""
        assets = StageAssets(populated_resolver, stage="smoke")
        app_hex, comms_hex = assets.hex_pair("debug")
        assert os.path.isfile(app_hex)
        assert os.path.isfile(comms_hex)
        assert app_hex != comms_hex

    def test_stage_prefix_detected(self, populated_resolver):
        """Test stage_prefix is auto-detected from labels."""
        assets = StageAssets(populated_resolver, stage="smoke")
        assert assets.stage_prefix == "smoke"

    def test_available_variants_detected(self, resolver):
        """Test available_variants detects debug and release."""
        resolver.add_build("driver_app_debug", version="0.8.3", variant="debug", track="BM")
        resolver.add_build("driver_app_release", version="0.8.3", variant="release", track="BM")
        resolver.add_build("driver_comms_debug", version="0.8.3", variant="debug", track="BM")
        resolver.add_build("driver_comms_release", version="0.8.3", variant="release", track="BM")
        resolver.add_build("modem_fw", version="1.3.6", variant="release", track="BM")
        assets = StageAssets(resolver, stage="driver")
        assert assets.available_variants == ["debug", "release"]

    def test_fuota_hex_with_suffix(self, fuota_resolver):
        """Test hex() with suffix for FUOTA transitions."""
        assets = StageAssets(fuota_resolver, stage="fuota")
        path = assets.hex("app", "debug", "A")
        assert os.path.isfile(path)


class TestStageAssetsModem:
    """Tests for modem_zip() resolution."""

    def test_modem_zip_from_build(self, resolver):
        """Test modem zip from build."""
        resolver.add_build(
            "smoke_app_debug", version="0.8.3", variant="debug", track="BM",
            modem_firmware="/tmp/modem.zip",
        )
        resolver.add_build("smoke_comms_debug", version="0.8.3", variant="debug", track="BM")
        resolver.add_build("modem_fw", version="1.3.6", variant="release", track="BM")
        assets = StageAssets(resolver, stage="smoke")
        path = assets.modem_zip()
        assert path == "/tmp/modem.zip"

    def test_modem_zip_none_when_not_available(self, populated_resolver):
        """Test modem zip none when not available."""
        assets = StageAssets(populated_resolver, stage="smoke")
        path = assets.modem_zip()
        assert path is None


class TestStageAssetsLabelsProperty:
    """Tests for labels and required_labels properties."""

    def test_labels_returns_sorted(self, populated_resolver):
        """Test labels returns sorted."""
        assets = StageAssets(populated_resolver, stage="smoke")
        labels = assets.labels
        assert labels == sorted(labels)
        assert "smoke_app_debug" in labels
        assert "smoke_comms_debug" in labels

    def test_required_labels_returns_stage_labels(self, populated_resolver):
        """Test required labels returns stage labels."""
        assets = StageAssets(populated_resolver, stage="smoke")
        required = assets.required_labels
        assert required == get_required_labels(Stage.SMOKE)


class TestStageAssetsValidation:
    """Tests for validate() with failed builds."""

    def test_validate_raises_on_failed_build(self, resolver):
        """Test validate raises on failed build."""
        resolver.add_build(
            "smoke_app_debug", version="0.8.3", variant="debug", track="BM",
            status="FAILED",
        )
        resolver.add_build("smoke_comms_debug", version="0.8.3", variant="debug", track="BM")
        resolver.add_build("modem_fw", version="1.3.6", variant="release", track="BM")
        with pytest.raises(ConfigError, match="failed builds"):
            StageAssets(resolver, stage="smoke", strict=True)

    def test_validate_passes_with_cached_status(self, resolver):
        """Test validate passes with cached status."""
        resolver.add_build(
            "smoke_app_debug", version="0.8.3", variant="debug", track="BM",
            status="CACHED",
        )
        resolver.add_build("smoke_comms_debug", version="0.8.3", variant="debug", track="BM")
        resolver.add_build("modem_fw", version="1.3.6", variant="release", track="BM")
        # Should not raise
        assets = StageAssets(resolver, stage="smoke", strict=True)
        assert assets.missing_labels() == []


# =============================================================================
# get_required_labels tests
# =============================================================================


class TestGetRequiredLabels:
    """Tests for get_required_labels from stages module."""

    def test_all_stages_have_labels(self):
        """Test all validation stages have required labels."""
        for stage in (Stage.SMOKE, Stage.DRIVER, Stage.INTEGRATION, Stage.REGRESSION, Stage.FUOTA):
            labels = get_required_labels(stage)
            assert len(labels) > 0, f"Stage '{stage.value}' has no required labels"

    def test_fuota_has_seven_labels(self):
        """Test fuota has seven labels."""
        assert len(get_required_labels(Stage.FUOTA)) == 7

    def test_smoke_has_three_labels(self):
        """Test smoke has three labels."""
        assert len(get_required_labels(Stage.SMOKE)) == 3
