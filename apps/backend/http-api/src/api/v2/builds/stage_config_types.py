"""Request types for product stage configuration CRUD.

Thin config: revision, branch, signing key. That's it.
Test config lives in the test repo. Build recipes are convention-driven.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

VALID_STAGES = {1, 2, 3, 4, 5}
STAGE_NAMES = {
    1: "Smoke",
    2: "Silicon",
    3: "Integration",
    4: "Nightly",
    5: "FUOTA",
}


@dataclass
class StageConfigCreateRequest:
    stage: int
    name: str
    enabled: bool = False
    boardRevisionId: Optional[str] = None
    watchBranch: Optional[str] = None
    signingKeyId: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["StageConfigCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        stage = data.get("stage")
        if stage is None:
            return None, "Stage is required"
        if not isinstance(stage, int) or stage not in VALID_STAGES:
            return None, "Stage must be an integer between 1 and 5"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        expected_name = STAGE_NAMES.get(stage)
        if name != expected_name:
            return None, f"Name must be '{expected_name}' for stage {stage}"

        return cls(
            stage=stage,
            name=name,
            enabled=data.get("enabled", False),
            boardRevisionId=data.get("boardRevisionId"),
            watchBranch=(data.get("watchBranch") or "").strip() or None,
            signingKeyId=data.get("signingKeyId"),
        ), None


@dataclass
class StageConfigUpdateRequest:
    enabled: Optional[bool] = None
    boardRevisionId: Optional[str] = None
    watchBranch: Optional[str] = None
    signingKeyId: Optional[str] = None
    _has_board_revision_id: bool = False
    _has_watch_branch: bool = False
    _has_signing_key_id: bool = False

    @classmethod
    def from_json(cls, data: dict, stage: Optional[int] = None) -> Tuple[Optional["StageConfigUpdateRequest"], Optional[str]]:
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

        signing_key_id = data.get("signingKeyId")
        has_sk = "signingKeyId" in data

        has_any = enabled is not None or has_brid or has_wb or has_sk
        if not has_any:
            return None, "No fields to update"

        return cls(
            enabled=enabled,
            boardRevisionId=board_revision_id,
            watchBranch=watch_branch,
            signingKeyId=signing_key_id,
            _has_board_revision_id=has_brid,
            _has_watch_branch=has_wb,
            _has_signing_key_id=has_sk,
        ), None

    def to_update_data(self) -> dict:
        update_data = {}
        if self.enabled is not None:
            update_data["enabled"] = self.enabled
        if self._has_board_revision_id:
            update_data["boardRevisionId"] = self.boardRevisionId
        if self._has_watch_branch:
            update_data["watchBranch"] = self.watchBranch
        if self._has_signing_key_id:
            update_data["signingKeyId"] = self.signingKeyId
        return update_data
