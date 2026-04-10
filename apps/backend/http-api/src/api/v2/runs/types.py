from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

VALID_RUN_TYPES = ("VALIDATION", "MANUFACTURING")
VALID_RUN_STATUSES = ("PENDING", "ACTIVE", "COMPLETED", "FAILED", "CANCELLED")


@dataclass
class CreateRunRequest:
    """Create a new test run (TestRun + RunTarget)."""
    type: str
    product_id: str
    fixture_id: Optional[str] = None
    serial_number: Optional[str] = None
    notes: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["CreateRunRequest"], Optional[str]]:
        """Parse and validate JSON into a CreateRunRequest."""
        if not data:
            return None, "Request body must contain JSON data"

        run_type = (data.get("type") or "").strip().upper()
        if not run_type:
            return None, "type is required"
        if run_type not in VALID_RUN_TYPES:
            return None, f"type must be one of: {', '.join(VALID_RUN_TYPES)}"

        product_id = (data.get("productId") or "").strip()
        if not product_id:
            return None, "productId is required"

        fixture_id = data.get("fixtureId")
        if fixture_id is not None:
            fixture_id = str(fixture_id).strip() or None

        serial_number = data.get("serialNumber")
        if serial_number is not None:
            serial_number = str(serial_number).strip() or None

        config = data.get("config")
        if config is not None and not isinstance(config, dict):
            return None, "config must be an object"

        notes = data.get("notes")
        if notes is not None:
            notes = str(notes).strip() or None

        return cls(
            type=run_type,
            product_id=product_id,
            fixture_id=fixture_id,
            serial_number=serial_number,
            notes=notes,
            config=config,
        ), None


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_run(run: Any, include_targets: bool = False) -> dict:
    """Serialize a TestRun DB record to an API response dict."""
    data = {
        "id": run.id,
        "type": run.type,
        "name": run.name,
        "productId": run.productId,
        "fixtureId": run.fixtureId,
        "testPackageId": run.testPackageId,
        "buildRunId": run.buildRunId,
        "manufacturingSessionId": run.manufacturingSessionId,
        "panelIdentifier": run.panelIdentifier,
        "assetSetId": run.assetSetId,
        "status": run.status,
        "operatorId": run.operatorId,
        "targetCount": run.targetCount,
        "completedCount": run.completedCount,
        "passedCount": run.passedCount,
        "failedCount": run.failedCount,
        "config": run.config,
        "notes": run.notes,
        "errorMessage": run.errorMessage,
        "startedAt": run.startedAt.isoformat() if run.startedAt else None,
        "completedAt": run.completedAt.isoformat() if run.completedAt else None,
        "durationMs": run.durationMs,
        "createdAt": run.createdAt.isoformat(),
        "updatedAt": run.updatedAt.isoformat(),
    }

    # Optional relations
    if hasattr(run, "product") and run.product is not None:
        data["product"] = {"id": run.product.id, "name": run.product.name}
    if hasattr(run, "operator") and run.operator is not None:
        data["operator"] = {
            "id": run.operator.id,
            "name": run.operator.name,
            "email": run.operator.email,
        }
    if hasattr(run, "fixture") and run.fixture is not None:
        data["fixture"] = {"id": run.fixture.id, "name": run.fixture.name}
    if hasattr(run, "testPackage") and run.testPackage is not None:
        data["testPackage"] = {
            "id": run.testPackage.id,
            "version": run.testPackage.version,
            "type": run.testPackage.type,
            "status": run.testPackage.status,
        }
    if hasattr(run, "buildRun") and run.buildRun is not None:
        data["buildRun"] = {
            "id": run.buildRun.id,
            "name": run.buildRun.name,
            "status": run.buildRun.status,
            "commitSha": run.buildRun.commitSha,
            "branch": run.buildRun.branch,
        }
    if hasattr(run, "assetSet") and run.assetSet is not None:
        data["assetSet"] = {
            "id": run.assetSet.id,
            "version": getattr(run.assetSet, "version", None),
            "status": run.assetSet.status,
        }

    if include_targets and hasattr(run, "targets") and run.targets is not None:
        data["targets"] = [_serialize_target(t) for t in run.targets]

    return data


