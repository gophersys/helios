"""Firmware asset management for validation tests.

Provides two main classes:
- FirmwareAssetManager: Downloads firmware from MinIO and uploads to MTIB server.
- PipelineAssets: Fetches build artifacts from Concord CI pipeline API.

Storage layout in MinIO (firmware/builds prefix):
    firmware/builds/{product}/{build_id}/{filename}
    firmware/builds/alpha_fw/abc123/app_nrf52840.hex
    firmware/builds/alpha_fw/abc123/comms_nrf9151.hex

Environment variables:
    STORAGE_URL:               MinIO endpoint (e.g., http://minio:9000)
    STORAGE_ACCESS_KEY:        MinIO access key
    STORAGE_SECRET_ACCESS_KEY: MinIO secret key
    STORAGE_BUCKET:            Bucket name (default: concord)
    FIRMWARE_BUCKET_FILE_PATH: Path to firmware in MinIO (optional, for K8s jobs)
    CONCORD_API_URL:           Concord HTTP API base URL (for PipelineAssets)
    CONCORD_API_KEY:           API key for auth (for PipelineAssets)
    PIPELINE_ID:               Pipeline to fetch builds from (for PipelineAssets)

Example usage:
    # FirmwareAssetManager (standalone)
    assets = FirmwareAssetManager(mtib=client)
    hex_name = assets.fetch_and_upload("firmware/builds/alpha_fw/abc123/app_nrf52840.hex")
    assets.cleanup()

    # PipelineAssets (CI pipeline)
    pipeline = PipelineAssets(pipeline_id="cmmk9o8zh00008785xh9ltn0d")
    mfg_app = pipeline.get_hex("MFG_BASE", "app")
    cfw_files = pipeline.get_cfw_files("MFG_BUMP")
"""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

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
    STORAGE_BUCKET: str = "concord"

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
            except Exception:
                pass

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
        target: str = "nrf52840",
        mtib_name: Optional[str] = None,
    ) -> str:
        """Download firmware from MinIO and upload to MTIB server.

        Args:
            storage_key: Full MinIO object key (e.g., "firmware/builds/alpha/abc/app.hex")
            target: MTIB target type ("nrf52840", "nrf9151", "nrf9151_modem")
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
        target: str = "nrf52840",
        mtib_name: Optional[str] = None,
    ) -> str:
        """Upload a local firmware file to MTIB server (bypasses MinIO).

        Useful for local development or when firmware is already on disk.

        Args:
            local_path: Path to local .hex/.zip file
            target: MTIB target type ("nrf52840", "nrf9151", "nrf9151_modem")
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
        from protocols.mtib.mtib_pb2 import FwFileInfo, HostType

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
            self._temp_files.remove(path)

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

        bucket = self._config.STORAGE_BUCKET

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
            self._temp_files.remove(local_path)
            raise RuntimeError(f"Failed to download {storage_key}: {e}") from e

    def _upload_to_mtib(self, local_path: str, target: str, mtib_name: str) -> None:
        """Upload local file to MTIB server."""
        from protocols.mtib.mtib_pb2 import HostType

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


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Assets (merged from pipeline_assets.py)
# ─────────────────────────────────────────────────────────────────────────────

_pipeline_log = Logger(log_name="pipeline_assets")


class _PipelineConfig(EnvConfig):
    """Pipeline assets configuration."""
    ENV_PREFIX = ""

    CONCORD_API_URL: Optional[str] = None
    CONCORD_API_KEY: Optional[str] = None
    PIPELINE_ID: Optional[str] = None

    STORAGE_URL: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_ACCESS_KEY: Optional[str] = None
    STORAGE_BUCKET: str = "concord"


@dataclass
class BuildArtifact:
    """A single build artifact from the pipeline."""
    id: str
    name: str
    storage_key: str
    size_bytes: int
    checksum: str
    local_path: Optional[str] = None  # Set after download


