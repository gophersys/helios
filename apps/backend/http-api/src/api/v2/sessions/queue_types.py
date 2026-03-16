from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class QueueEntryCreateRequest:
    pipelineRunId: str
    stage: int
    priority: Optional[int] = None  # Override stage config priority
    reason: Optional[str] = None
    stageConfigId: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["QueueEntryCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        pipeline_run_id = (data.get("pipelineRunId") or "").strip()
        if not pipeline_run_id:
            return None, "pipelineRunId is required"
        stage = data.get("stage")
        if stage is None:
            return None, "stage is required"
        if not isinstance(stage, int) or stage < 1 or stage > 5:
            return None, "stage must be an integer between 1 and 5"
        priority = data.get("priority")
        if priority is not None:
            if not isinstance(priority, int) or priority < 0 or priority > 200:
                return None, "priority must be an integer between 0 and 200"
        reason = data.get("reason")
        stage_config_id = data.get("stageConfigId")
        return cls(
            pipelineRunId=pipeline_run_id,
            stage=stage,
            priority=priority,
            reason=reason.strip() if reason else None,
            stageConfigId=stage_config_id.strip() if stage_config_id else None,
        ), None


@dataclass
class QueueEntryUpdateRequest:
    priority: Optional[int] = None
    status: Optional[str] = None
    benchId: Optional[str] = None
    errorMessage: Optional[str] = None
    _has_bench_id: bool = False
    _has_error_message: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["QueueEntryUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        priority = data.get("priority")
        if priority is not None:
            if not isinstance(priority, int) or priority < 0 or priority > 200:
                return None, "priority must be an integer between 0 and 200"
        status = data.get("status")
        valid_statuses = {"QUEUED", "ASSIGNED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        if status is not None and status not in valid_statuses:
            return None, f"status must be one of: {', '.join(sorted(valid_statuses))}"
        bench_id = data.get("benchId")
        has_bench_id = "benchId" in data
        error_message = data.get("errorMessage")
        has_error_message = "errorMessage" in data
        
        if priority is None and status is None and not has_bench_id and not has_error_message:
            return None, "No fields to update"
        
        return cls(
            priority=priority,
            status=status,
            benchId=bench_id,
            errorMessage=error_message,
            _has_bench_id=has_bench_id,
            _has_error_message=has_error_message,
        ), None
