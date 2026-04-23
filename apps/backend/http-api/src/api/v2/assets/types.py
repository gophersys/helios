"""Request types for asset set and asset endpoints."""

from dataclasses import dataclass
from typing import Optional, Tuple

VALID_SOURCES = {"BUILD_SERVICE", "MANUAL_UPLOAD", "EXTERNAL_CI"}
VALID_STATUSES = {"PENDING", "COMPLETE", "FAILED"}


@dataclass
class AssetSetCreateRequest:
    """Request body for creating a new asset set."""

    version: str
    variant: str = "debug"
    source: str = "MANUAL_UPLOAD"
    boardRevisionId: Optional[str] = None
    stageConfigId: Optional[str] = None
    stage: Optional[int] = None
    commitSha: Optional[str] = None
    branch: Optional[str] = None
    recipeVersionId: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["AssetSetCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        if not version:
            return None, "Version is required"
        variant = (data.get("variant") or "debug").strip()
        source = (data.get("source") or "MANUAL_UPLOAD").strip().upper()
        if source not in VALID_SOURCES:
            return None, f"Invalid source: {source}. Valid: {sorted(VALID_SOURCES)}"
        return cls(
            version=version,
            variant=variant,
            source=source,
            boardRevisionId=data.get("boardRevisionId"),
            stageConfigId=data.get("stageConfigId"),
            stage=data.get("stage"),
            commitSha=(data.get("commitSha") or "").strip() or None,
            branch=(data.get("branch") or "").strip() or None,
            recipeVersionId=data.get("recipeVersionId"),
            notes=(data.get("notes") or "").strip() or None,
        ), None


@dataclass
class ExternalAssetSetCreateRequest:
    """Request body for creating an asset set from an external CI build."""

    version: str
    externalBuildId: str
    variant: str = "debug"
    boardRevisionId: Optional[str] = None
    stageConfigId: Optional[str] = None
    stage: Optional[int] = None
    commitSha: Optional[str] = None
    branch: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ExternalAssetSetCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        if not version:
            return None, "Version is required"
        external_build_id = (data.get("externalBuildId") or "").strip()
        if not external_build_id:
            return None, "externalBuildId is required"
        return cls(
            version=version,
            externalBuildId=external_build_id,
            variant=(data.get("variant") or "debug").strip(),
            boardRevisionId=data.get("boardRevisionId"),
            stageConfigId=data.get("stageConfigId"),
            stage=data.get("stage"),
            commitSha=(data.get("commitSha") or "").strip() or None,
            branch=(data.get("branch") or "").strip() or None,
            notes=(data.get("notes") or "").strip() or None,
        ), None
