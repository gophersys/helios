"""Firmware asset management for validation tests.

Provides FirmwareAssetManager: Downloads firmware from MinIO and uploads to
MTIB server.

For build run artifact resolution, use ArtifactResolver from
corekinect.test.artifact_resolver instead.

Storage layout in MinIO (firmware/builds prefix):
    firmware/builds/{product}/{build_id}/{filename}
    firmware/builds/alpha_fw/abc123/app_nrf52840.hex
    firmware/builds/alpha_fw/abc123/comms_nrf9151.hex

Environment variables:
    STORAGE_URL:               MinIO endpoint (e.g., http://minio:9000)
    STORAGE_ACCESS_KEY:        MinIO access key
    STORAGE_SECRET_ACCESS_KEY: MinIO secret key
    STORAGE_BUCKET_NAME:       Bucket name (default: concord)
    FIRMWARE_BUCKET_FILE_PATH: Path to firmware in MinIO (optional, for K8s jobs)

Example usage:
    assets = FirmwareAssetManager(mtib=client)
    hex_name = assets.fetch_and_upload("firmware/builds/alpha_fw/abc123/app_nrf52840.hex", target="nrf52840")
    assets.cleanup()
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from protocols.mtib.mtib_pb2 import FwFileInfo, HostType

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.utils import EnvConfig, Logger

log = Logger(log_name="firmware_assets")

# Optional MinIO import
try:
    from minio import Minio
    _HAS_MINIO = True
except ImportError:
    _HAS_MINIO = False


class _StorageConfig(EnvConfig):
    """MinIO storage config — same as ArtifactWriter for consistency."""
    ENV_PREFIX = ""

    STORAGE_URL: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_ACCESS_KEY: Optional[str] = None
    STORAGE_BUCKET_NAME: str = "concord"

    # Firmware path for K8s jobs (optional)
    FIRMWARE_BUCKET_FILE_PATH: Optional[str] = None


@dataclass
class FirmwareAsset:
    """Metadata for a downloaded firmware asset."""
    storage_key: str          # MinIO object key
    local_path: str           # Temp file path (after download)
    mtib_name: str            # Name on MTIB server (after upload)
    size_bytes: int = 0
    uploaded: bool = False


class FirmwareAssetManager:
    """Manages firmware asset lifecycle: MinIO → local → MTIB → cleanup.

    Thread-safe for single-session use. Not designed for concurrent access
    across multiple test sessions.

    Args:
        mtib: Connected MTIB V1 client for upload operations.
        logger: Optional parent logger for child logger creation.
        auto_cleanup: If True, cleanup is called automatically on __del__.
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        logger: Optional[Logger] = None,
        auto_cleanup: bool = True,
    ):
        self._mtib = mtib
        self._log = logger.from_parent("firmware_assets") if logger else log
        self._auto_cleanup = auto_cleanup

        # Storage client (lazy init)
        self._minio: Optional[Minio] = None
        self._config = _StorageConfig()

        # Tracking
        self._assets: Dict[str, FirmwareAsset] = {}  # storage_key -> asset
        self._uploaded_names: Set[str] = set()       # MTIB filenames to cleanup
        self._temp_files: List[str] = []             # Local temp files to cleanup

    def __del__(self):
        if self._auto_cleanup:
            try:
                self.cleanup()
            except Exception as exc:
                log.warning("Error during firmware asset cleanup: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # MinIO Client
    # ─────────────────────────────────────────────────────────────────────────

    def _get_minio(self) -> Optional[Minio]:
        """Lazy-initialize MinIO client."""
        if self._minio is not None:
            return self._minio

        if not _HAS_MINIO:
            self._log.warning("minio package not installed — storage disabled")
            return None

        if not self._config.STORAGE_URL:
            self._log.debug("STORAGE_URL not set — storage disabled")
            return None

        parsed = urlparse(self._config.STORAGE_URL)
        self._minio = Minio(
            endpoint=parsed.netloc,
            access_key=self._config.STORAGE_ACCESS_KEY or "",
            secret_key=self._config.STORAGE_SECRET_ACCESS_KEY or "",
            secure=(parsed.scheme == "https"),
        )
        self._log.debug("MinIO client initialized: %s", parsed.netloc)
        return self._minio

    @property
    def storage_enabled(self) -> bool:
        """Check if MinIO storage is configured and available."""
        return self._get_minio() is not None

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def fetch_and_upload(
        self,
        storage_key: str,
        target: str,
        mtib_name: Optional[str] = None,
    ) -> str:
        """Download firmware from MinIO and upload to MTIB server.

        Args:
            storage_key: Full MinIO object key (e.g., "firmware/builds/alpha/abc/app.hex")
            target: MTIB target type ("nrf52840", "nrf9151", "nrf9151_modem") — required
            mtib_name: Override filename on MTIB (default: basename of storage_key)

        Returns:
            Filename on MTIB server (for use with flash_firmware)

        Raises:
            RuntimeError: If MinIO not configured or download/upload fails
        """
        # Check if already uploaded
        if storage_key in self._assets and self._assets[storage_key].uploaded:
            asset = self._assets[storage_key]
            self._log.debug("Asset already uploaded: %s -> %s", storage_key, asset.mtib_name)
            return asset.mtib_name

        # Download from MinIO
        local_path = self._download(storage_key)

        # Determine MTIB filename
        if mtib_name is None:
            mtib_name = Path(storage_key).name

        # Upload to MTIB
        self._upload_to_mtib(local_path, target, mtib_name)

        # Track the asset
        asset = FirmwareAsset(
            storage_key=storage_key,
            local_path=local_path,
            mtib_name=mtib_name,
            size_bytes=os.path.getsize(local_path),
            uploaded=True,
        )
        self._assets[storage_key] = asset
        self._uploaded_names.add(mtib_name)

        self._log.info("Firmware ready on MTIB: %s (from %s)", mtib_name, storage_key)
        return mtib_name

    def upload_local(
        self,
        local_path: str,
        target: str,
        mtib_name: Optional[str] = None,
    ) -> str:
        """Upload a local firmware file to MTIB server (bypasses MinIO).

        Useful for local development or when firmware is already on disk.

        Args:
            local_path: Path to local .hex/.zip file
            target: MTIB target type ("nrf52840", "nrf9151", "nrf9151_modem") — required
            mtib_name: Override filename on MTIB (default: basename of local_path)

        Returns:
            Filename on MTIB server
        """
        if mtib_name is None:
            mtib_name = Path(local_path).name

        self._upload_to_mtib(local_path, target, mtib_name)
        self._uploaded_names.add(mtib_name)

        self._log.info("Local firmware uploaded to MTIB: %s", mtib_name)
        return mtib_name

    def cleanup(self) -> None:
        """Delete uploaded firmware from MTIB server and local temp files.

        Safe to call multiple times. Logs warnings but doesn't raise on errors.
        """
        # Delete from MTIB
        for name in list(self._uploaded_names):
            try:
                # DeleteFwFile requires FwFileInfo, not just the name string
                file_info = FwFileInfo(name=name, target=HostType.HOST_TYPE_NRF52840)
                err = self._mtib.DeleteFwFile(file_info)
                if err:
                    self._log.warning("Failed to delete %s from MTIB: %s", name, err)
                else:
                    self._log.debug("Deleted %s from MTIB", name)
            except Exception as e:
                self._log.warning("Error deleting %s from MTIB: %s", name, e)
            self._uploaded_names.discard(name)

        # Delete local temp files
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
                    self._log.debug("Deleted temp file: %s", path)
            except Exception as e:
                self._log.warning("Error deleting temp file %s: %s", path, e)
            try:
                self._temp_files.remove(path)
            except ValueError:
                pass

        self._assets.clear()

    def list_mtib_files(self) -> List[str]:
        """List firmware files currently on the MTIB server."""
        files, err = self._mtib.ListFwFiles()
        if err:
            self._log.warning("ListFwFiles failed: %s", err)
            return []
        return [f.name for f in files] if files else []

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _download(self, storage_key: str) -> str:
        """Download object from MinIO to a temp file."""
        minio = self._get_minio()
        if minio is None:
            raise RuntimeError("MinIO storage not configured")

        bucket = self._config.STORAGE_BUCKET_NAME

        # Create temp file with correct extension
        suffix = Path(storage_key).suffix or ".hex"
        fd, local_path = tempfile.mkstemp(suffix=suffix, prefix="fw_")
        os.close(fd)
        self._temp_files.append(local_path)

        try:
            self._log.debug("Downloading %s/%s -> %s", bucket, storage_key, local_path)
            minio.fget_object(bucket, storage_key, local_path)
            size = os.path.getsize(local_path)
            self._log.debug("Downloaded %d bytes", size)
            return local_path
        except Exception as e:
            # Cleanup on failure
            if os.path.exists(local_path):
                os.unlink(local_path)
            try:
                self._temp_files.remove(local_path)
            except ValueError:
                pass
            raise RuntimeError(f"Failed to download {storage_key}: {e}") from e

    def _upload_to_mtib(self, local_path: str, target: str, mtib_name: str) -> None:
        """Upload local file to MTIB server."""
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Firmware file not found: {local_path}")

        # Map target string to HostType
        target_map = {
            "nrf52840": HostType.HOST_TYPE_NRF52840,
            "nrf9151": HostType.HOST_TYPE_NRF9151,
            "nrf9160": HostType.HOST_TYPE_NRF9160,
            "nrf9151_modem": HostType.HOST_TYPE_NRF9151_MODEM,
            "nrf9160_modem": HostType.HOST_TYPE_NRF9160_MODEM,
        }

        host_type = target_map.get(target)
        if host_type is None:
            raise ValueError(f"Unknown target: {target}")

        err = self._mtib.UploadFwFile(local_path, host_type)
        if err:
            raise RuntimeError(f"Failed to upload {local_path} to MTIB: {err}")


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: create from environment (for K8s jobs)
# ─────────────────────────────────────────────────────────────────────────────

def get_firmware_path_from_env() -> Optional[str]:
    """Get firmware MinIO path from FIRMWARE_BUCKET_FILE_PATH env var.

    Used by K8s validation jobs where firmware path is injected.
    """
    return os.environ.get("FIRMWARE_BUCKET_FILE_PATH")
