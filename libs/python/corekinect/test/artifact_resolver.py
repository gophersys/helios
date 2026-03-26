"""Product-agnostic artifact resolution for validation tests.

Every artifact is discovered through the build.json manifest's targets[] array
— no hardcoded App IDs, chip names, or filename conventions.

Usage:
    resolver = ArtifactResolver(
        pipeline_id="build-42",
        api_url="https://concord.local",
        api_key="ck_run_..."
    )

    # Get parsed manifest
    manifest = resolver.get_manifest("MFG_BASE")

    # Download artifact by role + type
    app_hex = resolver.get_artifact("MFG_BASE", role="app", artifact_type="plaintextHex")

    # Get all CFWs
    cfws = resolver.get_artifacts("MFG_BASE", artifact_type="encryptedCfw")

    # Get target metadata without downloading
    target = resolver.get_target("MFG_BASE", role="app")
    # target.app_id == 109, target.host_type == "HOST_TYPE_NRF52840"
"""

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

from corekinect.utils import Logger

log = Logger(log_name="artifact_resolver")

# Optional MinIO import
try:
    from minio import Minio
    _HAS_MINIO = True
except ImportError:
    _HAS_MINIO = False


# =============================================================================
# Storage configuration
# =============================================================================


@dataclass
class StorageConfig:
    """MinIO storage configuration."""

    url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    bucket_name: str = "concord"

    @classmethod
    def from_env(cls) -> "StorageConfig":
        return cls(
            url=os.environ.get("STORAGE_URL"),
            access_key=os.environ.get("STORAGE_ACCESS_KEY"),
            secret_key=os.environ.get("STORAGE_SECRET_ACCESS_KEY"),
            bucket_name=os.environ.get("STORAGE_BUCKET_NAME", "concord"),
        )


# =============================================================================
# Manifest data model
# =============================================================================


@dataclass
class ManifestTarget:
    """A single build target from the build.json manifest."""

    role: str
    processor: str
    app_id: int
    host_type: str
    jlink_family: str
    plaintext_hex: Optional[str]
    encrypted_cfw: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "ManifestTarget":
        return cls(
            role=data["role"],
            processor=data["processor"],
            app_id=data["appId"],
            host_type=data["hostType"],
            jlink_family=data["jlinkFamily"],
            plaintext_hex=data.get("plaintextHex"),
            encrypted_cfw=data.get("encryptedCfw"),
        )

    def get_file_for_type(self, artifact_type: str) -> Optional[str]:
        """Get the filename for an artifact type."""
        if artifact_type == "plaintextHex":
            return self.plaintext_hex
        elif artifact_type == "encryptedCfw":
            return self.encrypted_cfw
        return None


@dataclass
class BuildManifest:
    """Parsed build.json manifest."""

    schema_version: int
    product: str
    board: str
    version: str
    variant: str
    track: str
    release_track: str
    ncs_version: str
    commit_sha: str
    branch: str
    built_at: str
    targets: List[ManifestTarget]
    modem_firmware: Optional[Dict[str, Any]]
    corecloud: Dict[str, Any]
    signing: Optional[Dict[str, Any]] = None

    # Raw dict for forward compatibility
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "BuildManifest":
        schema = data.get("schemaVersion", 0)
        if schema != 1:
            raise ValueError(
                f"Unsupported build.json schema version {schema}. "
                f"Expected 1. Update ArtifactResolver or regenerate manifests."
            )

        targets = [ManifestTarget.from_dict(t) for t in data.get("targets", [])]
        corecloud = data.get("corecloud", {})

        return cls(
            schema_version=schema,
            product=data.get("product", ""),
            board=data.get("board", ""),
            version=data.get("version", ""),
            variant=data.get("variant", ""),
            track=data.get("track", ""),
            release_track=data.get("releaseTrack", ""),
            ncs_version=data.get("ncsVersion", ""),
            commit_sha=data.get("commitSha", ""),
            branch=data.get("branch", ""),
            built_at=data.get("builtAt", ""),
            targets=targets,
            modem_firmware=data.get("modemFirmware"),
            corecloud=corecloud,
            signing=data.get("signing"),
            _raw=data,
        )

    def get_target(self, role: str) -> Optional[ManifestTarget]:
        """Find a target by role (e.g., 'app', 'comms')."""
        for t in self.targets:
            if t.role == role:
                return t
        return None

    @property
    def all_app_ids(self) -> Set[int]:
        """All app IDs from all targets."""
        return {t.app_id for t in self.targets}

    @property
    def device_type_id(self) -> int:
        return self.corecloud.get("deviceTypeId", 0)

    @property
    def device_variant_id(self) -> int:
        return self.corecloud.get("deviceVariantId", 0)

    @property
    def api_env(self) -> str:
        return self.corecloud.get("apiEnv", "")


