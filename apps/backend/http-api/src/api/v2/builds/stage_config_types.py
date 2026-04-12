"""Request types for product stage configuration CRUD.

Thin config: revision, branch, signing key. That's it.
Test config lives in the test repo. Build recipes are convention-driven.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

VALID_TYPES = {"VALIDATION", "MANUFACTURING"}
VALID_VALIDATION_STAGES = {1, 2, 3, 4, 5}
VALID_MANUFACTURING_STAGES = {1}
VALID_STAGES = VALID_VALIDATION_STAGES | VALID_MANUFACTURING_STAGES

STAGE_NAMES = {
    "VALIDATION": {1: "Smoke", 2: "Driver", 3: "Integration", 4: "Regression", 5: "FUOTA"},
    "MANUFACTURING": {1: "Manufacturing"},
}


VALID_TRIGGER_TYPES = {"pr_push", "pr_merge", "auto", "schedule", "manual"}
VALID_ASSET_SOURCES = {"BUILD_SERVICE", "MANUAL_UPLOAD", "EXTERNAL_CI"}


@dataclass
class StageConfigCreateRequest:
    """Request body for creating a product stage configuration."""

    type: str  # VALIDATION or MANUFACTURING
    stage: int
    name: str
    enabled: bool = False
    boardRevisionId: Optional[str] = None
    watchBranch: Optional[str] = None
    triggerTypes: Optional[list] = None
    signingKeyId: Optional[str] = None
    assetSource: str = "BUILD_SERVICE"

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["StageConfigCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        stage_type = (data.get("type") or "VALIDATION").strip().upper()
        if stage_type not in VALID_TYPES:
            return None, f"type must be one of: {', '.join(sorted(VALID_TYPES))}"

        valid_stages = VALID_MANUFACTURING_STAGES if stage_type == "MANUFACTURING" else VALID_VALIDATION_STAGES
        stage = data.get("stage")
        if stage is None:
            return None, "stage is required"
        if not isinstance(stage, int) or stage not in valid_stages:
            return None, f"stage must be one of: {sorted(valid_stages)} for type {stage_type}"

        name = (data.get("name") or "").strip()
        if not name:
            # Auto-name from stage type + number
            type_names = STAGE_NAMES.get(stage_type, {})
            name = type_names.get(stage, f"Stage {stage}")

        trigger_types = data.get("triggerTypes", ["manual"])
        if isinstance(trigger_types, str):
            trigger_types = [trigger_types]
        if not isinstance(trigger_types, list):
            return None, "triggerTypes must be an array"
        invalid = [t for t in trigger_types if t not in VALID_TRIGGER_TYPES]
        if invalid:
            return None, f"Invalid trigger types: {invalid}. Valid: {sorted(VALID_TRIGGER_TYPES)}"
        if not trigger_types:
            trigger_types = ["manual"]

        asset_source = (data.get("assetSource") or "BUILD_SERVICE").strip().upper()
        if asset_source not in VALID_ASSET_SOURCES:
            return None, f"assetSource must be one of: {', '.join(sorted(VALID_ASSET_SOURCES))}"

        return cls(
            type=stage_type,
            stage=stage,
            name=name,
            enabled=data.get("enabled", False),
            boardRevisionId=data.get("boardRevisionId"),
            watchBranch=(data.get("watchBranch") or "").strip() or None,
            triggerTypes=trigger_types,
            signingKeyId=data.get("signingKeyId"),
            assetSource=asset_source,
        ), None


@dataclass
class StageConfigUpdateRequest:
    """Request body for updating a product stage configuration."""

    enabled: Optional[bool] = None
    boardRevisionId: Optional[str] = None
    watchBranch: Optional[str] = None
    triggerTypes: Optional[list] = None
    signingKeyId: Optional[str] = None
    assetSource: Optional[str] = None
    _has_board_revision_id: bool = False
    _has_watch_branch: bool = False
    _has_trigger_type: bool = False
    _has_signing_key_id: bool = False
    _has_asset_source: bool = False

    @classmethod
    def from_json(cls, data: dict, stage: Optional[int] = None) -> Tuple[Optional["StageConfigUpdateRequest"], Optional[str]]:
        """Parse and validate JSON into a StageConfigUpdateRequest."""
        if data is None:
            return None, "Request body must contain JSON data"

        enabled = data.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            return None, "Enabled must be a boolean"

        board_revision_id = data.get("boardRevisionId")
        has_brid = "boardRevisionId" in data

        watch_branch = data.get("watchBranch")
        has_wb = "watchBranch" in data
        if watch_branch is not None:
            watch_branch = watch_branch.strip() or None

        trigger_types = data.get("triggerTypes")
        has_tt = "triggerTypes" in data
        if trigger_types is not None:
            if isinstance(trigger_types, str):
                trigger_types = [trigger_types]
            if not isinstance(trigger_types, list):
                return None, "triggerTypes must be an array"
            invalid = [t for t in trigger_types if t not in VALID_TRIGGER_TYPES]
            if invalid:
                return None, f"Invalid trigger types: {invalid}"

        signing_key_id = data.get("signingKeyId")
        has_sk = "signingKeyId" in data

        asset_source = data.get("assetSource")
        has_as = "assetSource" in data
        if asset_source is not None:
            asset_source = asset_source.strip().upper()
            if asset_source not in VALID_ASSET_SOURCES:
                return None, f"assetSource must be one of: {', '.join(sorted(VALID_ASSET_SOURCES))}"

        has_any = enabled is not None or has_brid or has_wb or has_tt or has_sk or has_as
        if not has_any:
            return None, "No fields to update"

        return cls(
            enabled=enabled,
            boardRevisionId=board_revision_id,
            watchBranch=watch_branch,
            triggerTypes=trigger_types,
            signingKeyId=signing_key_id,
            assetSource=asset_source,
            _has_board_revision_id=has_brid,
            _has_watch_branch=has_wb,
            _has_trigger_type=has_tt,
            _has_signing_key_id=has_sk,
            _has_asset_source=has_as,
        ), None

    def to_update_data(self) -> dict:
        """Build a dict of changed fields for the Prisma update call."""
        update_data: Dict[str, Any] = {}
        if self.enabled is not None:
            update_data["enabled"] = self.enabled
        if self._has_board_revision_id:
            update_data["boardRevisionId"] = self.boardRevisionId
        if self._has_watch_branch:
            update_data["watchBranch"] = self.watchBranch
        if self._has_trigger_type:
            update_data["triggerTypes"] = self.triggerTypes
        if self._has_signing_key_id:
            update_data["signingKeyId"] = self.signingKeyId
        if self._has_asset_source:
            update_data["assetSource"] = self.assetSource
        return update_data
