"""Unit tests for firmware asset management module.

Tests FirmwareAsset dataclass, get_firmware_path_from_env(),
and _StorageConfig parsing. All tests run without MinIO or MTIB
hardware.
"""

import os
from unittest.mock import patch

import pytest

from corekinect.test.firmware import (
    FirmwareAsset,
    get_firmware_path_from_env,
    _StorageConfig,
)


# =============================================================================
# FirmwareAsset dataclass
# =============================================================================


class TestFirmwareAsset:
    """Test FirmwareAsset dataclass construction and defaults."""

    def test_construction_all_fields(self):
        asset = FirmwareAsset(
            storage_key="firmware/builds/alpha/abc/app.hex",
            local_path="/tmp/fw_abc123.hex",
            mtib_name="app.hex",
            size_bytes=65536,
            uploaded=True,
        )
        assert asset.storage_key == "firmware/builds/alpha/abc/app.hex"
        assert asset.local_path == "/tmp/fw_abc123.hex"
        assert asset.mtib_name == "app.hex"
        assert asset.size_bytes == 65536
        assert asset.uploaded is True

    def test_default_size_bytes(self):
        """size_bytes defaults to 0."""
        asset = FirmwareAsset(
            storage_key="fw/app.hex",
            local_path="/tmp/fw.hex",
            mtib_name="app.hex",
        )
        assert asset.size_bytes == 0

    def test_default_uploaded(self):
        """uploaded defaults to False."""
        asset = FirmwareAsset(
            storage_key="fw/app.hex",
            local_path="/tmp/fw.hex",
            mtib_name="app.hex",
        )
        assert asset.uploaded is False

    def test_defaults_together(self):
        """Both defaults should work together."""
        asset = FirmwareAsset(
            storage_key="k",
            local_path="/p",
            mtib_name="n",
        )
        assert asset.size_bytes == 0
        assert asset.uploaded is False

    def test_large_size_bytes(self):
        """Should handle large firmware files."""
        asset = FirmwareAsset(
            storage_key="k",
            local_path="/p",
            mtib_name="n",
            size_bytes=10_000_000,
        )
        assert asset.size_bytes == 10_000_000


# =============================================================================
# get_firmware_path_from_env
# =============================================================================


class TestGetFirmwarePathFromEnv:
    """Test get_firmware_path_from_env() environment variable reading."""

    def test_returns_path_when_set(self):
        with patch.dict(os.environ, {
            "FIRMWARE_BUCKET_FILE_PATH": "firmware/builds/alpha/abc123/app.hex",
        }):
            result = get_firmware_path_from_env()
            assert result == "firmware/builds/alpha/abc123/app.hex"

    def test_returns_none_when_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            result = get_firmware_path_from_env()
            assert result is None

    def test_returns_empty_string_if_set_empty(self):
        """An empty string is still a valid env var value."""
        with patch.dict(os.environ, {"FIRMWARE_BUCKET_FILE_PATH": ""}):
            result = get_firmware_path_from_env()
            assert result == ""

    def test_preserves_full_path(self):
        path = "firmware/builds/alpha_fw/build-xyz/0.8.3_comms_nrf9151.hex"
        with patch.dict(os.environ, {"FIRMWARE_BUCKET_FILE_PATH": path}):
            result = get_firmware_path_from_env()
            assert result == path


# =============================================================================
# _StorageConfig
# =============================================================================


class TestStorageConfigFirmware:
    """Test _StorageConfig (firmware module's EnvConfig subclass)."""

    def test_defaults_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.STORAGE_URL is None
            assert cfg.STORAGE_ACCESS_KEY is None
            assert cfg.STORAGE_SECRET_ACCESS_KEY is None
            assert cfg.STORAGE_BUCKET_NAME == "concord"
            assert cfg.FIRMWARE_BUCKET_FILE_PATH is None

    def test_reads_storage_url(self):
        with patch.dict(os.environ, {"STORAGE_URL": "http://minio:9000"}, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.STORAGE_URL == "http://minio:9000"

    def test_reads_all_storage_vars(self):
        env = {
            "STORAGE_URL": "https://minio.prod:9000",
            "STORAGE_ACCESS_KEY": "admin",
            "STORAGE_SECRET_ACCESS_KEY": "password123",
            "STORAGE_BUCKET_NAME": "my-firmware",
            "FIRMWARE_BUCKET_FILE_PATH": "firmware/builds/alpha/build-1/app.hex",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.STORAGE_URL == "https://minio.prod:9000"
            assert cfg.STORAGE_ACCESS_KEY == "admin"
            assert cfg.STORAGE_SECRET_ACCESS_KEY == "password123"
            assert cfg.STORAGE_BUCKET_NAME == "my-firmware"
            assert cfg.FIRMWARE_BUCKET_FILE_PATH == "firmware/builds/alpha/build-1/app.hex"

    def test_bucket_name_default(self):
        """STORAGE_BUCKET_NAME defaults to 'concord' when not in env."""
        with patch.dict(os.environ, {}, clear=True):
            cfg = _StorageConfig(auto_load_env=False)
            assert cfg.STORAGE_BUCKET_NAME == "concord"
