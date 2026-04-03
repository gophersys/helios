"""Request types for asset set and asset endpoints."""

from dataclasses import dataclass
from typing import Optional, Tuple

VALID_SOURCES = {"BUILD_SERVICE", "MANUAL_UPLOAD", "EXTERNAL_CI"}
VALID_STATUSES = {"PENDING", "COMPLETE", "VALIDATED", "FAILED"}


@dataclass
class AssetSetCreateRequest:
    version: str
    variant: str = "debug"
    source: str = "MANUAL_UPLOAD"
    boardRevisionId: Optional[str] = None
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
        stage = data.get("stage")
        if stage is not None:
            if not isinstance(stage, int) or stage < 1 or stage > 5:
                return None, "Stage must be an integer between 1 and 5"
        return cls(
            version=version,
            variant=variant,
            source=source,
            boardRevisionId=data.get("boardRevisionId"),
            stage=stage,
            commitSha=(data.get("commitSha") or "").strip() or None,
            branch=(data.get("branch") or "").strip() or None,
            recipeVersionId=data.get("recipeVersionId"),
            notes=(data.get("notes") or "").strip() or None,
        ), None


@dataclass
class ExternalAssetSetCreateRequest:
    version: str
    externalBuildId: str
    variant: str = "debug"
    boardRevisionId: Optional[str] = None
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
        stage = data.get("stage")
        if stage is not None:
            if not isinstance(stage, int) or stage < 1 or stage > 5:
                return None, "Stage must be an integer between 1 and 5"
        return cls(
            version=version,
            externalBuildId=external_build_id,
            variant=(data.get("variant") or "debug").strip(),
            boardRevisionId=data.get("boardRevisionId"),
            stage=stage,
            commitSha=(data.get("commitSha") or "").strip() or None,
            branch=(data.get("branch") or "").strip() or None,
            notes=(data.get("notes") or "").strip() or None,
        ), None
