"""Request types for product stage configuration CRUD.

Simplified: no build config fields. Build recipes are convention-driven
via StageBuildDef. Stage config only holds test + scheduling settings.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

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
    enabled: bool = True
    boardRevisionId: Optional[str] = None
    testDirectory: Optional[str] = None
    testMarker: Optional[str] = None
    testTimeout: int = 900
    priority: int = 50
    blocksMerge: bool = False
    autoProgress: bool = False
    requiresBench: bool = True
    maxDurationSec: int = 3600
    description: Optional[str] = None

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

        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            return None, "Enabled must be a boolean"

        board_revision_id = data.get("boardRevisionId")
        test_directory = (data.get("testDirectory") or "").strip() or None
        test_marker = (data.get("testMarker") or "").strip() or None
        description = (data.get("description") or "").strip() or None

        test_timeout = data.get("testTimeout", 900)
        if not isinstance(test_timeout, int) or test_timeout <= 0:
            return None, "testTimeout must be a positive integer"
        priority = data.get("priority", 50)
        if not isinstance(priority, int) or priority < 0 or priority > 200:
            return None, "priority must be an integer between 0 and 200"
        max_duration_sec = data.get("maxDurationSec", 3600)
        if not isinstance(max_duration_sec, int) or max_duration_sec <= 0:
            return None, "maxDurationSec must be a positive integer"

        blocks_merge = data.get("blocksMerge", False)
        auto_progress = data.get("autoProgress", False)
        requires_bench = data.get("requiresBench", True)

        return cls(
            stage=stage,
            name=name,
            enabled=enabled,
            boardRevisionId=board_revision_id,
            testDirectory=test_directory,
            testMarker=test_marker,
            testTimeout=test_timeout,
            priority=priority,
            blocksMerge=blocks_merge,
            autoProgress=auto_progress,
            requiresBench=requires_bench,
            maxDurationSec=max_duration_sec,
            description=description,
        ), None


@dataclass
class StageConfigUpdateRequest:
    enabled: Optional[bool] = None
    boardRevisionId: Optional[str] = None
    testDirectory: Optional[str] = None
    testMarker: Optional[str] = None
    testTimeout: Optional[int] = None
    priority: Optional[int] = None
    blocksMerge: Optional[bool] = None
    autoProgress: Optional[bool] = None
    requiresBench: Optional[bool] = None
    maxDurationSec: Optional[int] = None
    description: Optional[str] = None
    _has_board_revision_id: bool = False
    _has_test_directory: bool = False
    _has_test_marker: bool = False
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict, stage: Optional[int] = None) -> Tuple[Optional["StageConfigUpdateRequest"], Optional[str]]:
        if data is None:
            return None, "Request body must contain JSON data"

        enabled = data.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            return None, "Enabled must be a boolean"

        board_revision_id = data.get("boardRevisionId")
        has_board_revision_id = "boardRevisionId" in data

        test_directory = data.get("testDirectory")
        has_test_directory = "testDirectory" in data
        if test_directory is not None:
            test_directory = test_directory.strip() or None

        test_marker = data.get("testMarker")
        has_test_marker = "testMarker" in data
        if test_marker is not None:
            test_marker = test_marker.strip() or None

        description = data.get("description")
        has_description = "description" in data
        if description is not None:
            description = description.strip() or None

        test_timeout = data.get("testTimeout")
        if test_timeout is not None:
            if not isinstance(test_timeout, int) or test_timeout <= 0:
                return None, "testTimeout must be a positive integer"
        priority = data.get("priority")
        if priority is not None:
            if not isinstance(priority, int) or priority < 0 or priority > 200:
                return None, "priority must be an integer between 0 and 200"
        max_duration_sec = data.get("maxDurationSec")
        if max_duration_sec is not None:
            if not isinstance(max_duration_sec, int) or max_duration_sec <= 0:
                return None, "maxDurationSec must be a positive integer"

        blocks_merge = data.get("blocksMerge")
        if blocks_merge is not None and not isinstance(blocks_merge, bool):
            return None, "blocksMerge must be a boolean"
        auto_progress = data.get("autoProgress")
        if auto_progress is not None and not isinstance(auto_progress, bool):
            return None, "autoProgress must be a boolean"
        requires_bench = data.get("requiresBench")
        if requires_bench is not None and not isinstance(requires_bench, bool):
            return None, "requiresBench must be a boolean"

        has_any = (
            enabled is not None or has_board_revision_id or
            has_test_directory or has_test_marker or has_description or
            test_timeout is not None or priority is not None or
            max_duration_sec is not None or
            blocks_merge is not None or auto_progress is not None or
            requires_bench is not None
        )
        if not has_any:
            return None, "No fields to update"

        return cls(
            enabled=enabled,
            boardRevisionId=board_revision_id,
            testDirectory=test_directory,
            testMarker=test_marker,
            testTimeout=test_timeout,
            priority=priority,
            blocksMerge=blocks_merge,
            autoProgress=auto_progress,
            requiresBench=requires_bench,
            maxDurationSec=max_duration_sec,
            description=description,
            _has_board_revision_id=has_board_revision_id,
            _has_test_directory=has_test_directory,
            _has_test_marker=has_test_marker,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.enabled is not None:
            update_data["enabled"] = self.enabled
        if self._has_board_revision_id:
            update_data["boardRevisionId"] = self.boardRevisionId
        if self._has_test_directory:
            update_data["testDirectory"] = self.testDirectory
        if self._has_test_marker:
            update_data["testMarker"] = self.testMarker
        if self.testTimeout is not None:
            update_data["testTimeout"] = self.testTimeout
        if self.priority is not None:
            update_data["priority"] = self.priority
        if self.blocksMerge is not None:
            update_data["blocksMerge"] = self.blocksMerge
        if self.autoProgress is not None:
            update_data["autoProgress"] = self.autoProgress
        if self.requiresBench is not None:
            update_data["requiresBench"] = self.requiresBench
        if self.maxDurationSec is not None:
            update_data["maxDurationSec"] = self.maxDurationSec
        if self._has_description:
            update_data["description"] = self.description
        return update_data