@dataclass
class PipelineBuild:
    """A build job from the pipeline."""
    id: str
    product: str
    variant: str
    status: str
    matrix_label: str
    matrix_index: int
    version_string: Optional[str] = None
    artifacts: List[BuildArtifact] = field(default_factory=list)

    def get_artifact(self, name_pattern: str) -> Optional[BuildArtifact]:
        """Find artifact by name pattern (e.g., 'app_nrf52840.hex', '.cfw')."""
        for a in self.artifacts:
            if name_pattern in a.name:
                return a
        return None

    def get_hex(self, target: str) -> Optional[BuildArtifact]:
        """Get hex file for target ('app' or 'comms').

        Supports both new naming (109.0.8.1.hex / 108.0.8.1.hex)
        and legacy naming (app_nrf52840.hex / comms_nrf9151.hex).
        """
        # App ID mapping: 109=nRF52840 (app), 108=nRF9151 (comms)
        app_id = {"app": "109.", "comms": "108."}.get(target)
        if app_id:
            # Try new versioned naming first
            for a in self.artifacts:
                if a.name.startswith(app_id) and a.name.endswith(".hex"):
                    return a
        # Fallback to legacy naming
        legacy = {
            "app": ["app_nrf52840.hex", "nrf52840.hex"],
            "comms": ["comms_nrf9151.hex", "comms_nrf9160.hex", "nrf9151.hex", "nrf9160.hex"],
        }
        for pattern in legacy.get(target, [target]):
            a = self.get_artifact(pattern)
            if a:
                return a
        return None

    def get_cfw_files(self) -> List[BuildArtifact]:
        """Get all CFW files from this build."""
        return [a for a in self.artifacts if a.name.endswith(".cfw")]