def _serialize_target(target: Any) -> dict:
    """Serialize a RunTarget DB record to an API response dict."""
    data = {
        "id": target.id,
        "runId": target.runId,
        "slotIndex": target.slotIndex,
        "slotId": target.slotId,
        "serialNumber": target.serialNumber,
        "deviceId": target.deviceId,
        "status": target.status,
        "metadata": target.metadata,
        "errorMessage": target.errorMessage,
        "startedAt": target.startedAt.isoformat() if target.startedAt else None,
        "completedAt": target.completedAt.isoformat() if target.completedAt else None,
        "durationMs": target.durationMs,
        "createdAt": target.createdAt.isoformat(),
    }

    if hasattr(target, "executions") and target.executions is not None:
        data["executions"] = [_serialize_execution(ex) for ex in target.executions]

    return data


def _serialize_execution(ex: Any) -> dict:
    """Serialize a TestExecution DB record to an API response dict."""
    data = {
        "id": ex.id,
        "targetId": ex.targetId,
        "executionIndex": ex.executionIndex,
        "name": ex.name,
        "module": ex.module,
        "status": ex.status,
        "durationMs": ex.durationMs,
        "errorMessage": ex.errorMessage,
        "measurements": ex.measurements,
        "logOutput": ex.logOutput,
        "logStorageKey": ex.logStorageKey,
        "startedAt": ex.startedAt.isoformat() if ex.startedAt else None,
        "completedAt": ex.completedAt.isoformat() if ex.completedAt else None,
        "createdAt": ex.createdAt.isoformat(),
    }

    if hasattr(ex, "steps") and ex.steps is not None:
        data["steps"] = [_serialize_step(s) for s in ex.steps]

    return data


def _serialize_step(step: Any) -> dict:
    """Serialize a TestStep DB record to an API response dict."""
    return {
        "id": step.id,
        "executionId": step.executionId,
        "stepIndex": step.stepIndex,
        "name": step.name,
        "status": step.status,
        "passed": step.passed,
        "durationMs": step.durationMs,
        "errorMessage": step.errorMessage,
        "measurements": step.measurements,
        "logOutput": step.logOutput,
        "logStorageKey": step.logStorageKey,
        "startedAt": step.startedAt.isoformat() if step.startedAt else None,
        "completedAt": step.completedAt.isoformat() if step.completedAt else None,
        "createdAt": step.createdAt.isoformat(),
    }


# ---------------------------------------------------------------------------
# Request types (migrated from sessions/types.py)
# ---------------------------------------------------------------------------


@dataclass
class RunTriggerRequest:
    """Trigger a K8s validation job for an existing run."""
    firmware_version: str
    firmware_path: Optional[str] = None
    pipeline_id: Optional[str] = None
    stage: str = "fuota"
    config: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["RunTriggerRequest"], Optional[str]]:
        """Parse and validate JSON into a RunTriggerRequest."""
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
        if stage not in ("smoke", "driver", "integration", "regression", "fuota"):
            return None, "stage must be one of: smoke, driver, integration, regression, fuota"

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
    """Log chunk from pytest reporter -- streamed during test execution.

    Can be sent with or without testName:
    - With testName: logs are associated with specific test
    - Without testName: logs are run-level output (pytest framework, setup, etc.)
    """
    file: str
    offset: int
    data: str  # base64 encoded
    test_name: Optional[str] = None
    timestamp: Optional[int] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportLogChunkRequest"], Optional[str]]:
        """Parse and validate JSON into a ReportLogChunkRequest."""
        if not data:
            return None, "Request body must contain JSON data"

        file = (data.get("file") or "").strip()
        if not file:
            return None, "file is required"

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
class ValidationTestsRunRequest:
    """Request structure for running a validation test."""

    product: str
    zip_file_path: str
    additional_fields: Dict[str, str]

    @classmethod
    def from_form_data(cls, form_data: dict, zip_file_path: str) -> Tuple[Optional["ValidationTestsRunRequest"], Optional[str]]:
        """Parse form data into request object with validation."""
        if not form_data:
            return None, "Request must contain form data"

        product = form_data.get("product")
        if not product:
            return None, "Field 'product' is required"

        additional_fields = {}
        for key, value in form_data.items():
            if key not in ["product", "file"] and value:
                additional_fields[key] = value

        return cls(product=product, zip_file_path=zip_file_path, additional_fields=additional_fields), None