# =============================================================================
# Internal: build + artifact data from API
# =============================================================================


@dataclass
class _ArtifactInfo:
    """An artifact record from the Concord API."""
    id: str
    name: str
    storage_key: str
    size_bytes: int
    checksum: str
    local_path: Optional[str] = None


@dataclass
class _BuildInfo:
    """A build record from the Concord API."""
    id: str
    product: str
    variant: str
    status: str
    matrix_label: str
    matrix_index: int
    version_string: Optional[str]
    artifacts: List[_ArtifactInfo] = field(default_factory=list)

    @property
    def has_manifest(self) -> bool:
        return any(a.name == "build.json" for a in self.artifacts)

    def get_manifest_artifact(self) -> Optional[_ArtifactInfo]:
        for a in self.artifacts:
            if a.name == "build.json":
                return a
        return None

    def find_artifact_by_name(self, name: str) -> Optional[_ArtifactInfo]:
        for a in self.artifacts:
            if a.name == name:
                return a
        return None

    def find_artifacts_by_extension(self, ext: str) -> List[_ArtifactInfo]:
        return [a for a in self.artifacts if a.name.endswith(ext)]


@dataclass
class ResolvedArtifact:
    """A resolved artifact with its local path and metadata."""
    local_path: str
    name: str
    role: Optional[str]
    artifact_type: Optional[str]
    storage_key: str


# =============================================================================
# ArtifactResolver
# =============================================================================


