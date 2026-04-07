"""Tests for src/worker/manifest.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.worker.manifest import (
    PROCESSOR_MAP,
    _compute_track,
    _scan_artifacts,
    classify_artifact,
    generate_build_manifest,
)


class TestClassifyArtifact:
    """Tests for classify_artifact()."""

    def test_classify_artifact_hex(self):
        """A versioned hex filename returns ('plaintextHex', appId)."""
        result = classify_artifact("109.0.8.3.hex")
        assert result == ("plaintextHex", 109)

    def test_classify_artifact_cfw(self):
        """A CFW filename returns ('encryptedCfw', appId)."""
        result = classify_artifact("108.0.5.2-BM.cfw")
        assert result == ("encryptedCfw", 108)

    def test_classify_artifact_invalid(self):
        """A non-artifact filename returns None."""
        assert classify_artifact("readme.txt") is None

    @pytest.mark.parametrize("filename,expected", [
        ("109.0.8.3-BMD.hex", ("plaintextHex", 109)),
        ("108.0.8.3-BMD.cfw", ("encryptedCfw", 108)),
        ("109.0.8.3-BM.hex", ("plaintextHex", 109)),
        ("108.0.5.2-P.cfw", ("encryptedCfw", 108)),
        ("109.0.8.3.hex", ("plaintextHex", 109)),
        ("108.0.8.3.cfw", ("encryptedCfw", 108)),
    ])
    def test_classify_artifact_valid_patterns(self, filename, expected):
        """All expected valid patterns are classified correctly."""
        assert classify_artifact(filename) == expected

    @pytest.mark.parametrize("filename", [
        "readme.txt",
        "build.log",
        "build.json",
        "zephyr.hex",           # no appId prefix
        "109.hex",              # missing version components
        "109.0.hex",            # incomplete version
        "abc.0.8.3.hex",        # non-numeric appId
        "",
    ])
    def test_classify_artifact_invalid_patterns(self, filename):
        """Non-artifact filenames consistently return None."""
        assert classify_artifact(filename) is None


class TestComputeTrack:
    """Tests for _compute_track()."""

    def test_compute_track_bench_release(self):
        """bench + release → 'BM'."""
        assert _compute_track("release", "bench") == "BM"

    def test_compute_track_bench_mfg(self):
        """bench + mfg → 'BM'."""
        assert _compute_track("mfg", "bench") == "BM"

    def test_compute_track_bench_debug(self):
        """bench + debug → 'BMD'."""
        assert _compute_track("debug", "bench") == "BMD"

    def test_compute_track_production_release(self):
        """production + release → 'P'."""
        assert _compute_track("release", "production") == "P"

    def test_compute_track_production_debug(self):
        """production + debug → 'PD'."""
        assert _compute_track("debug", "production") == "PD"

    def test_compute_track_engineering_release(self):
        """engineering + release → 'EM'."""
        assert _compute_track("release", "engineering") == "EM"

    def test_compute_track_engineering_mfg(self):
        """engineering + mfg → 'EM'."""
        assert _compute_track("mfg", "engineering") == "EM"

    def test_compute_track_engineering_debug(self):
        """engineering + debug → 'EMD'."""
        assert _compute_track("debug", "engineering") == "EMD"

    @pytest.mark.parametrize("variant,track,expected", [
        ("release", "bench", "BM"),
        ("mfg", "bench", "BM"),
        ("debug", "bench", "BMD"),
        ("release", "engineering", "EM"),
        ("debug", "engineering", "EMD"),
        ("release", "production", "P"),
        ("debug", "production", "PD"),
    ])
    def test_compute_track_parametrized(self, variant, track, expected):
        """Parametrized coverage of all track/variant combinations."""
        assert _compute_track(variant, track) == expected


class TestScanArtifacts:
    """Tests for _scan_artifacts()."""

    def test_scan_artifacts_groups_by_app_id(self, tmp_path):
        """Files are returned grouped by appId with correct artifact types."""
        (tmp_path / "109.0.8.3.hex").write_text("hex-data")
        (tmp_path / "108.0.8.3-BM.cfw").write_text("cfw-data")

        result = _scan_artifacts(tmp_path)

        assert 109 in result
        assert result[109]["plaintextHex"] == "109.0.8.3.hex"
        assert 108 in result
        assert result[108]["encryptedCfw"] == "108.0.8.3-BM.cfw"

    def test_scan_artifacts_recursive(self, tmp_path):
        """Recursively finds artifacts in subdirectories."""
        subdir = tmp_path / "0.8.3" / "release"
        subdir.mkdir(parents=True)
        (subdir / "109.0.8.3.hex").write_text("hex")
        (subdir / "109.0.8.3-BM.cfw").write_text("cfw")

        result = _scan_artifacts(tmp_path)

        assert 109 in result
        assert "plaintextHex" in result[109]
        assert "encryptedCfw" in result[109]
        # Paths should be relative to output_dir
        assert not result[109]["plaintextHex"].startswith("/")

    def test_scan_artifacts_empty_dir(self, tmp_path):
        """Empty output directory returns empty dict."""
        assert _scan_artifacts(tmp_path) == {}

    def test_scan_artifacts_ignores_non_artifacts(self, tmp_path):
        """build.log, zephyr.hex and other non-artifact files are ignored."""
        (tmp_path / "build.log").write_text("log")
        (tmp_path / "zephyr.hex").write_text("hex")  # no appId prefix
        (tmp_path / "readme.txt").write_text("readme")

        assert _scan_artifacts(tmp_path) == {}

    # TODO: test_scan_artifacts_multiple_app_ids
    # TODO: test_scan_artifacts_both_types_per_app_id


class TestGenerateBuildManifest:
    """Tests for generate_build_manifest()."""

    def test_generate_build_manifest_full(self, tmp_path, sample_build_config):
        """Full manifest contains expected structure with targets and corecloud."""
        # Create fake artifacts
        (tmp_path / "109.0.8.3.hex").write_text("hex")
        (tmp_path / "108.0.8.3-BM.cfw").write_text("cfw")

        manifest = generate_build_manifest(
            build_config=sample_build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="release",
            commit_sha="deadbeef",
            branch="main",
        )

        assert manifest["schemaVersion"] == 1
        assert manifest["product"] == "alpha"
        assert manifest["board"] == "alpha_b0"
        assert manifest["version"] == "0.8.3"
        assert manifest["variant"] == "release"
        assert manifest["track"] == "BM"
        assert manifest["releaseTrack"] == "bench"
        assert manifest["ncsVersion"] == "2.7.0"
        assert manifest["commitSha"] == "deadbeef"
        assert manifest["branch"] == "main"
        assert "builtAt" in manifest
        assert "targets" in manifest
        assert "corecloud" in manifest
        assert len(manifest["targets"]) == 2

    def test_generate_build_manifest_targets_have_required_fields(self, tmp_path, sample_build_config):
        """Every target entry has role, processor, appId, hostType, jlinkFamily."""
        manifest = generate_build_manifest(
            build_config=sample_build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="release",
            commit_sha="deadbeef",
            branch="main",
        )
        for target in manifest["targets"]:
            assert "role" in target
            assert "processor" in target
            assert "appId" in target
            assert "hostType" in target
            assert "jlinkFamily" in target

    def test_generate_build_manifest_no_artifacts(self, tmp_path, sample_build_config):
        """Manifest is generated even when output dir has no artifact files."""
        manifest = generate_build_manifest(
            build_config=sample_build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.0.0",
            variant="release",
            commit_sha="",
            branch="main",
        )
        assert manifest["schemaVersion"] == 1
        # All targets present but artifacts are None
        for target in manifest["targets"]:
            assert target["plaintextHex"] is None
            assert target["encryptedCfw"] is None

    def test_generate_build_manifest_signing_fingerprints(self, tmp_path, sample_build_config):
        """Signing fingerprints are included when key files exist in key_dir."""
        key_dir = tmp_path / "keys"
        key_dir.mkdir()
        (key_dir / "encryption_key.pem").write_bytes(b"fake-key-app")
        (key_dir / "comms_encryption_key.pem").write_bytes(b"fake-key-comms")

        manifest = generate_build_manifest(
            build_config=sample_build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="release",
            commit_sha="abc123",
            branch="main",
            key_dir=key_dir,
        )

        assert "signing" in manifest
        assert "keyFingerprints" in manifest["signing"]

    def test_generate_build_manifest_no_signing_when_no_key_dir(self, tmp_path, sample_build_config):
        """No signing block when key_dir is None."""
        manifest = generate_build_manifest(
            build_config=sample_build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="release",
            commit_sha="abc123",
            branch="main",
            key_dir=None,
        )
        assert "signing" not in manifest

    def test_generate_build_manifest_dict_targets_normalized(self, tmp_path):
        """Dict-format targets ({"app": {...}, "comms": {...}}) are normalized to a list."""
        build_config = {
            "targets": {
                "app": {"appId": 109, "processor": "nrf52840"},
                "comms": {"appId": 108, "processor": "nrf9151"},
            },
            "cfw": {},
            "releaseTrack": "bench",
            "ncsVersion": "2.7.0",
        }
        manifest = generate_build_manifest(
            build_config=build_config,
            output_dir=tmp_path,
            product="alpha",
            board="alpha_b0",
            version="0.8.3",
            variant="release",
            commit_sha="",
            branch="main",
        )
        assert isinstance(manifest["targets"], list)
        assert len(manifest["targets"]) == 2


class TestProcessorMap:
    """Tests for PROCESSOR_MAP completeness."""

    def test_processor_map_contains_nrf52840(self):
        """PROCESSOR_MAP has an entry for nrf52840."""
        assert "nrf52840" in PROCESSOR_MAP
        assert PROCESSOR_MAP["nrf52840"]["hostType"] == "HOST_TYPE_NRF52840"
        assert PROCESSOR_MAP["nrf52840"]["jlinkFamily"] == "NRF52"

    def test_processor_map_contains_nrf9151(self):
        """PROCESSOR_MAP has an entry for nrf9151."""
        assert "nrf9151" in PROCESSOR_MAP
        assert PROCESSOR_MAP["nrf9151"]["jlinkFamily"] == "NRF91"

    def test_processor_map_contains_nrf9160(self):
        """PROCESSOR_MAP has an entry for nrf9160."""
        assert "nrf9160" in PROCESSOR_MAP
        assert PROCESSOR_MAP["nrf9160"]["jlinkFamily"] == "NRF91"

    def test_processor_map_entries_have_required_fields(self):
        """Every PROCESSOR_MAP entry has both hostType and jlinkFamily."""
        for name, info in PROCESSOR_MAP.items():
            assert "hostType" in info, f"Missing hostType for {name}"
            assert "jlinkFamily" in info, f"Missing jlinkFamily for {name}"

    # TODO: test_processor_map_alpha_app_ids_map_to_correct_processors
