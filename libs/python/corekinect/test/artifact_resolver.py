"""Product-agnostic artifact resolution via build.json manifests.

Artifacts are discovered through the manifest's targets[] array --
no hardcoded App IDs, chip names, or filename conventions.

All artifact downloads go through the Concord HTTP API — this library
NEVER accesses storage (MinIO/S3) directly.

    resolver = ArtifactResolver("run-42", api_url, api_key)
    app_hex = resolver.get_artifact("mfg_base", role="app", artifact_type="plaintextHex")
    cfws = resolver.get_artifacts("mfg_base", artifact_type="encryptedCfw")
"""

import json
import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests

from corekinect.utils import Logger

log = Logger(log_name="artifact_resolver")


# =============================================================================
# Manifest data model
# =============================================================================


@dataclass
class ManifestTarget:
    """Single build target from a build.json manifest (role, processor, app ID, artifacts)."""

    role: str
    processor: str
    app_id: int
    host_type: str
    jlink_family: str
    plaintext_hex: Optional[str]
    encrypted_cfw: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "ManifestTarget":
        """From dict."""
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
    """Parsed build.json manifest with targets, version, and corecloud metadata."""

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
    def from_dict(cls, data: dict, artifact_names: Optional[List[str]] = None) -> "BuildManifest":
        """From dict."""
        schema = data.get("schemaVersion", 0)

        if schema == 1:
            targets = [ManifestTarget.from_dict(t) for t in data.get("targets", [])]
            corecloud = data.get("corecloud", {})
        elif schema == 0:
            # Legacy build.json — infer targets from artifact filenames
            targets = cls._infer_targets_from_artifacts(data, artifact_names or [])
            corecloud = {}
        else:
            raise ValueError(
                f"Unsupported build.json schema version {schema}. "
                f"Expected 0 or 1. Update ArtifactResolver or regenerate manifests."
            )

        return cls(
            schema_version=schema,
            product=data.get("product", ""),
            board=data.get("board", ""),
            version=data.get("version", ""),
            variant=data.get("variant", ""),
            track=data.get("track", data.get("cfw_track", "")),
            release_track=data.get("releaseTrack", ""),
            ncs_version=data.get("ncsVersion", ""),
            commit_sha=data.get("commitSha", ""),
            branch=data.get("branch", ""),
            built_at=data.get("builtAt", data.get("built_at", "")),
            targets=targets,
            modem_firmware=data.get("modemFirmware"),
            corecloud=corecloud,
            signing=data.get("signing"),
            _raw=data,
        )

    @staticmethod
    def _infer_targets_from_artifacts(
        data: dict, artifact_names: List[str]
    ) -> List["ManifestTarget"]:
        """Infer targets from legacy artifact filenames ({appId}.{version}-{track}.{ext})."""
        # Map of known app IDs to role/processor/hostType/jlinkFamily
        APP_ID_MAP = {
            109: ("app", "nrf52840", "HOST_TYPE_NRF52840", "NRF52"),
            108: ("comms", "nrf9151", "HOST_TYPE_NRF9151", "NRF91"),
        }

        # Find hex/cfw files and group by app ID
        app_id_files: Dict[int, Dict[str, str]] = {}
        for name in artifact_names:
            if not (name.endswith(".hex") or name.endswith(".cfw")):
                continue
            # Parse: {appId}.{rest}
            parts = name.split(".", 1)
            if not parts[0].isdigit():
                continue
            app_id = int(parts[0])
            if app_id not in app_id_files:
                app_id_files[app_id] = {}
            if name.endswith(".hex"):
                app_id_files[app_id]["hex"] = name
            elif name.endswith(".cfw"):
                app_id_files[app_id]["cfw"] = name

        targets = []
        for app_id in sorted(app_id_files.keys()):
            files = app_id_files[app_id]
            if app_id in APP_ID_MAP:
                role, processor, host_type, jlink_family = APP_ID_MAP[app_id]
            else:
                role = f"target_{app_id}"
                processor = "unknown"
                host_type = "unknown"
                jlink_family = "unknown"

            targets.append(ManifestTarget(
                role=role,
                processor=processor,
                app_id=app_id,
                host_type=host_type,
                jlink_family=jlink_family,
                plaintext_hex=files.get("hex"),
                encrypted_cfw=files.get("cfw"),
            ))

        return targets

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
        """Device type id."""
        return self.corecloud.get("deviceTypeId", 0)

    @property
    def device_variant_id(self) -> int:
        """Device variant id."""
        return self.corecloud.get("deviceVariantId", 0)

    @property
    def api_env(self) -> str:
        """Api env."""
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
        """Has manifest."""
        return any(a.name == "build.json" for a in self.artifacts)

    def get_manifest_artifact(self) -> Optional[_ArtifactInfo]:
        """Get manifest artifact."""
        for a in self.artifacts:
            if a.name == "build.json":
                return a
        return None

    def find_artifact_by_name(self, name: str) -> Optional[_ArtifactInfo]:
        """Find artifact by name."""
        for a in self.artifacts:
            if a.name == name:
                return a
        return None

    def find_artifacts_by_extension(self, ext: str) -> List[_ArtifactInfo]:
        """Find artifacts by extension."""
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
    """Fetch build run builds and resolve artifacts by role + type.

    All artifact discovery goes through build.json manifests --
    no hardcoded filenames or app IDs.

    All downloads go through the Concord HTTP API -- no direct storage access.
    """

    def __init__(
        self,
        build_run_id: str,
        api_url: str,
        api_key: str,
        logger: Optional[Logger] = None,
        **kwargs,
    ):
        # Warn about deprecated storage_config parameter
        """  init  ."""
        if "storage_config" in kwargs:
            warnings.warn(
                "storage_config parameter is deprecated and ignored. "
                "ArtifactResolver now downloads exclusively via the HTTP API.",
                DeprecationWarning,
                stacklevel=2,
            )

        self._build_run_id = build_run_id
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._log = logger.from_parent("artifact_resolver") if logger else log

        # HTTP session
        self._session = requests.Session()
        auth_prefix = "ApiKey" if api_key.startswith("ck_") else "Bearer"
        self._session.headers["Authorization"] = f"{auth_prefix} {api_key}"

        # Lazy state
        self._builds: Dict[str, _BuildInfo] = {}
        self._manifests: Dict[str, BuildManifest] = {}
        self._builds_fetched = False

        # Temp file tracking for cleanup
        self._temp_files: List[str] = []
        self._temp_dirs: List[str] = []

    # ─────────────────────────────────────────────────────────────────────
    # Build run + build fetching
    # ─────────────────────────────────────────────────────────────────────

    def _ensure_builds(self) -> None:
        """Fetch build run builds if not yet loaded."""
        if self._builds_fetched:
            return

        url = f"{self._api_url}/v2/builds/runs/{self._build_run_id}"
        self._log.info("Fetching build run %s", self._build_run_id)

        resp = self._session.get(url, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch build run: {resp.status_code} {resp.text[:200]}"
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

        self._builds_fetched = True

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
        self._ensure_builds()
        if label not in self._builds:
            available = list(self._builds.keys())
            raise KeyError(
                f"Build not found: '{label}'. Available: {available}"
            )
        return self._builds[label]

    # ─────────────────────────────────────────────────────────────────────
    # File download (via HTTP API only)
    # ─────────────────────────────────────────────────────────────────────

    def _download_artifact(self, build_id: str, artifact_name: str) -> str:
        """Download an artifact via the HTTP API. Returns local path.

        Uses GET /v2/builds/<build_id>/artifacts/<name> which streams
        the file from server-side storage.
        """
        url = f"{self._api_url}/v2/builds/{build_id}/artifacts/{artifact_name}"
        self._log.info("Downloading %s from build %s", artifact_name, build_id)

        resp = self._session.get(url, timeout=120, stream=True)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to download artifact '{artifact_name}' from build "
                f"{build_id}: {resp.status_code}"
            )

        temp_dir = tempfile.mkdtemp(prefix="resolver_")
        self._temp_dirs.append(temp_dir)
        local_path = os.path.join(temp_dir, artifact_name)

        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return local_path

    def _ensure_artifact_downloaded(self, artifact: _ArtifactInfo, build_id: str) -> str:
        """Download artifact if not already cached. Return local path."""
        if artifact.local_path and os.path.exists(artifact.local_path):
            return artifact.local_path

        local_path = self._download_artifact(build_id, artifact.name)
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

        local_path = self._ensure_artifact_downloaded(manifest_artifact, build.id)
        with open(local_path) as f:
            data = json.load(f)

        # Pass artifact names so legacy manifests can infer targets
        artifact_names = [a.name for a in build.artifacts]
        return BuildManifest.from_dict(data, artifact_names=artifact_names)

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

        return self._ensure_artifact_downloaded(artifact, build.id)

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    @property
    def build_run_id(self) -> str:
        """Build run id."""
        return self._build_run_id

    @property
    def builds(self) -> Dict[str, _BuildInfo]:
        """All builds indexed by matrix label."""
        self._ensure_builds()
        return self._builds

    def get_manifest(self, label: str) -> BuildManifest:
        """Return parsed BuildManifest. Raises KeyError/ValueError if missing."""
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
        """Download artifact and return local path.

        Args:
            label: Build matrix label (e.g., "mfg_base").
            role: "app" or "comms".
            artifact_type: "plaintextHex" or "encryptedCfw".
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
        """Download all artifacts of a type from a build. Returns local paths."""
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
                paths.append(self._ensure_artifact_downloaded(artifact, build.id))
        return paths

    def get_targets(self, label: str) -> List[ManifestTarget]:
        """Return all ManifestTargets for a build label."""
        manifest = self.get_manifest(label)
        return manifest.targets

    def get_target(self, label: str, role: str) -> Optional[ManifestTarget]:
        """Return ManifestTarget by role, or None if not found."""
        manifest = self.get_manifest(label)
        return manifest.get_target(role)

    def get_version(self, label: str) -> str:
        """Return version string for a build label."""
        build = self._get_build(label)
        manifest = self._get_or_load_manifest(label)
        if manifest is not None:
            return manifest.version
        return build.version_string or ""

    def get_modem_firmware(self, label: str) -> Optional[str]:
        """Download modem firmware from the manifest. Returns local path or None."""
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

        return self._ensure_artifact_downloaded(artifact, build.id)

    @property
    def modem_firmware_info(self) -> Optional[Dict[str, Any]]:
        """Return modem firmware metadata without downloading. None if unavailable."""
        # Try triggerData first
        self._ensure_builds()
        url = f"{self._api_url}/v2/builds/runs/{self._build_run_id}"
        try:
            resp = self._session.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    data = data["data"]
                trigger_data = data.get("triggerData") or {}
                modem = trigger_data.get("modemFirmware")
                if modem:
                    return modem
        except Exception as exc:
            self._log.warning("Failed to fetch modem firmware info from build run: %s", exc)

        # Fall back to build manifests
        for label in self._builds:
            manifest = self._get_or_load_manifest(label)
            if manifest and manifest.modem_firmware:
                return manifest.modem_firmware

        return None

    def get_modem_from_asset_set(self) -> Optional[str]:
        """Download modem firmware from the AssetSet's modemFirmware reference.

        Calls GET /v2/asset-sets/{id} to get the modem firmware storageKey,
        then downloads the file from MinIO via the storage download endpoint.

        Requires ASSET_SET_ID env var. Returns None if not set or if the
        asset set has no modem firmware reference.
        """
        asset_set_id = os.environ.get("ASSET_SET_ID")
        if not asset_set_id:
            return None

        try:
            url = f"{self._api_url}/v2/asset-sets/{asset_set_id}"
            resp = self._session.get(url, timeout=10)
            if resp.status_code != 200:
                self._log.debug(
                    "Asset set %s fetch failed: %s", asset_set_id, resp.status_code,
                )
                return None

            data = resp.json()
            if "data" in data:
                data = data["data"]

            modem_fw = data.get("modemFirmware")
            if not modem_fw or not modem_fw.get("storageKey"):
                return None

            storage_key = modem_fw["storageKey"]
            filename = modem_fw.get("filename", "modem_firmware.zip")

            # Download via the storage download endpoint (same pattern as AssetSetResolver)
            download_url = f"{self._api_url}/v2/storage/download"
            resp = self._session.get(
                download_url, params={"key": storage_key}, timeout=120, stream=True,
            )
            if resp.status_code != 200:
                self._log.warning(
                    "Failed to download modem firmware from %s: %s",
                    storage_key, resp.status_code,
                )
                return None

            temp_dir = tempfile.mkdtemp(prefix="resolver_modem_")
            self._temp_dirs.append(temp_dir)
            local_path = os.path.join(temp_dir, filename)

            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            self._log.info("Downloaded modem firmware: %s → %s", storage_key, local_path)
            return local_path
        except Exception as e:
            self._log.warning("Failed to resolve modem firmware from asset set: %s", e)
            return None

    def get_modem_firmware_from_trigger(self) -> Optional[str]:
        """Deprecated: modem firmware should be managed via BoardRevision and
        included in AssetSets automatically. Returns None.
        """
        warnings.warn(
            "get_modem_firmware_from_trigger() is deprecated. Modem firmware "
            "is now managed via BoardRevision and included in AssetSets "
            "during build promotion. Use get_modem_firmware(label) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return None

    def has_all_builds(self) -> bool:
        """Return True if all build run builds are SUCCESS or CACHED."""
        builds = self.builds
        if len(builds) < 2:
            return False

        for label, build in builds.items():
            if build.status not in ("SUCCESS", "CACHED"):
                return False

        return True

    def summary(self) -> str:
        """Return human-readable summary of build run builds."""
        lines = [f"Build run: {self._build_run_id}"]
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
        """Remove all downloaded temp files."""
        for path in list(self._temp_dirs):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception as exc:
                self._log.warning("Failed to remove temp dir %s: %s", path, exc)
        self._temp_dirs.clear()

        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception as exc:
                self._log.warning("Failed to remove temp file %s: %s", path, exc)
        self._temp_files.clear()

    def __del__(self):
        """  del  ."""
        try:
            self.cleanup()
        except Exception as exc:
            self._log.warning("Error during artifact resolver cleanup: %s", exc)
