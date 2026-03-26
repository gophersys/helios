from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

VALID_SESSION_TYPES = ("VALIDATION", "MANUFACTURING")


@dataclass
class SessionRerunRequest:
    """Clone a session with optional different pipeline."""
    pipeline_run_id: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SessionRerunRequest"], Optional[str]]:
        if not data:
            # Allow empty body — rerun with same pipeline
            return cls(), None

        pipeline_run_id = data.get("pipelineRunId")
        if pipeline_run_id is not None:
            pipeline_run_id = str(pipeline_run_id).strip() or None

        return cls(pipeline_run_id=pipeline_run_id), None


@dataclass
class RunCreateRequest:
    """Create a new validation run (Session + Device + optional test filter)."""
    name: str
    product_id: str
    node_id: str
    serial_number: str
    type: str = "VALIDATION"
    firmware_variant: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    test_filter: Optional[List[str]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["RunCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"

        product_id = (data.get("productId") or "").strip()
        if not product_id:
            return None, "productId is required"

        node_id = (data.get("nodeId") or "").strip()
        if not node_id:
            return None, "nodeId is required"

        serial_number = (data.get("serialNumber") or "").strip()
        if not serial_number:
            return None, "serialNumber is required"

        session_type = (data.get("type") or "VALIDATION").strip().upper()
        if session_type not in VALID_SESSION_TYPES:
            return None, f"type must be one of: {', '.join(VALID_SESSION_TYPES)}"

        firmware_variant = data.get("firmwareVariant")
        if firmware_variant is not None:
            firmware_variant = firmware_variant.strip()

        config = data.get("config")
        if config is not None and not isinstance(config, dict):
            return None, "config must be an object"

        notes = data.get("notes")
        if notes is not None:
            notes = notes.strip() or None

        test_filter = data.get("testFilter")
        if test_filter is not None:
            if not isinstance(test_filter, list):
                return None, "testFilter must be an array of test names"
            test_filter = [t.strip() for t in test_filter if isinstance(t, str) and t.strip()]

        return cls(
            name=name,
            product_id=product_id,
            node_id=node_id,
            serial_number=serial_number,
            type=session_type,
            firmware_variant=firmware_variant,
            config=config,
            notes=notes,
            test_filter=test_filter,
        ), None


@dataclass
class ReportStartRequest:
    """pytest session started — set Session ACTIVE, record start time."""

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportStartRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        return cls(), None


@dataclass
class ReportTestStartRequest:
    """Individual test started — create/update TestExecution to RUNNING."""
    test_name: str
    module: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportTestStartRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        test_name = (data.get("testName") or "").strip()
        if not test_name:
            return None, "testName is required"

        module = data.get("module")
        if module is not None:
            module = module.strip() or None

        return cls(test_name=test_name, module=module), None


@dataclass
class ReportTestResultRequest:
    """Individual test finished — create TestStep, update TestExecution."""
    test_name: str
    passed: bool
    module: Optional[str] = None
    duration_s: Optional[float] = None
    error_message: Optional[str] = None
    measurements: Optional[Dict[str, Any]] = None
    skipped: bool = False
    log_output: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportTestResultRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        test_name = (data.get("testName") or "").strip()
        if not test_name:
            return None, "testName is required"

        passed = data.get("passed")
        if passed is None:
            return None, "passed is required"
        if not isinstance(passed, bool):
            return None, "passed must be a boolean"

        duration_s = data.get("durationS")
        if duration_s is not None:
            try:
                duration_s = float(duration_s)
            except (TypeError, ValueError):
                return None, "durationS must be a number"

        error_message = data.get("errorMessage")
        if error_message is not None:
            error_message = str(error_message).strip() or None

        measurements = data.get("measurements")
        if measurements is not None and not isinstance(measurements, dict):
            return None, "measurements must be an object"

        skipped = data.get("skipped", False)
        if not isinstance(skipped, bool):
            skipped = False

        log_output = data.get("logOutput")
        if log_output is not None:
            log_output = str(log_output)[:10000] or None  # Cap at 10KB

        module = data.get("module")
        if module is not None:
            module = str(module).strip() or None

        return cls(
            test_name=test_name,
            passed=passed,
            module=module,
            duration_s=duration_s,
            error_message=error_message,
            measurements=measurements,
            skipped=skipped,
            log_output=log_output,
        ), None


@dataclass
class ReportFinishRequest:
    """pytest session finished — update Session counts, set COMPLETED."""
    total: int
    passed: int
    failed: int
    errors: int = 0
    duration_s: Optional[float] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportFinishRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        total = data.get("total")
        if total is None:
            return None, "total is required"
        if not isinstance(total, int) or total < 0:
            return None, "total must be a non-negative integer"

        passed = data.get("passed")
        if passed is None:
            return None, "passed is required"
        if not isinstance(passed, int) or passed < 0:
            return None, "passed must be a non-negative integer"

        failed = data.get("failed")
        if failed is None:
            return None, "failed is required"
        if not isinstance(failed, int) or failed < 0:
            return None, "failed must be a non-negative integer"

        errors = data.get("errors", 0)
        if not isinstance(errors, int) or errors < 0:
            return None, "errors must be a non-negative integer"

        duration_s = data.get("durationS")
        if duration_s is not None:
            try:
                duration_s = float(duration_s)
            except (TypeError, ValueError):
                return None, "durationS must be a number"

        return cls(
            total=total,
            passed=passed,
            failed=failed,
            errors=errors,
            duration_s=duration_s,
        ), None


@dataclass
class RunTriggerRequest:
    """Trigger a K8s validation job for an existing run."""
    firmware_version: str
    firmware_path: Optional[str] = None  # Legacy: MinIO path (deprecated)
    pipeline_id: Optional[str] = None  # Stage 4: CI pipeline ID (preferred)
    stage: str = "fuota"  # Test stage: smoke, silicon, integration, nightly, fuota
    config: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["RunTriggerRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        firmware_version = (data.get("firmwareVersion") or "").strip()
        if not firmware_version:
            return None, "firmwareVersion is required"

        firmware_path = data.get("firmwarePath")
        if firmware_path is not None:
            firmware_path = firmware_path.strip() or None

        pipeline_id = data.get("pipelineId")
        if pipeline_id is not None:
            pipeline_id = pipeline_id.strip() or None

        stage = (data.get("stage") or "fuota").strip().lower()
        if stage not in ("smoke", "silicon", "integration", "nightly", "fuota"):
            return None, "stage must be one of: smoke, silicon, integration, nightly, fuota"

        config = data.get("config")
        if config is not None and not isinstance(config, dict):
            return None, "config must be an object"

        return cls(
            firmware_version=firmware_version,
            firmware_path=firmware_path,
            pipeline_id=pipeline_id,
            stage=stage,
            config=config,
        ), None


@dataclass
class ReportLogChunkRequest:
    """Log chunk from pytest reporter — streamed during test execution.

    Can be sent with or without testName:
    - With testName: logs are associated with specific test (for per-test log display)
    - Without testName: logs are associated with run-level output (pytest framework, setup, etc.)
    """
    file: str
    offset: int
    data: str  # base64 encoded
    test_name: Optional[str] = None  # Which test this log belongs to (if any)
    timestamp: Optional[int] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportLogChunkRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        file = (data.get("file") or "").strip()
        if not file:
            return None, "file is required"

        # Validate file path to prevent directory traversal
        if ".." in file or file.startswith("/"):
            return None, "Invalid file path"

        offset = data.get("offset")
        if offset is None:
            return None, "offset is required"
        if not isinstance(offset, int) or offset < 0:
            return None, "offset must be a non-negative integer"

        chunk_data = data.get("data")
        if not chunk_data:
            return None, "data is required"
        if not isinstance(chunk_data, str):
            return None, "data must be a base64-encoded string"

        test_name = data.get("testName")
        if test_name is not None:
            test_name = str(test_name).strip() or None

        timestamp = data.get("timestamp")
        if timestamp is not None:
            if not isinstance(timestamp, (int, float)):
                return None, "timestamp must be a number"
            timestamp = int(timestamp)

        return cls(
            file=file,
            offset=offset,
            data=chunk_data,
            test_name=test_name,
            timestamp=timestamp,
        ), None


@dataclass
class StepStartRequest:
    """Sub-step started within a test execution."""
    test_name: str
    step_name: str
    step_index: int
    device_serial: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["StepStartRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        test_name = (data.get("testName") or "").strip()
        if not test_name:
            return None, "testName is required"

        step_name = (data.get("stepName") or "").strip()
        if not step_name:
            return None, "stepName is required"

        step_index = data.get("stepIndex")
        if step_index is None:
            return None, "stepIndex is required"
        if not isinstance(step_index, int) or step_index < 0:
            return None, "stepIndex must be a non-negative integer"

        device_serial = data.get("deviceSerial")
        if device_serial is not None:
            device_serial = str(device_serial).strip() or None

        return cls(
            test_name=test_name,
            step_name=step_name,
            step_index=step_index,
            device_serial=device_serial,
        ), None


@dataclass
class StepResultRequest:
    """Sub-step finished within a test execution."""
    test_name: str
    step_index: int
    passed: bool
    device_serial: Optional[str] = None
    error_message: Optional[str] = None
    measurements: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["StepResultRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        test_name = (data.get("testName") or "").strip()
        if not test_name:
            return None, "testName is required"

        step_index = data.get("stepIndex")
        if step_index is None:
            return None, "stepIndex is required"
        if not isinstance(step_index, int) or step_index < 0:
            return None, "stepIndex must be a non-negative integer"

        passed = data.get("passed")
        if passed is None:
            return None, "passed is required"
        if not isinstance(passed, bool):
            return None, "passed must be a boolean"

        device_serial = data.get("deviceSerial")
        if device_serial is not None:
            device_serial = str(device_serial).strip() or None

        error_message = data.get("errorMessage")
        if error_message is not None:
            error_message = str(error_message).strip() or None

        measurements = data.get("measurements")
        if measurements is not None and not isinstance(measurements, dict):
            return None, "measurements must be an object"

        duration_ms = data.get("durationMs")
        if duration_ms is not None:
            try:
                duration_ms = int(duration_ms)
            except (TypeError, ValueError):
                return None, "durationMs must be an integer"

        return cls(
            test_name=test_name,
            step_index=step_index,
            passed=passed,
            device_serial=device_serial,
            error_message=error_message,
            measurements=measurements,
            duration_ms=duration_ms,
        ), None


# ── Manual run types ─────────────────────────────────────────────────────


@dataclass
class ValidationTestsRunRequest:
    """Request structure for running a validation test"""

    product: str
    zip_file_path: str
    additional_fields: Dict[str, str]

    @classmethod
    def from_form_data(cls, form_data: dict, zip_file_path: str) -> Tuple[Optional["ValidationTestsRunRequest"], Optional[str]]:
        """Parse form data into request object with validation"""
        if not form_data:
            return None, "Request must contain form data"

        product = form_data.get("product")
        if not product:
            return None, "Field 'product' is required"

        # Extract additional fields (excluding name, product, and file)
        additional_fields = {}
        for key, value in form_data.items():
            if key not in ["product", "file"] and value:
                additional_fields[key] = value

        return cls(product=product, zip_file_path=zip_file_path, additional_fields=additional_fields), None


# ── Queue types ──────────────────────────────────────────────────────────


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