class ArtifactResolver:
    """Product-agnostic artifact resolver.

    Fetches pipeline builds from the Concord API, downloads build.json
    manifests, and resolves artifacts by role + type using the manifest's
    targets[] array.

    Every build must include a build.json manifest. Builds without a
    manifest are invalid and will raise an error.
    """

    def __init__(
        self,
        pipeline_id: str,
        api_url: str,
        api_key: str,
        storage_config: Optional[StorageConfig] = None,
        logger: Optional[Logger] = None,
    ):
        self._pipeline_id = pipeline_id
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._storage = storage_config or StorageConfig.from_env()
        self._log = logger.from_parent("artifact_resolver") if logger else log

        # HTTP session
        self._session = requests.Session()
        auth_prefix = "ApiKey" if api_key.startswith("ck_") else "Bearer"
        self._session.headers["Authorization"] = f"{auth_prefix} {api_key}"

        # Lazy state
        self._builds: Dict[str, _BuildInfo] = {}
        self._manifests: Dict[str, BuildManifest] = {}
        self._pipeline_fetched = False

        # MinIO client (lazy)
        self._minio: Optional[Any] = None

        # Temp file tracking for cleanup
        self._temp_files: List[str] = []
        self._temp_dirs: List[str] = []

    # ─────────────────────────────────────────────────────────────────────
    # Pipeline + build fetching
    # ─────────────────────────────────────────────────────────────────────

    def _ensure_pipeline(self) -> None:
        """Fetch pipeline builds if not yet loaded."""
        if self._pipeline_fetched:
            return

        url = f"{self._api_url}/v2/builds/pipelines/{self._pipeline_id}"
        self._log.info("Fetching pipeline %s", self._pipeline_id)

        resp = self._session.get(url, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch pipeline: {resp.status_code} {resp.text[:200]}"
            )

        data = resp.json()
        if "data" in data:
            data = data["data"]

        for b in data.get("builds", []):
            label = b.get("matrixLabel")
            if not label:
                continue

            artifacts = self._parse_artifacts(b)

            # If artifacts not inline and count > 0, fetch separately
            if not artifacts and b.get("artifactCount", 0) > 0:
                artifacts = self._fetch_build_artifacts(b["id"])
            elif not artifacts and b.get("reusedFromId"):
                artifacts = self._fetch_build_artifacts(b["reusedFromId"])

            build = _BuildInfo(
                id=b["id"],
                product=b.get("product", ""),
                variant=b.get("variant", ""),
                status=b["status"],
                matrix_label=label,
                matrix_index=b.get("matrixIndex", 0),
                version_string=b.get("versionString"),
                artifacts=artifacts,
            )
            self._builds[label] = build
            self._log.debug(
                "Build %s: %s v%s (%d artifacts, manifest=%s)",
                label, build.variant, build.version_string,
                len(artifacts), build.has_manifest,
            )

        self._pipeline_fetched = True

    def _parse_artifacts(self, build_data: dict) -> List[_ArtifactInfo]:
        """Parse inline artifacts from build data."""
        result = []
        for a in build_data.get("artifacts", []):
            result.append(_ArtifactInfo(
                id=a["id"],
                name=a["name"],
                storage_key=a["storageKey"],
                size_bytes=a.get("sizeBytes", 0),
                checksum=a.get("checksum", ""),
            ))
        return result

    def _fetch_build_artifacts(self, build_id: str) -> List[_ArtifactInfo]:
        """Fetch artifacts for a build from the API."""
        url = f"{self._api_url}/v2/builds/{build_id}/artifacts"
        try:
            resp = self._session.get(url, timeout=30)
            if resp.status_code != 200:
                self._log.warning("Failed to fetch artifacts for %s: %s", build_id, resp.status_code)
                return []

            data = resp.json()
            if "data" in data:
                data = data["data"]

            return [
                _ArtifactInfo(
                    id=a["id"],
                    name=a["name"],
                    storage_key=a["storageKey"],
                    size_bytes=a.get("sizeBytes", 0),
                    checksum=a.get("checksum", ""),
                )
                for a in data
            ]
        except Exception as e:
            self._log.warning("Error fetching artifacts for %s: %s", build_id, e)
            return []

    def _get_build(self, label: str) -> _BuildInfo:
        """Get a build by label, raising KeyError if not found."""
        self._ensure_pipeline()
        if label not in self._builds:
            available = list(self._builds.keys())
            raise KeyError(
                f"Build not found: '{label}'. Available: {available}"
            )
        return self._builds[label]

    # ─────────────────────────────────────────────────────────────────────
    # MinIO / file download
    # ─────────────────────────────────────────────────────────────────────

    def _get_minio(self):
        """Lazy-init MinIO client."""
        if self._minio is not None:
            return self._minio

        if not _HAS_MINIO:
            raise RuntimeError("minio package not installed")

        if not self._storage.url:
            raise RuntimeError("STORAGE_URL not configured")

        parsed = urlparse(self._storage.url)
        self._minio = Minio(
            endpoint=parsed.netloc,
            access_key=self._storage.access_key or "",
            secret_key=self._storage.secret_key or "",
            secure=(parsed.scheme == "https"),
        )
        return self._minio

    def _download_file(self, storage_key: str) -> str:
        """Download a file from MinIO, return local path."""
        minio = self._get_minio()
        bucket = self._storage.bucket_name

        # Preserve original filename
        original_name = Path(storage_key).name
        temp_dir = tempfile.mkdtemp(prefix="resolver_")
        self._temp_dirs.append(temp_dir)
        local_path = os.path.join(temp_dir, original_name)

        self._log.info("Downloading %s/%s", bucket, storage_key)
        minio.fget_object(bucket, storage_key, local_path)
        return local_path

    def _ensure_artifact_downloaded(self, artifact: _ArtifactInfo) -> str:
        """Download artifact if not already cached. Return local path."""
        if artifact.local_path and os.path.exists(artifact.local_path):
            return artifact.local_path

        local_path = self._download_file(artifact.storage_key)
        artifact.local_path = local_path
        return local_path

    # ─────────────────────────────────────────────────────────────────────
    # Manifest resolution
    # ─────────────────────────────────────────────────────────────────────

    def _load_manifest(self, build: _BuildInfo) -> Optional[BuildManifest]:
        """Download and parse build.json manifest for a build."""
        manifest_artifact = build.get_manifest_artifact()
        if manifest_artifact is None:
            return None

        local_path = self._ensure_artifact_downloaded(manifest_artifact)
        with open(local_path) as f:
            data = json.load(f)

        return BuildManifest.from_dict(data)

    def _get_or_load_manifest(self, label: str) -> Optional[BuildManifest]:
        """Get cached manifest or load from build."""
        if label in self._manifests:
            return self._manifests[label]

        build = self._get_build(label)
        manifest = self._load_manifest(build)

        if manifest is not None:
            self._manifests[label] = manifest

        return manifest

    def _resolve_artifact_from_manifest(
        self,
        build: _BuildInfo,
        manifest: BuildManifest,
        role: str,
        artifact_type: str,
    ) -> str:
        """Resolve and download an artifact using manifest metadata."""
        target = manifest.get_target(role)
        if target is None:
            available_roles = [t.role for t in manifest.targets]
            raise ValueError(
                f"No target with role='{role}' in build {build.matrix_label}. "
                f"Available roles: {available_roles}"
            )

        filename = target.get_file_for_type(artifact_type)
        if filename is None:
            raise ValueError(
                f"Target role='{role}' has no '{artifact_type}' artifact "
                f"in build {build.matrix_label}"
            )

        # filename is relative to build dir (e.g., "hex/109.0.8.3-BM.hex")
        # Find matching artifact by name (basename of the manifest path)
        basename = Path(filename).name
        artifact = build.find_artifact_by_name(basename)
        if artifact is None:
            # Try the full relative path as name
            artifact = build.find_artifact_by_name(filename)

        if artifact is None:
            raise ValueError(
                f"Artifact '{basename}' referenced by manifest not found in "
                f"build {build.matrix_label} artifacts. "
                f"Available: {[a.name for a in build.artifacts]}"
            )

        return self._ensure_artifact_downloaded(artifact)

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    @property
    def builds(self) -> Dict[str, _BuildInfo]:
        """All builds indexed by matrix label."""
        self._ensure_pipeline()
        return self._builds

    def get_manifest(self, label: str) -> BuildManifest:
        """Get parsed build.json manifest for a build.

        Returns:
            BuildManifest instance.

        Raises:
            KeyError: If build label not found.
            ValueError: If build has no build.json manifest.
        """
        manifest = self._get_or_load_manifest(label)

        if manifest is None:
            raise ValueError(
                f"Build '{label}' has no build.json manifest. "
                f"All builds must include a build.json manifest. "
                f"Regenerate this build with the current build worker."
            )

        return manifest

    def get_artifact(
        self,
        label: str,
        role: str,
        artifact_type: str,
    ) -> str:
        """Download and return local path to an artifact.

        Args:
            label: Build matrix label (e.g., "MFG_BASE", "PROD_VERBOSE")
            role: Target role (e.g., "app", "comms")
            artifact_type: "plaintextHex" or "encryptedCfw"

        Returns:
            Local file path to the downloaded artifact.

        Raises:
            KeyError: Build label not found.
            ValueError: Artifact not found for the given role + type,
                or build has no manifest.
        """
        build = self._get_build(label)
        manifest = self._get_or_load_manifest(label)

        if manifest is None or not manifest.targets:
            raise ValueError(
                f"Build '{label}' has no build.json manifest. "
                f"All builds must include a manifest."
            )

        return self._resolve_artifact_from_manifest(
            build, manifest, role, artifact_type
        )

    def get_artifacts(
        self,
        label: str,
        artifact_type: str,
    ) -> List[str]:
        """Download all artifacts of a type from a build.

        Returns:
            List of local file paths.

        Raises:
            KeyError: Build label not found.
            ValueError: Build has no manifest.
        """
        build = self._get_build(label)
        manifest = self._get_or_load_manifest(label)

        if manifest is None or not manifest.targets:
            raise ValueError(
                f"Build '{label}' has no build.json manifest. "
                f"All builds must include a manifest."
            )

        paths = []
        for target in manifest.targets:
            filename = target.get_file_for_type(artifact_type)
            if filename is None:
                continue
            basename = Path(filename).name
            artifact = build.find_artifact_by_name(basename)
            if artifact is None:
                artifact = build.find_artifact_by_name(filename)
            if artifact is not None:
                paths.append(self._ensure_artifact_downloaded(artifact))
        return paths

    def get_targets(self, label: str) -> List[ManifestTarget]:
        """Get all build targets from the manifest.

        Returns:
            List of ManifestTarget with role, processor, appId, hostType, etc.

        Raises:
            KeyError: Build label not found.
        """
        manifest = self.get_manifest(label)
        return manifest.targets

    def get_target(self, label: str, role: str) -> Optional[ManifestTarget]:
        """Get a single target by role.

        Returns:
            ManifestTarget or None if role not found.
        """
        manifest = self.get_manifest(label)
        return manifest.get_target(role)

    def get_version(self, label: str) -> str:
        """Get version string for a build."""
        build = self._get_build(label)
        manifest = self._get_or_load_manifest(label)
        if manifest is not None:
            return manifest.version
        return build.version_string or ""

    def get_modem_firmware(self, label: str) -> Optional[str]:
        """Download modem firmware from the manifest.

        Returns:
            Local path to modem firmware zip, or None if not specified.
        """
        build = self._get_build(label)
        manifest = self._get_or_load_manifest(label)

        if manifest is None or manifest.modem_firmware is None:
            return None

        modem_file = manifest.modem_firmware.get("file")
        if not modem_file:
            return None

        basename = Path(modem_file).name
        artifact = build.find_artifact_by_name(basename)
        if artifact is None:
            artifact = build.find_artifact_by_name(modem_file)
        if artifact is None:
            self._log.warning("Modem firmware '%s' not in build artifacts", modem_file)
            return None

        return self._ensure_artifact_downloaded(artifact)

    def get_modem_firmware_from_trigger(self) -> Optional[str]:
        """Download modem firmware from pipeline triggerData.

        Some pipelines carry modem firmware in triggerData rather than
        per-build manifests. This method handles that case.

        Returns:
            Local path or None.
        """
        self._ensure_pipeline()

        # Access raw pipeline data — we need triggerData
        url = f"{self._api_url}/v2/builds/pipelines/{self._pipeline_id}"
        try:
            resp = self._session.get(url, timeout=30)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if "data" in data:
                data = data["data"]
            trigger_data = data.get("triggerData") or {}
            modem = trigger_data.get("modemFirmware")
            if not modem or not modem.get("storageKey"):
                return None

            return self._download_file(modem["storageKey"])
        except Exception as e:
            self._log.warning("Failed to fetch modem firmware from triggerData: %s", e)
            return None

    def has_all_builds(self) -> bool:
        """Check if the pipeline has the minimum required builds."""
        builds = self.builds
        if len(builds) < 2:
            return False

        for label, build in builds.items():
            if build.status not in ("SUCCESS", "CACHED"):
                return False

        return True

    def summary(self) -> str:
        """Human-readable summary of pipeline builds."""
        lines = [f"Pipeline: {self._pipeline_id}"]
        for label, build in sorted(self.builds.items(), key=lambda x: x[1].matrix_index):
            status_icon = "OK" if build.status in ("SUCCESS", "CACHED") else "FAIL"
            manifest_flag = " [manifest]" if build.has_manifest else " [NO MANIFEST]"
            artifacts = ", ".join(a.name for a in build.artifacts[:3])
            if len(build.artifacts) > 3:
                artifacts += f" (+{len(build.artifacts) - 3} more)"
            lines.append(
                f"  [{build.matrix_index}] {status_icon} {label}: "
                f"v{build.version_string or '?'}{manifest_flag} - {artifacts}"
            )
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Remove all downloaded temp files and directories."""
        for path in list(self._temp_dirs):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
        self._temp_dirs.clear()

        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass
        self._temp_files.clear()

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
