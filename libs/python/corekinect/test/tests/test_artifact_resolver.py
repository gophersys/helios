"""Unit tests for ArtifactResolver."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from corekinect.test.artifact_resolver import (
    ArtifactResolver,
    BuildManifest,
    ManifestTarget,
    ResolvedArtifact,
    StorageConfig,
)


# =============================================================================
# FIXTURES
# =============================================================================


ALPHA_MANIFEST = {
    "schemaVersion": 1,
    "product": "alpha",
    "board": "alpha_b0",
    "version": "0.8.3",
    "variant": "mfg",
    "track": "BM",
    "releaseTrack": "bench",
    "ncsVersion": "v2.9.0",
    "commitSha": "abc1234def5678",
    "branch": "main",
    "builtAt": "2026-03-26T18:30:00Z",
    "targets": [
        {
            "role": "app",
            "processor": "nrf52840",
            "appId": 109,
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
            "plaintextHex": "hex/109.0.8.3-BM.hex",
            "encryptedCfw": "cfw/109.0.8.3-BM.cfw",
        },
        {
            "role": "comms",
            "processor": "nrf9151",
            "appId": 108,
            "hostType": "HOST_TYPE_NRF9151",
            "jlinkFamily": "NRF91",
            "plaintextHex": "hex/108.0.8.3-BM.hex",
            "encryptedCfw": "cfw/108.0.8.3-BM.cfw",
        },
    ],
    "modemFirmware": {
        "chipset": "nrf9151",
        "file": "modem/mfw_nrf91x1_2.0.2.zip",
        "hostType": "HOST_TYPE_NRF9151",
    },
    "corecloud": {
        "deviceTypeId": 2,
        "deviceVariantId": 3,
        "apiEnv": "val",
    },
}

SIGMA5_MANIFEST = {
    "schemaVersion": 1,
    "product": "sigma5",
    "board": "sigma5_std",
    "version": "1.0.0",
    "variant": "release",
    "track": "P",
    "releaseTrack": "production",
    "ncsVersion": "v2.9.0",
    "commitSha": "789abcdef012",
    "branch": "release/v1.0",
    "builtAt": "2026-03-26T19:00:00Z",
    "targets": [
        {
            "role": "app",
            "processor": "nrf52840",
            "appId": 201,
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
            "plaintextHex": "hex/201.1.0.0-P.hex",
            "encryptedCfw": "cfw/201.1.0.0-P.cfw",
        },
    ],
    "corecloud": {
        "deviceTypeId": 5,
        "deviceVariantId": 1,
        "apiEnv": "val",
    },
}


def _make_pipeline_response(builds_data):
    """Create a mock pipeline API response."""
    return {
        "data": {
            "id": "pipeline-42",
            "builds": builds_data,
        }
    }


def _make_build(label, artifacts, status="SUCCESS", version="0.8.3"):
    """Create a mock build dict."""
    return {
        "id": f"build-{label}",
        "product": "alpha",
        "variant": "mfg",
        "status": status,
        "matrixLabel": label,
        "matrixIndex": 0,
        "versionString": version,
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }


def _make_artifact(name, storage_key=None):
    """Create a mock artifact dict."""
    if storage_key is None:
        storage_key = f"firmware/builds/alpha/build-1/{name}"
    return {
        "id": f"art-{name}",
        "name": name,
        "storageKey": storage_key,
        "sizeBytes": 1024,
        "checksum": "abc123",
    }


def _make_build_with_manifest(label, manifest_dict, hex_and_cfw_names=None,
                               status="SUCCESS", version="0.8.3"):
    """Create a build with a build.json manifest artifact and hex/cfw artifacts."""
    artifacts = [_make_artifact("build.json")]
    if hex_and_cfw_names:
        for name in hex_and_cfw_names:
            artifacts.append(_make_artifact(name))
    return _make_build(label, artifacts, status=status, version=version)


class MockResponse:
    """Mock requests.Response."""

    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data) if json_data else ""
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise Exception(f"HTTP {self.status_code}")


# =============================================================================
# BuildManifest parsing
# =============================================================================


class TestBuildManifest:
    """Test build.json manifest parsing."""

    def test_parse_alpha_manifest(self):
        manifest = BuildManifest.from_dict(ALPHA_MANIFEST)
        assert manifest.schema_version == 1
        assert manifest.product == "alpha"
        assert manifest.board == "alpha_b0"
        assert manifest.version == "0.8.3"
        assert manifest.variant == "mfg"
        assert manifest.track == "BM"
        assert len(manifest.targets) == 2

    def test_parse_targets(self):
        manifest = BuildManifest.from_dict(ALPHA_MANIFEST)
        app = manifest.get_target("app")
        assert app is not None
        assert app.role == "app"
        assert app.processor == "nrf52840"
        assert app.app_id == 109
        assert app.host_type == "HOST_TYPE_NRF52840"
        assert app.jlink_family == "NRF52"
        assert app.plaintext_hex == "hex/109.0.8.3-BM.hex"
        assert app.encrypted_cfw == "cfw/109.0.8.3-BM.cfw"

        comms = manifest.get_target("comms")
        assert comms is not None
        assert comms.role == "comms"
        assert comms.app_id == 108

    def test_parse_single_target_product(self):
        manifest = BuildManifest.from_dict(SIGMA5_MANIFEST)
        assert len(manifest.targets) == 1
        assert manifest.targets[0].app_id == 201
        assert manifest.get_target("comms") is None

    def test_corecloud_metadata(self):
        manifest = BuildManifest.from_dict(ALPHA_MANIFEST)
        assert manifest.device_type_id == 2
        assert manifest.device_variant_id == 3
        assert manifest.api_env == "val"

    def test_modem_firmware(self):
        manifest = BuildManifest.from_dict(ALPHA_MANIFEST)
        assert manifest.modem_firmware is not None
        assert manifest.modem_firmware["chipset"] == "nrf9151"

        # Sigma5 has no modem
        manifest2 = BuildManifest.from_dict(SIGMA5_MANIFEST)
        assert manifest2.modem_firmware is None

    def test_get_target_missing_role(self):
        manifest = BuildManifest.from_dict(ALPHA_MANIFEST)
        assert manifest.get_target("nonexistent") is None

    def test_all_app_ids(self):
        manifest = BuildManifest.from_dict(ALPHA_MANIFEST)
        ids = manifest.all_app_ids
        assert ids == {108, 109}

    def test_invalid_schema_version(self):
        data = {**ALPHA_MANIFEST, "schemaVersion": 99}
        with pytest.raises(ValueError, match="Unsupported.*schema.*99"):
            BuildManifest.from_dict(data)

    def test_missing_schema_version(self):
        data = {k: v for k, v in ALPHA_MANIFEST.items() if k != "schemaVersion"}
        with pytest.raises(ValueError, match="Unsupported.*schema.*0"):
            BuildManifest.from_dict(data)


# =============================================================================
# ArtifactResolver — manifest-based resolution
# =============================================================================


class TestArtifactResolverManifest:
    """Test ArtifactResolver with builds that include build.json manifests."""

    def _make_resolver(self, builds, manifest_dict=None, download_side_effect=None):
        """Create resolver with mocked API + storage."""
        pipeline_resp = _make_pipeline_response(builds)

        def mock_get(url, **kwargs):
            if "/builds/pipelines/" in url:
                return MockResponse(pipeline_resp)
            if "/artifacts" in url:
                # Return artifacts for a build
                for b in builds:
                    if b["id"] in url:
                        return MockResponse({"data": b.get("artifacts", [])})
                return MockResponse({"data": []})
            return MockResponse(None, 404)

        with patch("corekinect.test.artifact_resolver.requests") as mock_requests:
            mock_session = MagicMock()
            mock_requests.Session.return_value = mock_session
            mock_session.get.side_effect = mock_get

            resolver = ArtifactResolver(
                pipeline_id="pipeline-42",
                api_url="http://localhost:9001",
                api_key="ck_test_key",
            )

        # Patch storage for downloads
        resolver._session = mock_session
        mock_session.get.side_effect = mock_get

        if manifest_dict is not None:
            # Patch _download_file to return temp files with manifest content
            original_download = resolver._download_file

            def mock_download(storage_key):
                if storage_key.endswith("build.json"):
                    tmp = tempfile.NamedTemporaryFile(
                        suffix=".json", delete=False, mode="w"
                    )
                    json.dump(manifest_dict, tmp)
                    tmp.close()
                    resolver._temp_files.append(tmp.name)
                    return tmp.name
                # For hex/cfw, create a small dummy file
                suffix = Path(storage_key).suffix or ".bin"
                tmp = tempfile.NamedTemporaryFile(
                    suffix=suffix, delete=False, mode="wb"
                )
                tmp.write(b"\x00" * 64)
                tmp.close()
                resolver._temp_files.append(tmp.name)
                return tmp.name

            resolver._download_file = mock_download

        return resolver

    def test_get_manifest(self):
        build = _make_build_with_manifest(
            "MFG_BASE", ALPHA_MANIFEST,
            hex_and_cfw_names=["109.0.8.3-BM.hex", "108.0.8.3-BM.hex"],
        )
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        manifest = resolver.get_manifest("MFG_BASE")
        assert manifest.product == "alpha"
        assert manifest.version == "0.8.3"
        assert len(manifest.targets) == 2

    def test_get_manifest_cached(self):
        build = _make_build_with_manifest("MFG_BASE", ALPHA_MANIFEST)
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        m1 = resolver.get_manifest("MFG_BASE")
        m2 = resolver.get_manifest("MFG_BASE")
        assert m1 is m2  # Same object, not re-downloaded

    def test_get_artifact_hex_by_role(self):
        build = _make_build_with_manifest(
            "MFG_BASE", ALPHA_MANIFEST,
            hex_and_cfw_names=[
                "109.0.8.3-BM.hex", "108.0.8.3-BM.hex",
                "109.0.8.3-BM.cfw", "108.0.8.3-BM.cfw",
            ],
        )
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        path = resolver.get_artifact("MFG_BASE", role="app", artifact_type="plaintextHex")
        assert path is not None
        assert Path(path).exists()

    def test_get_artifact_cfw_by_role(self):
        build = _make_build_with_manifest(
            "MFG_BASE", ALPHA_MANIFEST,
            hex_and_cfw_names=[
                "109.0.8.3-BM.hex", "108.0.8.3-BM.hex",
                "109.0.8.3-BM.cfw", "108.0.8.3-BM.cfw",
            ],
        )
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        path = resolver.get_artifact("MFG_BASE", role="comms", artifact_type="encryptedCfw")
        assert path is not None
        assert Path(path).exists()

    def test_get_artifacts_all_cfws(self):
        build = _make_build_with_manifest(
            "MFG_BASE", ALPHA_MANIFEST,
            hex_and_cfw_names=[
                "109.0.8.3-BM.cfw", "108.0.8.3-BM.cfw",
            ],
        )
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        paths = resolver.get_artifacts("MFG_BASE", artifact_type="encryptedCfw")
        assert len(paths) == 2

    def test_get_artifacts_all_hexes(self):
        build = _make_build_with_manifest(
            "MFG_BASE", ALPHA_MANIFEST,
            hex_and_cfw_names=[
                "109.0.8.3-BM.hex", "108.0.8.3-BM.hex",
            ],
        )
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        paths = resolver.get_artifacts("MFG_BASE", artifact_type="plaintextHex")
        assert len(paths) == 2

    def test_get_targets(self):
        build = _make_build_with_manifest("MFG_BASE", ALPHA_MANIFEST)
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        targets = resolver.get_targets("MFG_BASE")
        assert len(targets) == 2
        roles = {t.role for t in targets}
        assert roles == {"app", "comms"}

    def test_get_target_single(self):
        build = _make_build_with_manifest("MFG_BASE", ALPHA_MANIFEST)
        resolver = self._make_resolver([build], manifest_dict=ALPHA_MANIFEST)

        target = resolver.get_target("MFG_BASE", role="app")
        assert target.app_id == 109
        assert target.host_type == "HOST_TYPE_NRF52840"

    def test_single_processor_product(self):
        build = _make_build_with_manifest(
            "RELEASE", SIGMA5_MANIFEST,
            hex_and_cfw_names=["201.1.0.0-P.hex", "201.1.0.0-P.cfw"],
            version="1.0.0",
        )
        resolver = self._make_resolver([build], manifest_dict=SIGMA5_MANIFEST)

        targets = resolver.get_targets("RELEASE")
        assert len(targets) == 1
        assert targets[0].app_id == 201

        path = resolver.get_artifact("RELEASE", role="app", artifact_type="plaintextHex")
        assert path is not None

        # No comms target
        assert resolver.get_target("RELEASE", role="comms") is None


# =============================================================================
# ArtifactResolver — missing manifest errors
# =============================================================================


class TestArtifactResolverNoManifest:
    """Test that builds without build.json raise errors."""

    def _make_resolver_no_manifest(self, builds):
        """Create resolver with builds that have no manifest artifact."""
        pipeline_resp = _make_pipeline_response(builds)

        def mock_get(url, **kwargs):
            if "/builds/pipelines/" in url:
                return MockResponse(pipeline_resp)
            if "/artifacts" in url:
                for b in builds:
                    if b["id"] in url:
                        return MockResponse({"data": b.get("artifacts", [])})
                return MockResponse({"data": []})
            return MockResponse(None, 404)

        with patch("corekinect.test.artifact_resolver.requests") as mock_requests:
            mock_session = MagicMock()
            mock_requests.Session.return_value = mock_session
            mock_session.get.side_effect = mock_get

            resolver = ArtifactResolver(
                pipeline_id="pipeline-42",
                api_url="http://localhost:9001",
                api_key="ck_test_key",
            )

        resolver._session = mock_session
        mock_session.get.side_effect = mock_get
        return resolver

    def test_no_manifest_get_manifest_raises(self):
        """Builds without build.json should raise ValueError."""
        build = _make_build("MFG_BASE", [
            _make_artifact("109.0.8.3-BM.hex"),
            _make_artifact("108.0.8.3-BM.hex"),
        ])
        resolver = self._make_resolver_no_manifest([build])

        with pytest.raises(ValueError, match="no build.json manifest"):
            resolver.get_manifest("MFG_BASE")

    def test_no_manifest_get_artifact_raises(self):
        """get_artifact should raise when build has no manifest."""
        build = _make_build("MFG_BASE", [
            _make_artifact("109.0.8.3-BM.hex"),
            _make_artifact("108.0.8.3-BM.hex"),
        ])
        resolver = self._make_resolver_no_manifest([build])

        with pytest.raises(ValueError, match="no build.json manifest"):
            resolver.get_artifact("MFG_BASE", role="app", artifact_type="plaintextHex")

    def test_no_manifest_get_artifacts_raises(self):
        """get_artifacts should raise when build has no manifest."""
        build = _make_build("MFG_BASE", [
            _make_artifact("109.0.8.3-BM.cfw"),
            _make_artifact("108.0.8.3-BM.cfw"),
        ])
        resolver = self._make_resolver_no_manifest([build])

        with pytest.raises(ValueError, match="no build.json manifest"):
            resolver.get_artifacts("MFG_BASE", artifact_type="encryptedCfw")


# =============================================================================
# ArtifactResolver — error handling
# =============================================================================


class TestArtifactResolverErrors:
    """Test error cases."""

    def _make_resolver_with_builds(self, builds):
        pipeline_resp = _make_pipeline_response(builds)

        def mock_get(url, **kwargs):
            if "/builds/pipelines/" in url:
                return MockResponse(pipeline_resp)
            return MockResponse(None, 404)

        with patch("corekinect.test.artifact_resolver.requests") as mock_requests:
            mock_session = MagicMock()
            mock_requests.Session.return_value = mock_session
            mock_session.get.side_effect = mock_get

            resolver = ArtifactResolver(
                pipeline_id="pipeline-42",
                api_url="http://localhost:9001",
                api_key="ck_test_key",
            )

        resolver._session = mock_session
        mock_session.get.side_effect = mock_get
        return resolver

    def test_missing_build_label(self):
        build = _make_build("MFG_BASE", [])
        resolver = self._make_resolver_with_builds([build])

        with pytest.raises(KeyError, match="NONEXISTENT"):
            resolver.get_manifest("NONEXISTENT")

    def test_missing_artifact_role(self):
        build = _make_build_with_manifest("MFG_BASE", ALPHA_MANIFEST)
        resolver = self._make_resolver_with_builds([build])

        # Mock manifest download
        def mock_download(storage_key):
            if storage_key.endswith("build.json"):
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".json", delete=False, mode="w"
                )
                json.dump(ALPHA_MANIFEST, tmp)
                tmp.close()
                resolver._temp_files.append(tmp.name)
                return tmp.name
            raise RuntimeError(f"Artifact not found: {storage_key}")

        resolver._download_file = mock_download

        with pytest.raises(ValueError, match="No target.*role='modem'"):
            resolver.get_artifact("MFG_BASE", role="modem", artifact_type="plaintextHex")

    def test_empty_pipeline(self):
        resolver = self._make_resolver_with_builds([])

        with pytest.raises(KeyError, match="MFG_BASE"):
            resolver.get_manifest("MFG_BASE")

    def test_get_target_nonexistent_role(self):
        build = _make_build_with_manifest("MFG_BASE", ALPHA_MANIFEST)
        resolver = self._make_resolver_with_builds([build])

        def mock_download(storage_key):
            tmp = tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w"
            )
            json.dump(ALPHA_MANIFEST, tmp)
            tmp.close()
            resolver._temp_files.append(tmp.name)
            return tmp.name

        resolver._download_file = mock_download

        result = resolver.get_target("MFG_BASE", role="nonexistent")
        assert result is None


# =============================================================================
# ArtifactResolver — cleanup
# =============================================================================


class TestArtifactResolverCleanup:
    """Test temp file cleanup."""

    def test_cleanup_removes_temp_files(self):
        with patch("corekinect.test.artifact_resolver.requests"):
            resolver = ArtifactResolver(
                pipeline_id="p1",
                api_url="http://localhost",
                api_key="ck_test",
            )

        # Create some temp files
        tmp1 = tempfile.NamedTemporaryFile(delete=False)
        tmp1.close()
        tmp2 = tempfile.NamedTemporaryFile(delete=False)
        tmp2.close()

        resolver._temp_files.extend([tmp1.name, tmp2.name])

        assert Path(tmp1.name).exists()
        assert Path(tmp2.name).exists()

        resolver.cleanup()

        assert not Path(tmp1.name).exists()
        assert not Path(tmp2.name).exists()
        assert len(resolver._temp_files) == 0


# =============================================================================
# StorageConfig
# =============================================================================


class TestStorageConfig:
    """Test StorageConfig from env vars."""

    def test_defaults(self):
        cfg = StorageConfig()
        assert cfg.bucket_name == "concord"

    def test_from_env(self):
        with patch.dict(os.environ, {
            "STORAGE_URL": "http://minio:9000",
            "STORAGE_ACCESS_KEY": "access",
            "STORAGE_SECRET_ACCESS_KEY": "secret",
            "STORAGE_BUCKET_NAME": "my-bucket",
        }):
            cfg = StorageConfig.from_env()
            assert cfg.url == "http://minio:9000"
            assert cfg.access_key == "access"
            assert cfg.secret_key == "secret"
            assert cfg.bucket_name == "my-bucket"