class PipelineAssets:
    """Fetches and manages firmware assets from a CI pipeline.

    Connects to Concord API to get pipeline builds, then downloads
    artifacts from MinIO as needed.
    """

    def __init__(
        self,
        pipeline_id: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        self._config = _PipelineConfig()
        self._log = logger.from_parent("pipeline_assets") if logger else _pipeline_log

        self._pipeline_id = pipeline_id or self._config.PIPELINE_ID
        if not self._pipeline_id:
            raise ValueError("pipeline_id required (or set PIPELINE_ID env var)")

        self._api_url = self._config.CONCORD_API_URL
        self._api_key = self._config.CONCORD_API_KEY

        # Lazy-init
        self._minio: Optional[Minio] = None
        self._pipeline_data: Optional[Dict[str, Any]] = None
        self._builds: Dict[str, PipelineBuild] = {}  # matrixLabel -> build
        self._temp_files: List[str] = []

    def __del__(self):
        self.cleanup()

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline API
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_pipeline(self) -> Dict[str, Any]:
        """Fetch pipeline data from Concord API."""
        if self._pipeline_data:
            return self._pipeline_data

        if not self._api_url:
            raise RuntimeError("CONCORD_API_URL not configured")

        url = f"{self._api_url.rstrip('/')}/v2/builds/pipelines/{self._pipeline_id}"
        headers = {}
        if self._api_key:
            # API keys (ck_*) use ApiKey prefix, JWTs use Bearer
            if self._api_key.startswith("ck_"):
                headers["Authorization"] = f"ApiKey {self._api_key}"
            else:
                headers["Authorization"] = f"Bearer {self._api_key}"

        self._log.info("Fetching pipeline %s from %s", self._pipeline_id, self._api_url)
        resp = requests.get(url, headers=headers, timeout=30)

        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch pipeline: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        if "data" in data:
            data = data["data"]

        self._pipeline_data = data
        self._parse_builds(data.get("builds", []))
        return data

    def _fetch_build_artifacts(self, build_id: str) -> List[BuildArtifact]:
        """Fetch artifacts for a specific build from the API."""
        if not self._api_url:
            return []

        url = f"{self._api_url.rstrip('/')}/v2/builds/{build_id}/artifacts"
        headers = {}
        if self._api_key:
            if self._api_key.startswith("ck_"):
                headers["Authorization"] = f"ApiKey {self._api_key}"
            else:
                headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                self._log.warning("Failed to fetch artifacts for build %s: %s", build_id, resp.status_code)
                return []

            data = resp.json()
            if "data" in data:
                data = data["data"]

            artifacts = []
            for a in data:
                artifacts.append(BuildArtifact(
                    id=a["id"],
                    name=a["name"],
                    storage_key=a["storageKey"],
                    size_bytes=a.get("sizeBytes", 0),
                    checksum=a.get("checksum", ""),
                ))
            return artifacts
        except Exception as e:
            self._log.warning("Error fetching artifacts for build %s: %s", build_id, e)
            return []

    def _parse_builds(self, builds_data: List[Dict[str, Any]]) -> None:
        """Parse builds from pipeline response."""
        for b in builds_data:
            label = b.get("matrixLabel")
            if not label:
                continue

            # Artifacts may be inline or need to be fetched separately
            artifacts = []
            inline_artifacts = b.get("artifacts", [])
            if inline_artifacts:
                # Use inline artifacts if present
                for a in inline_artifacts:
                    artifacts.append(BuildArtifact(
                        id=a["id"],
                        name=a["name"],
                        storage_key=a["storageKey"],
                        size_bytes=a.get("sizeBytes", 0),
                        checksum=a.get("checksum", ""),
                    ))
            elif b.get("artifactCount", 0) > 0:
                # Fetch artifacts separately if count > 0 but not inline
                self._log.debug("Fetching artifacts for build %s (%d expected)", label, b["artifactCount"])
                artifacts = self._fetch_build_artifacts(b["id"])

            build = PipelineBuild(
                id=b["id"],
                product=b["product"],
                variant=b.get("variant", ""),
                status=b["status"],
                matrix_label=label,
                matrix_index=b.get("matrixIndex", 0),
                version_string=b.get("versionString"),
                artifacts=artifacts,
            )
            self._builds[label] = build
            self._log.debug(
                "Loaded build %s: %s %s (%d artifacts)",
                label, build.product, build.variant, len(artifacts)
            )

    # ─────────────────────────────────────────────────────────────────────────
    # MinIO
    # ─────────────────────────────────────────────────────────────────────────

    def _get_minio(self) -> Minio:
        """Lazy-init MinIO client."""
        if self._minio:
            return self._minio

        if not _HAS_MINIO:
            raise RuntimeError("minio package not installed")

        if not self._config.STORAGE_URL:
            raise RuntimeError("STORAGE_URL not configured")

        parsed = urlparse(self._config.STORAGE_URL)
        self._minio = Minio(
            endpoint=parsed.netloc,
            access_key=self._config.STORAGE_ACCESS_KEY or "",
            secret_key=self._config.STORAGE_SECRET_ACCESS_KEY or "",
            secure=(parsed.scheme == "https"),
        )
        return self._minio

    def _download(self, storage_key: str) -> str:
        """Download file from MinIO to temp location."""
        minio = self._get_minio()
        bucket = self._config.STORAGE_BUCKET

        suffix = Path(storage_key).suffix or ".bin"
        fd, local_path = tempfile.mkstemp(suffix=suffix, prefix="fw_")
        os.close(fd)
        self._temp_files.append(local_path)

        self._log.info("Downloading %s/%s -> %s", bucket, storage_key, local_path)
        minio.fget_object(bucket, storage_key, local_path)
        return local_path

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    @property
    def builds(self) -> Dict[str, PipelineBuild]:
        """Get all builds indexed by matrixLabel. Fetches pipeline if needed."""
        if not self._builds:
            self._fetch_pipeline()
        return self._builds

    def get_build(self, matrix_label: str) -> PipelineBuild:
        """Get a specific build by matrixLabel."""
        builds = self.builds
        if matrix_label not in builds:
            raise KeyError(f"Build not found: {matrix_label}. Available: {list(builds.keys())}")
        return builds[matrix_label]

    def get_hex(self, matrix_label: str, target: str) -> str:
        """Download hex file for a build and return local path.

        Args:
            matrix_label: e.g., "MFG_BASE", "FUT_DEBUG_A"
            target: "app" (nRF52840) or "comms" (nRF9151)

        Returns:
            Local file path to the downloaded hex.
        """
        build = self.get_build(matrix_label)
        self._log.info(
            "get_hex: build=%s has %d artifacts: %s",
            matrix_label,
            len(build.artifacts),
            [a.name for a in build.artifacts]
        )
        artifact = build.get_hex(target)
        if not artifact:
            raise ValueError(f"No {target} hex found in build {matrix_label}. Artifacts: {[a.name for a in build.artifacts]}")

        if not artifact.local_path:
            artifact.local_path = self._download(artifact.storage_key)

        return artifact.local_path

    def get_cfw_files(self, matrix_label: str) -> List[str]:
        """Download all CFW files for a build and return local paths.

        Args:
            matrix_label: e.g., "MFG_BUMP", "FUT_DEBUG_A"

        Returns:
            List of local file paths to the downloaded CFW files.
        """
        build = self.get_build(matrix_label)
        cfw_artifacts = build.get_cfw_files()
        if not cfw_artifacts:
            raise ValueError(f"No CFW files found in build {matrix_label}")

        paths = []
        for a in cfw_artifacts:
            if not a.local_path:
                a.local_path = self._download(a.storage_key)
            paths.append(a.local_path)

        return paths

    def get_version(self, matrix_label: str) -> Optional[str]:
        """Get version string for a build."""
        build = self.get_build(matrix_label)
        return build.version_string

    def upload_to_mtib(self, local_path: str, mtib, target: str = "nrf52840") -> str:
        """Upload a local file to MTIB server.

        Args:
            local_path: Path to local hex/cfw file.
            mtib: MtibV1Client instance.
            target: MTIB target type.

        Returns:
            Filename on MTIB server.
        """
        from protocols.mtib.mtib_pb2 import HostType

        target_map = {
            "nrf52840": HostType.HOST_TYPE_NRF52840,
            "app": HostType.HOST_TYPE_NRF52840,
            "nrf9151": HostType.HOST_TYPE_NRF9151,
            "comms": HostType.HOST_TYPE_NRF9151,
            "nrf9160": HostType.HOST_TYPE_NRF9160,
        }

        host_type = target_map.get(target.lower())
        if not host_type:
            raise ValueError(f"Unknown target: {target}")

        err = mtib.UploadFwFile(local_path, host_type)
        if err:
            raise RuntimeError(f"Upload failed: {err}")

        return Path(local_path).name

    def cleanup(self) -> None:
        """Delete downloaded temp files."""
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass
            self._temp_files.remove(path)

    # ─────────────────────────────────────────────────────────────────────────
    # Stage 4 helpers
    # ─────────────────────────────────────────────────────────────────────────

    def get_fuota_transitions(self) -> List[tuple]:
        """Get the FUOTA transition sequence for this pipeline.

        Returns list of (from_label, to_label, purpose) tuples.
        Only returns transitions where:
        - The "to" build is a version_bump of the "from" build
        - Both builds have CFW files (produces_cfw=True)

        Stage 5 defines 4 valid FUOTA transitions:
        - MFG_BASE -> MFG_BUMP (sanity test: same code, bumped version)
        - FUT_DEBUG_A -> FUT_DEBUG_B (debug build FUOTA)
        - FUT_RELEASE_A -> FUT_RELEASE_B (release build FUOTA)
        - MAIN_BASELINE -> MAIN_MERGED (field upgrade path)
        """
        # These are the only valid FUOTA transitions per stage_builds.py
        # (where is_version_bump=True and base_label points to from_build)
        return [
            ("MFG_BASE", "MFG_BUMP", "MFG FUOTA sanity (same code, bumped version)"),
            ("FUT_DEBUG_A", "FUT_DEBUG_B", "Debug build FUOTA"),
            ("FUT_RELEASE_A", "FUT_RELEASE_B", "Release build FUOTA"),
            ("MAIN_BASELINE", "MAIN_MERGED", "Field upgrade path (main -> merged)"),
        ]

    def has_all_builds(self) -> bool:
        """Check if all 8 Stage 4 builds are present and completed."""
        required = [
            "MFG_BASE", "MFG_BUMP",
            "FUT_DEBUG_A", "FUT_DEBUG_B",
            "FUT_RELEASE_A", "FUT_RELEASE_B",
            "MAIN_BASELINE", "MAIN_MERGED",
        ]
        builds = self.builds
        for label in required:
            if label not in builds:
                return False
            if builds[label].status != "SUCCESS":
                return False
        return True

    def summary(self) -> str:
        """Return a summary of the pipeline builds."""
        lines = [f"Pipeline: {self._pipeline_id}"]
        for label, build in sorted(self.builds.items(), key=lambda x: x[1].matrix_index):
            status = "OK" if build.status == "SUCCESS" else "FAIL"
            artifacts = ", ".join(a.name for a in build.artifacts[:3])
            if len(build.artifacts) > 3:
                artifacts += f" (+{len(build.artifacts) - 3} more)"
            lines.append(f"  [{build.matrix_index}] {status} {label}: {build.version_string or '?'} - {artifacts}")
        return "\n".join(lines)
