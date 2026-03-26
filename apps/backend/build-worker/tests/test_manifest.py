"""Tests for build.json manifest generation."""

import json
import os
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.manifest import generate_build_manifest, classify_artifact, PROCESSOR_MAP


# --- Fixtures ---

@pytest.fixture
def build_config():
    """A realistic Product.buildConfig for alpha."""
    return {
        "targets": [
            {
                "role": "app",
                "processor": "nrf52840",
                "appId": 109,
            },
            {
                "role": "comms",
                "processor": "nrf9151",
                "appId": 108,
            },
        ],
        "cfw": {
            "deviceTypeId": 2,
            "deviceVariantId": 3,
            "apiEnv": "val",
        },
        "releaseTrack": "bench",
        "ncsVersion": "2.7.0",
    }


@pytest.fixture
def single_target_config():
    """A buildConfig for a single-processor product (like sigma5)."""
    return {
        "targets": [
            {
                "role": "app",
                "processor": "nrf52840",
                "appId": 201,
            },
        ],
        "cfw": {
            "deviceTypeId": 5,
            "deviceVariantId": 1,
            "apiEnv": "val",
        },
        "releaseTrack": "production",
        "ncsVersion": "2.9.0",
    }


@pytest.fixture
def output_dir(tmp_path):
    """Create a mock build output directory with hex and cfw files."""
    # Create hex files
    hex_dir = tmp_path
    (hex_dir / "109.0.8.3-BM.hex").write_text("fake hex app")
    (hex_dir / "108.0.8.3-BM.hex").write_text("fake hex comms")

    # Create cfw files
    (hex_dir / "109.0.8.3-BM.cfw").write_bytes(b"\x00" * 64)
    (hex_dir / "108.0.8.3-BM.cfw").write_bytes(b"\x00" * 64)

    # Create a build.log (should be ignored by manifest)
    (hex_dir / "build.log").write_text("build output")

    return tmp_path


@pytest.fixture
def output_dir_hex_only(tmp_path):
    """Output dir with hex files but no CFW (e.g., smoke build)."""
    (tmp_path / "109.0.8.3-BM.hex").write_text("fake hex app")
    (tmp_path / "108.0.8.3-BM.hex").write_text("fake hex comms")
    return tmp_path


@pytest.fixture
def output_dir_single_target(tmp_path):
    """Output dir for a single-target product."""
    (tmp_path / "201.1.0.0-P.hex").write_text("fake hex app")
    (tmp_path / "201.1.0.0-P.cfw").write_bytes(b"\x00" * 32)
    return tmp_path


@pytest.fixture
def key_dir(tmp_path):
    """Create mock signing key files."""
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "encryption_key.pem").write_text("fake-app-key-content")
    (keys / "comms_encryption_key.pem").write_text("fake-comms-key-content")
    return keys


# --- Tests ---

