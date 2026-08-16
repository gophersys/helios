"""Firmware resolution — unified source-agnostic firmware access.

Provides FirmwareSet: a single interface for accessing firmware hex files
regardless of whether they come from a Concord AssetSet, a CI BuildRun,
or local files. Tests never need to know the source.

Usage:
    fw = FirmwareSet.from_env()
    app_hex, comms_hex = fw.hex_pair("debug")

Resolution priority (auto-detected from environment):
    1. ASSET_SET_ID — downloads from Concord AssetSet API (manufacturing)
    2. BUILD_RUN_ID — downloads from build run artifacts (CI/validation)
    3. None — caller handles fallback (config filenames, skip, etc.)

The AssetSet path is completely independent of the build system. An AssetSet
is a collection of firmware files — they could come from CI, manual upload,
or an external build system. Manufacturing does not need to know how firmware
was built.
"""

import logging
import os
import shutil
import tempfile
from typing import Optional, Tuple

import requests

log = logging.getLogger("firmware_set")


class FirmwareSet:
    """Source-agnostic firmware file set.

    Provides hex() and hex_pair() for accessing firmware files.
    Downloads are lazy (on first access) and cached for the session lifetime.
    """

    def __init__(
        self,
        assets: list,
        api_url: str,
        api_key: str,
        source: str = "unknown",
        version: str = "",
    ):
        self._assets = assets
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._source = source
        self._version = version
        self._cache: dict = {}
        self._tmp_dir: Optional[str] = None

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Optional["FirmwareSet"]:
        """Auto-detect firmware source from environment.

        Returns None if no firmware source is configured.
        """
        api_url = api_url or os.environ.get("CONCORD_API_URL", "")
        api_key = api_key or os.environ.get("CONCORD_API_KEY", "")

        if not api_url or not api_key:
            return None

        # Priority 1: AssetSet (independent of build system)
        asset_set_id = os.environ.get("ASSET_SET_ID", "").strip()
        if asset_set_id:
            return cls._from_asset_set(asset_set_id, api_url, api_key)

        # Priority 2: BuildRun (CI/validation)
        build_run_id = os.environ.get("BUILD_RUN_ID", "").strip()
        if build_run_id:
            return cls._from_build_run(build_run_id, api_url, api_key)

        return None

    @classmethod
    def _from_asset_set(
        cls, asset_set_id: str, api_url: str, api_key: str,
    ) -> Optional["FirmwareSet"]:
        """Resolve from a Concord AssetSet."""
        headers = {"Authorization": f"ApiKey {api_key}"}
        try:
            resp = requests.get(
                f"{api_url}/v2/asset-sets/{asset_set_id}",
                headers=headers, timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            log.warning("Failed to fetch asset set %s: %s", asset_set_id, e)
            return None

        data = resp.json().get("data", {})
        assets = data.get("assets", [])
        if not assets:
            log.warning("Asset set %s has no files", asset_set_id)
            return None

        version = data.get("version", "")
        log.info("Firmware from asset set %s v%s (%d files)",
                 asset_set_id[:8], version, len(assets))

        return cls(assets=assets, api_url=api_url, api_key=api_key,
                   source=f"asset-set:{asset_set_id}", version=version)

    @classmethod
    def _from_build_run(
        cls, build_run_id: str, api_url: str, api_key: str,
    ) -> Optional["FirmwareSet"]:
        """Resolve from a CI BuildRun's artifacts."""
        headers = {"Authorization": f"ApiKey {api_key}"}
        try:
            resp = requests.get(
                f"{api_url}/v2/builds/runs/{build_run_id}",
                headers=headers, timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            log.warning("Failed to fetch build run %s: %s", build_run_id, e)
            return None

        data = resp.json().get("data", {})
        assets = []
        for build in data.get("builds", []):
            for artifact in build.get("artifacts", []):
                assets.append({
                    "filename": artifact.get("filename", ""),
                    "role": artifact.get("role", ""),
                    "artifactType": artifact.get("artifactType", ""),
                    "storageKey": artifact.get("storageKey", ""),
                })

        if not assets:
            log.warning("Build run %s has no artifacts", build_run_id)
            return None

        log.info("Firmware from build run %s (%d artifacts)",
                 build_run_id[:8], len(assets))

        return cls(assets=assets, api_url=api_url, api_key=api_key,
                   source=f"build-run:{build_run_id}",
                   version=data.get("name", ""))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hex(self, role: str, variant: str = "debug") -> str:
        """Get local path to a firmware hex file.

        Args:
            role: "app" or "comms"
            variant: "debug" or "release"

        Raises:
            KeyError: If no matching firmware found.
        """
        asset = self._find("plaintextHex", role, variant)
        if not asset:
            raise KeyError(
                f"No {role}/{variant} hex in {self._source}. "
                f"Available: {self._describe()}"
            )
        return self._download(asset)

    def hex_pair(self, variant: str = "debug") -> Tuple[str, str]:
        """Get (app_hex_path, comms_hex_path) for a variant.

        Raises:
            KeyError: If either file is missing.
        """
        return self.hex("app", variant), self.hex("comms", variant)

    def modem_fw(self) -> Optional[str]:
        """Get local path to modem firmware zip, or None if not in asset set.

        Modem firmware has role='modem' and is typically a .zip (DFU package).
        Unlike hex files, modem firmware is not variant-specific.
        """
        asset = self._find_by_role("modem")
        if not asset:
            return None
        return self._download(asset)

    def has_modem_fw(self) -> bool:
        """Check if modem firmware is available in the asset set."""
        return self._find_by_role("modem") is not None

    def has_variant(self, variant: str) -> bool:
        """Check if both app and comms hex exist for a variant."""
        return (self._find("plaintextHex", "app", variant) is not None
                and self._find("plaintextHex", "comms", variant) is not None)

    def available_variants(self) -> list:
        """List firmware variants present (e.g., ['debug', 'release'])."""
        variants = set()
        for a in self._assets:
            if a.get("artifactType") != "plaintextHex":
                continue
            fname = (a.get("filename") or "").lower()
            for v in ("debug", "release"):
                if v in fname:
                    variants.add(v)
        return sorted(variants)

    def cleanup(self) -> None:
        """Remove all downloaded temp files."""
        if self._tmp_dir and os.path.isdir(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find(self, artifact_type: str, role: str, variant: str) -> Optional[dict]:
        """Find an asset matching role + type + variant (filename pattern)."""
        for a in self._assets:
            if a.get("role") != role:
                continue
            if a.get("artifactType") != artifact_type:
                continue
            fname = (a.get("filename") or "").lower()
            if variant.lower() in fname:
                return a
        return None

    def _find_by_role(self, role: str) -> Optional[dict]:
        """Find the first asset with a given role (any artifact type)."""
        for a in self._assets:
            if a.get("role") == role:
                return a
        return None

    def _download(self, asset: dict) -> str:
        """Download an asset, cache locally, return file path."""
        key = asset.get("storageKey") or asset.get("filename", "")
        if key in self._cache:
            return self._cache[key]

        storage_key = asset.get("storageKey")
        if not storage_key:
            raise ValueError(f"Asset '{asset.get('filename')}' has no storageKey")

        if not self._tmp_dir:
            self._tmp_dir = tempfile.mkdtemp(prefix="concord_fw_")

        url = f"{self._api_url}/v2/storage/download?key={storage_key}"
        headers = {"Authorization": f"ApiKey {self._api_key}"}

        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()

        filename = asset.get("filename", os.path.basename(storage_key))
        path = os.path.join(self._tmp_dir, filename)
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = os.path.getsize(path) / 1024
        log.info("Downloaded: %s (%.1f KB)", filename, size_kb)
        self._cache[key] = path
        return path

    def _describe(self) -> str:
        """Format available assets for error messages."""
        items = []
        for a in self._assets:
            if a.get("artifactType") == "plaintextHex":
                items.append(f"{a.get('role', '?')}/{a.get('filename', '?')}")
        return ", ".join(items) or "(none)"

    def __repr__(self) -> str:
        return f"FirmwareSet({self._source}, v{self._version}, {len(self._assets)} files)"
