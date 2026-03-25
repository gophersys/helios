"""Request types for product stage configuration CRUD."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from database import Json

VALID_STAGES = {1, 2, 3, 4, 5}
STAGE_NAMES = {
    1: "Smoke",
    2: "Silicon",
    3: "Integration",
    4: "Nightly",
    5: "FUOTA",
}
VALID_VARIANTS = {"debug", "release", "mfg", "test"}
MFG_REPO_STAGES = {4, 5}


@dataclass
class StageConfigCreateRequest:
    stage: int
    name: str
    enabled: bool = True
    buildScript: Optional[str] = None
    buildTarget: Optional[str] = None
    fwRepoUrl: Optional[str] = None
    fwRepoBranch: Optional[str] = None
    mfgRepoUrl: Optional[str] = None
    mfgRepoBranch: Optional[str] = None
    buildVariant: Optional[str] = None
    configFlags: Optional[Dict[str, Any]] = None
    buildMatrix: Optional[List[Dict]] = None
    testDirectory: Optional[str] = None
    testMarker: Optional[str] = None
    testTimeout: int = 900
    priority: int = 50
    blocksMerge: bool = False
    requiresFuota: bool = False
    requiresBench: bool = True
    maxDurationSec: int = 3600
    description: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["StageConfigCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        # Stage (required, 1-5)
        stage = data.get("stage")
        if stage is None:
            return None, "Stage is required"
        if not isinstance(stage, int) or stage not in VALID_STAGES:
            return None, "Stage must be an integer between 1 and 5"

        # Name (required, must match stage)
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        expected_name = STAGE_NAMES.get(stage)
        if name != expected_name:
            return None, f"Name must be '{expected_name}' for stage {stage}"

        # Enabled
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            return None, "Enabled must be a boolean"

        # Optional string fields
        build_script = data.get("buildScript")
        if build_script is not None:
            build_script = build_script.strip() or None
        build_target = data.get("buildTarget")
        if build_target is not None:
            build_target = build_target.strip() or None
        fw_repo_url = data.get("fwRepoUrl")
        if fw_repo_url is not None:
            fw_repo_url = fw_repo_url.strip() or None
        fw_repo_branch = data.get("fwRepoBranch")
        if fw_repo_branch is not None:
            fw_repo_branch = fw_repo_branch.strip() or None
        mfg_repo_url = data.get("mfgRepoUrl")
        if mfg_repo_url is not None:
            mfg_repo_url = mfg_repo_url.strip() or None
            if stage not in MFG_REPO_STAGES:
                return None, "mfgRepoUrl is only valid for stages 4 and 5"
        mfg_repo_branch = data.get("mfgRepoBranch")
        if mfg_repo_branch is not None:
            mfg_repo_branch = mfg_repo_branch.strip() or None
        test_directory = data.get("testDirectory")
        if test_directory is not None:
            test_directory = test_directory.strip() or None
        test_marker = data.get("testMarker")
        if test_marker is not None:
            test_marker = test_marker.strip() or None
        description = data.get("description")
        if description is not None:
            description = description.strip() or None

        # Build variant
        build_variant = data.get("buildVariant")
        if build_variant is not None:
            build_variant = build_variant.strip().lower()
            if build_variant not in VALID_VARIANTS:
                return None, f"buildVariant must be one of: {', '.join(sorted(VALID_VARIANTS))}"

        # configFlags must be a dict if provided
        config_flags = data.get("configFlags")
        if config_flags is not None and not isinstance(config_flags, dict):
            return None, "configFlags must be a JSON object"

        # buildMatrix must be a list if provided
        build_matrix = data.get("buildMatrix")
        if build_matrix is not None and not isinstance(build_matrix, list):
            return None, "buildMatrix must be a JSON array"

        # Integer fields
        test_timeout = data.get("testTimeout", 900)
        if not isinstance(test_timeout, int) or test_timeout <= 0:
            return None, "testTimeout must be a positive integer"
        priority = data.get("priority", 50)
        if not isinstance(priority, int) or priority < 0 or priority > 200:
            return None, "priority must be an integer between 0 and 200"
        max_duration_sec = data.get("maxDurationSec", 3600)
        if not isinstance(max_duration_sec, int) or max_duration_sec <= 0:
            return None, "maxDurationSec must be a positive integer"

        # Boolean fields
        blocks_merge = data.get("blocksMerge", False)
        if not isinstance(blocks_merge, bool):
            return None, "blocksMerge must be a boolean"
        requires_fuota = data.get("requiresFuota", False)
        if not isinstance(requires_fuota, bool):
            return None, "requiresFuota must be a boolean"
        requires_bench = data.get("requiresBench", True)
        if not isinstance(requires_bench, bool):
            return None, "requiresBench must be a boolean"

        return cls(
            stage=stage,
            name=name,
            enabled=enabled,
            buildScript=build_script,
            buildTarget=build_target,
            fwRepoUrl=fw_repo_url,
            fwRepoBranch=fw_repo_branch,
            mfgRepoUrl=mfg_repo_url,
            mfgRepoBranch=mfg_repo_branch,
            buildVariant=build_variant,
            configFlags=config_flags,
            buildMatrix=build_matrix,
            testDirectory=test_directory,
            testMarker=test_marker,
            testTimeout=test_timeout,
            priority=priority,
            blocksMerge=blocks_merge,
            requiresFuota=requires_fuota,
            requiresBench=requires_bench,
            maxDurationSec=max_duration_sec,
            description=description,
        ), None


@dataclass
class StageConfigUpdateRequest:
    enabled: Optional[bool] = None
    buildScript: Optional[str] = None
    buildTarget: Optional[str] = None
    fwRepoUrl: Optional[str] = None
    fwRepoBranch: Optional[str] = None
    mfgRepoUrl: Optional[str] = None
    mfgRepoBranch: Optional[str] = None
    buildVariant: Optional[str] = None
    configFlags: Optional[Dict[str, Any]] = None
    buildMatrix: Optional[List[Dict]] = None
    testDirectory: Optional[str] = None
    testMarker: Optional[str] = None
    testTimeout: Optional[int] = None
    priority: Optional[int] = None
    blocksMerge: Optional[bool] = None
    requiresFuota: Optional[bool] = None
    requiresBench: Optional[bool] = None
    maxDurationSec: Optional[int] = None
    description: Optional[str] = None
    # Track explicitly-set-to-null vs omitted
    _has_build_script: bool = False
    _has_build_target: bool = False
    _has_fw_repo_url: bool = False
    _has_fw_repo_branch: bool = False
    _has_mfg_repo_url: bool = False
    _has_mfg_repo_branch: bool = False
    _has_build_variant: bool = False
    _has_config_flags: bool = False
    _has_build_matrix: bool = False
    _has_test_directory: bool = False
    _has_test_marker: bool = False
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict, stage: Optional[int] = None) -> Tuple[Optional["StageConfigUpdateRequest"], Optional[str]]:
        if data is None:
            return None, "Request body must contain JSON data"

        # Enabled
        enabled = data.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            return None, "Enabled must be a boolean"

        # Optional string fields with null tracking
        build_script = data.get("buildScript")
        has_build_script = "buildScript" in data
        if build_script is not None:
            build_script = build_script.strip() or None

        build_target = data.get("buildTarget")
        has_build_target = "buildTarget" in data
        if build_target is not None:
            build_target = build_target.strip() or None

        fw_repo_url = data.get("fwRepoUrl")
        has_fw_repo_url = "fwRepoUrl" in data
        if fw_repo_url is not None:
            fw_repo_url = fw_repo_url.strip() or None

        fw_repo_branch = data.get("fwRepoBranch")
        has_fw_repo_branch = "fwRepoBranch" in data
        if fw_repo_branch is not None:
            fw_repo_branch = fw_repo_branch.strip() or None

        mfg_repo_url = data.get("mfgRepoUrl")
        has_mfg_repo_url = "mfgRepoUrl" in data
        if mfg_repo_url is not None:
            mfg_repo_url = mfg_repo_url.strip() or None
            if stage is not None and stage not in MFG_REPO_STAGES:
                return None, "mfgRepoUrl is only valid for stages 4 and 5"

        mfg_repo_branch = data.get("mfgRepoBranch")
        has_mfg_repo_branch = "mfgRepoBranch" in data
        if mfg_repo_branch is not None:
            mfg_repo_branch = mfg_repo_branch.strip() or None

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

        # Build variant
        build_variant = data.get("buildVariant")
        has_build_variant = "buildVariant" in data
        if build_variant is not None:
            build_variant = build_variant.strip().lower()
            if build_variant not in VALID_VARIANTS:
                return None, f"buildVariant must be one of: {', '.join(sorted(VALID_VARIANTS))}"

        # configFlags
        config_flags = data.get("configFlags")
        has_config_flags = "configFlags" in data
        if has_config_flags and config_flags is not None and not isinstance(config_flags, dict):
            return None, "configFlags must be a JSON object"

        # buildMatrix
        build_matrix = data.get("buildMatrix")
        has_build_matrix = "buildMatrix" in data
        if has_build_matrix and build_matrix is not None and not isinstance(build_matrix, list):
            return None, "buildMatrix must be a JSON array"

        # Integer fields
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

        # Boolean fields
        blocks_merge = data.get("blocksMerge")
        if blocks_merge is not None and not isinstance(blocks_merge, bool):
            return None, "blocksMerge must be a boolean"
        requires_fuota = data.get("requiresFuota")
        if requires_fuota is not None and not isinstance(requires_fuota, bool):
            return None, "requiresFuota must be a boolean"
        requires_bench = data.get("requiresBench")
        if requires_bench is not None and not isinstance(requires_bench, bool):
            return None, "requiresBench must be a boolean"

        # Check if any field was provided
        has_any_field = (
            enabled is not None or
            has_build_script or has_build_target or
            has_fw_repo_url or has_fw_repo_branch or
            has_mfg_repo_url or has_mfg_repo_branch or
            has_build_variant or has_config_flags or has_build_matrix or
            has_test_directory or has_test_marker or has_description or
            test_timeout is not None or priority is not None or
            max_duration_sec is not None or
            blocks_merge is not None or requires_fuota is not None or
            requires_bench is not None
        )
        if not has_any_field:
            return None, "No fields to update"

        return cls(
            enabled=enabled,
            buildScript=build_script,
            buildTarget=build_target,
            fwRepoUrl=fw_repo_url,
            fwRepoBranch=fw_repo_branch,
            mfgRepoUrl=mfg_repo_url,
            mfgRepoBranch=mfg_repo_branch,
            buildVariant=build_variant,
            configFlags=config_flags,
            buildMatrix=build_matrix,
            testDirectory=test_directory,
            testMarker=test_marker,
            testTimeout=test_timeout,
            priority=priority,
            blocksMerge=blocks_merge,
            requiresFuota=requires_fuota,
            requiresBench=requires_bench,
            maxDurationSec=max_duration_sec,
            description=description,
            _has_build_script=has_build_script,
            _has_build_target=has_build_target,
            _has_fw_repo_url=has_fw_repo_url,
            _has_fw_repo_branch=has_fw_repo_branch,
            _has_mfg_repo_url=has_mfg_repo_url,
            _has_mfg_repo_branch=has_mfg_repo_branch,
            _has_build_variant=has_build_variant,
            _has_config_flags=has_config_flags,
            _has_build_matrix=has_build_matrix,
            _has_test_directory=has_test_directory,
            _has_test_marker=has_test_marker,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.enabled is not None:
            update_data["enabled"] = self.enabled
        if self._has_build_script:
            update_data["buildScript"] = self.buildScript
        if self._has_build_target:
            update_data["buildTarget"] = self.buildTarget
        if self._has_fw_repo_url:
            update_data["fwRepoUrl"] = self.fwRepoUrl
        if self._has_fw_repo_branch:
            update_data["fwRepoBranch"] = self.fwRepoBranch
        if self._has_mfg_repo_url:
            update_data["mfgRepoUrl"] = self.mfgRepoUrl
        if self._has_mfg_repo_branch:
            update_data["mfgRepoBranch"] = self.mfgRepoBranch
        if self._has_build_variant:
            update_data["buildVariant"] = self.buildVariant
        if self._has_config_flags:
            update_data["configFlags"] = Json(self.configFlags) if self.configFlags else None
        if self._has_build_matrix:
            update_data["buildMatrix"] = Json(self.buildMatrix) if self.buildMatrix else None
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
        if self.requiresFuota is not None:
            update_data["requiresFuota"] = self.requiresFuota
        if self.requiresBench is not None:
            update_data["requiresBench"] = self.requiresBench
        if self.maxDurationSec is not None:
            update_data["maxDurationSec"] = self.maxDurationSec
        if self._has_description:
            update_data["description"] = self.description
        return update_data