class TestGenerateBuildManifest:

    def test_schema_version(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234def5678",
            branch="main",
        )
        assert manifest["schemaVersion"] == 1

    def test_required_top_level_fields(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234def5678",
            branch="main",
        )
        required_fields = [
            "schemaVersion", "product", "board", "version", "variant",
            "track", "releaseTrack", "ncsVersion", "commitSha", "branch",
            "builtAt", "targets", "corecloud",
        ]
        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"

    def test_product_metadata(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234def5678",
            branch="main",
        )
        assert manifest["product"] == "alpha"
        assert manifest["board"] == "alpha_b0"
        assert manifest["version"] == "0.8.3"
        assert manifest["variant"] == "mfg"
        assert manifest["commitSha"] == "abc1234def5678"
        assert manifest["branch"] == "main"
        assert manifest["ncsVersion"] == "2.7.0"
        assert manifest["releaseTrack"] == "bench"

    def test_targets_array_dual_processor(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        targets = manifest["targets"]
        assert len(targets) == 2

        # App target
        app = next(t for t in targets if t["role"] == "app")
        assert app["processor"] == "nrf52840"
        assert app["appId"] == 109
        assert app["hostType"] == "HOST_TYPE_NRF52840"
        assert app["jlinkFamily"] == "NRF52"

        # Comms target
        comms = next(t for t in targets if t["role"] == "comms")
        assert comms["processor"] == "nrf9151"
        assert comms["appId"] == 108
        assert comms["hostType"] == "HOST_TYPE_NRF9151"
        assert comms["jlinkFamily"] == "NRF91"

    def test_targets_single_processor(self, single_target_config, output_dir_single_target):
        manifest = generate_build_manifest(
            build_config=single_target_config,
            output_dir=output_dir_single_target,
            product="sigma5",
            board="sigma5_std",
            version="1.0.0",
            variant="release",
            commit_sha="789abcdef012",
            branch="release/v1.0",
        )
        targets = manifest["targets"]
        assert len(targets) == 1
        assert targets[0]["role"] == "app"
        assert targets[0]["appId"] == 201

    def test_artifact_paths_hex_and_cfw(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        app = next(t for t in manifest["targets"] if t["role"] == "app")
        assert app["plaintextHex"] == "109.0.8.3-BM.hex"
        assert app["encryptedCfw"] == "109.0.8.3-BM.cfw"

        comms = next(t for t in manifest["targets"] if t["role"] == "comms")
        assert comms["plaintextHex"] == "108.0.8.3-BM.hex"
        assert comms["encryptedCfw"] == "108.0.8.3-BM.cfw"

    def test_artifact_paths_hex_only(self, build_config, output_dir_hex_only):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir_hex_only,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        app = next(t for t in manifest["targets"] if t["role"] == "app")
        assert app["plaintextHex"] == "109.0.8.3-BM.hex"
        assert app["encryptedCfw"] is None

    def test_corecloud_fields(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        assert manifest["corecloud"]["deviceTypeId"] == 2
        assert manifest["corecloud"]["deviceVariantId"] == 3
        assert manifest["corecloud"]["apiEnv"] == "val"

    def test_track_mfg(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        assert manifest["track"] == "BM"

    def test_track_debug(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="debug",
            commit_sha="abc1234",
            branch="main",
        )
        assert manifest["track"] == "BMD"

    def test_track_release_bench(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="release",
            commit_sha="abc1234",
            branch="main",
        )
        # bench releaseTrack + release variant = BM (bench+mfg, no debug)
        assert manifest["track"] == "BM"

    def test_track_release_production(self, single_target_config, output_dir_single_target):
        manifest = generate_build_manifest(
            build_config=single_target_config,
            output_dir=output_dir_single_target,
            product="sigma5",
            board="sigma5_std",
            version="1.0.0",
            variant="release",
            commit_sha="abc1234",
            branch="main",
        )
        assert manifest["track"] == "P"

    def test_signing_with_keys(self, build_config, output_dir, key_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
            key_dir=key_dir,
        )
        assert "signing" in manifest
        fingerprints = manifest["signing"]["keyFingerprints"]
        # Should have fingerprints keyed by appId string
        assert "109" in fingerprints or "108" in fingerprints

    def test_signing_without_keys(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        # No key_dir provided, signing should be absent
        assert "signing" not in manifest

    def test_builtAt_is_iso8601(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        built_at = manifest["builtAt"]
        assert built_at.endswith("Z")
        assert "T" in built_at

    def test_manifest_is_json_serializable(self, build_config, output_dir):
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=output_dir,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        # Should not raise
        serialized = json.dumps(manifest)
        parsed = json.loads(serialized)
        assert parsed["schemaVersion"] == 1

    def test_empty_output_dir(self, build_config, tmp_path):
        """Manifest still generates with no artifacts — targets have null paths."""
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="mfg",
            commit_sha="abc1234",
            branch="main",
        )
        app = next(t for t in manifest["targets"] if t["role"] == "app")
        assert app["plaintextHex"] is None
        assert app["encryptedCfw"] is None


class TestClassifyArtifact:

    def test_hex_classification(self):
        result = classify_artifact("109.0.8.3-BM.hex")
        assert result == ("plaintextHex", 109)

    def test_cfw_classification(self):
        result = classify_artifact("108.0.8.3-BM.cfw")
        assert result == ("encryptedCfw", 108)

    def test_non_artifact(self):
        result = classify_artifact("build.log")
        assert result is None

    def test_build_json(self):
        result = classify_artifact("build.json")
        assert result is None

    def test_versioned_hex_without_track(self):
        result = classify_artifact("109.0.8.3.hex")
        assert result == ("plaintextHex", 109)

    def test_cfw_with_debug_track(self):
        result = classify_artifact("109.0.8.3-BMD.cfw")
        assert result == ("encryptedCfw", 109)


class TestProcessorMap:

    def test_nrf52840_mapping(self):
        mapping = PROCESSOR_MAP["nrf52840"]
        assert mapping["hostType"] == "HOST_TYPE_NRF52840"
        assert mapping["jlinkFamily"] == "NRF52"

    def test_nrf9151_mapping(self):
        mapping = PROCESSOR_MAP["nrf9151"]
        assert mapping["hostType"] == "HOST_TYPE_NRF9151"
        assert mapping["jlinkFamily"] == "NRF91"

    def test_nrf9160_mapping(self):
        mapping = PROCESSOR_MAP["nrf9160"]
        assert mapping["hostType"] == "HOST_TYPE_NRF9160"
        assert mapping["jlinkFamily"] == "NRF91"
