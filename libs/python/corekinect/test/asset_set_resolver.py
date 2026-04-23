"""AssetSet-based artifact resolution.

Resolves firmware assets from Concord AssetSets instead of BuildRuns.
Used when assets are uploaded manually or via external CI
rather than built by Concord's build service.

    resolver = AssetSetResolver.from_stage_config(
        stage_config_id="cfg-123",
        api_url="http://localhost:9001",
        api_key="ck_...",
    )
    hex_path = resolver.get_artifact("mfg_base", role="app", artifact_type="plaintextHex")

Compatible with StageAssets/BuildAsset — same interface as ArtifactResolver.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from corekinect.errors import ConfigError

log = logging.getLogger("asset_set_resolver")


@dataclass
class AssetInfo:
    """Metadata for a single asset file."""
    id: str
    label: str
    role: str
    processor: Optional[str]
    artifact_type: str
    filename: str
    size_bytes: int
    checksum: str
    storage_key: str


@dataclass
class AssetSetData:
    """Parsed asset set with indexed assets."""
    id: str
    version: str
    variant: str
    stage: Optional[int]
    source: str
    status: str
    assets: List[AssetInfo] = field(default_factory=list)

    def assets_by_label(self, label: str) -> List[AssetInfo]:
        return [a for a in self.assets if a.label == label]

    def labels(self) -> List[str]:
        return sorted(set(a.label for a in self.assets))


class AssetSetResolver:
    """Resolve firmware artifacts from a Concord AssetSet.

    Drop-in replacement for ArtifactResolver when assets come from
    manual upload or external CI instead of the build service.
    """

    def __init__(
        self,
        asset_set: AssetSetData,
        api_url: str,
        api_key: str,
        download_dir: Optional[str] = None,
    ):
        self._asset_set = asset_set
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._download_dir = download_dir or tempfile.mkdtemp(prefix="concord_assets_")
        self._download_cache: Dict[str, str] = {}

    @classmethod
    def from_asset_set_id(
        cls,
        asset_set_id: str,
        api_url: str,
        api_key: str,
    ) -> "AssetSetResolver":
        """Create resolver from a specific asset set ID."""
        data = cls._fetch(f"{api_url.rstrip('/')}/v2/asset-sets/{asset_set_id}", api_key)
        asset_set = cls._parse_asset_set(data)
        return cls(asset_set, api_url, api_key)

    @classmethod
    def from_stage_config(
        cls,
        stage_config_id: str,
        api_url: str,
        api_key: str,
        status: str = "COMPLETE",
    ) -> "AssetSetResolver":
        """Create resolver from the latest asset set for a stage config."""
        url = f"{api_url.rstrip('/')}/v2/asset-sets/latest?stageConfigId={stage_config_id}&status={status}"
        data = cls._fetch(url, api_key)
        asset_set = cls._parse_asset_set(data)
        return cls(asset_set, api_url, api_key)

    @staticmethod
    def _fetch(url: str, api_key: str) -> dict:
        resp = requests.get(url, headers={"Authorization": f"ApiKey {api_key}"}, timeout=30)
        if resp.status_code != 200:
            raise ConfigError(f"Asset set fetch failed ({resp.status_code}): {resp.text[:200]}")
        body = resp.json()
        return body.get("data", body)

    @staticmethod
    def _parse_asset_set(data: dict) -> AssetSetData:
        assets = [
            AssetInfo(
                id=a["id"],
                label=a["label"],
                role=a["role"],
                processor=a.get("processor"),
                artifact_type=a["artifactType"],
                filename=a["filename"],
                size_bytes=a.get("sizeBytes", 0),
                checksum=a.get("checksum", ""),
                storage_key=a.get("storageKey", ""),
            )
            for a in data.get("assets", [])
        ]
        return AssetSetData(
            id=data["id"],
            version=data.get("version", ""),
            variant=data.get("variant", ""),
            stage=data.get("stage"),
            source=data.get("source", ""),
            status=data.get("status", ""),
            assets=assets,
        )

    # ── Interface compatible with ArtifactResolver ──────────

    def get_artifact(
        self,
        label: str,
        role: str = "app",
        artifact_type: str = "plaintextHex",
    ) -> Optional[str]:
        """Download and return local path to an artifact file."""
        matching = [
            a for a in self._asset_set.assets
            if a.label == label and a.role == role and a.artifact_type == artifact_type
        ]
        if not matching:
            return None
        return self._download(matching[0])

    def get_artifacts(
        self,
        label: str,
        artifact_type: str = "encryptedCfw",
    ) -> List[str]:
        """Download and return local paths to all matching artifacts."""
        matching = [
            a for a in self._asset_set.assets
            if a.label == label and a.artifact_type == artifact_type
        ]
        return [self._download(a) for a in matching]

    def get_version(self, label: str) -> str:
        """Return the asset set version string."""
        return self._asset_set.version

    def get_manifest(self, label: str):
        """Return build manifest for a label (if manifest asset exists)."""
        manifest_asset = next(
            (a for a in self._asset_set.assets if a.label == label and a.artifact_type == "manifest"),
            None,
        )
        if not manifest_asset:
            raise ConfigError(f"No manifest for label={label}")
        path = self._download(manifest_asset)
        with open(path) as f:
            return json.load(f)

    def available_labels(self) -> List[str]:
        """Return all labels present in the asset set."""
        return self._asset_set.labels()

    def _download(self, asset: AssetInfo) -> str:
        """Download an asset file to local disk. Cached."""
        cache_key = f"{asset.label}/{asset.filename}"
        if cache_key in self._download_cache:
            return self._download_cache[cache_key]

        url = f"{self._api_url}/v2/storage/download?key={asset.storage_key}"
        resp = requests.get(
            url,
            headers={"Authorization": f"ApiKey {self._api_key}"},
            timeout=120,
            stream=True,
        )
        if resp.status_code != 200:
            raise ConfigError(f"Asset download failed ({resp.status_code}): {asset.filename}")

        label_dir = os.path.join(self._download_dir, asset.label)
        os.makedirs(label_dir, exist_ok=True)
        local_path = os.path.join(label_dir, asset.filename)

        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        self._download_cache[cache_key] = local_path
        log.debug("Downloaded %s → %s", cache_key, local_path)
        return local_path

    def cleanup(self):
        """Remove downloaded files."""
        if os.path.exists(self._download_dir):
            shutil.rmtree(self._download_dir, ignore_errors=True)
        self._download_cache.clear()
