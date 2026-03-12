from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RunCreateRequest:
    """Create a new validation run (Session + Device + optional test filter)."""
    name: str
    product_id: str
    node_id: str
    serial_number: str
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
    """Individual test finished — create TestResult, update TestExecution."""
    test_name: str
    passed: bool
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

        return cls(
            test_name=test_name,
            passed=passed,
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
    stage: str = "gate"  # Test stage: gate, nightly, integration, smoke
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

        stage = (data.get("stage") or "gate").strip().lower()
        if stage not in ("gate", "nightly", "integration", "smoke", "fuota"):
            return None, "stage must be one of: gate, nightly, integration, smoke, fuota"

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
