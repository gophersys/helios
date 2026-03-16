import logging
import math
from datetime import datetime, timezone
from typing import Any

from database import Json
from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .types import RunCreateRequest, SessionRerunRequest

logger = logging.getLogger(__name__)


# -------------------------------------------------
#                                      Serializers
# -------------------------------------------------

def _serialize_session(s: Any, include_executions: bool = False) -> dict:
    data = {
        "id": s.id,
        "name": s.name,
        "type": s.type if hasattr(s, "type") else "VALIDATION",
        "productId": s.productId,
        "fixtureId": s.fixtureId,
        "pipelineRunId": s.pipelineRunId if hasattr(s, "pipelineRunId") else None,
        "status": s.status,
        "config": s.config,
        "targetCount": s.targetCount,
        "completedCount": s.completedCount,
        "passedCount": s.passedCount,
        "failedCount": s.failedCount,
        "durationMs": s.durationMs if hasattr(s, "durationMs") else None,
        "errorMessage": s.errorMessage if hasattr(s, "errorMessage") else None,
        "startedAt": s.startedAt.isoformat() if s.startedAt else None,
        "finishedAt": s.finishedAt.isoformat() if s.finishedAt else None,
        "notes": s.notes,
        "createdAt": s.createdAt.isoformat(),
        "updatedAt": s.updatedAt.isoformat(),
    }
    if hasattr(s, "product") and s.product is not None:
        data["product"] = {"id": s.product.id, "name": s.product.name}
    if hasattr(s, "createdBy") and s.createdBy is not None:
        data["createdBy"] = {"id": s.createdBy.id, "name": s.createdBy.name, "email": s.createdBy.email}
    if hasattr(s, "pipelineRun") and s.pipelineRun is not None:
        data["pipelineRun"] = _serialize_pipeline_run(s.pipelineRun)
    if hasattr(s, "devices") and s.devices is not None:
        data["devices"] = [_serialize_device(d) for d in s.devices]
    if include_executions and hasattr(s, "devices") and s.devices is not None:
        executions = []
        for d in s.devices:
            if hasattr(d, "executions") and d.executions is not None:
                for ex in d.executions:
                    # Include full results with logs for run detail page
                    executions.append(_serialize_execution(ex, include_results=True))
        data["executions"] = executions
    return data


def _serialize_device(d: Any) -> dict:
    data = {
        "id": d.id,
        "serialNumber": d.serialNumber,
        "sessionId": d.sessionId,
        "status": d.status,
        "metadata": d.metadata,
        "createdAt": d.createdAt.isoformat(),
        "updatedAt": d.updatedAt.isoformat(),
    }
    return data


def _serialize_execution(ex: Any, include_results: bool = False) -> dict:
    data = {
        "id": ex.id,
        "testId": ex.testId,
        "nodeId": ex.nodeId,
        "deviceId": ex.deviceId,
        "status": ex.status,
        "config": ex.config,
        "startedAt": ex.startedAt.isoformat() if ex.startedAt else None,
        "finishedAt": ex.finishedAt.isoformat() if ex.finishedAt else None,
        "createdAt": ex.createdAt.isoformat(),
        "updatedAt": ex.updatedAt.isoformat(),
    }
    if hasattr(ex, "test") and ex.test is not None:
        data["test"] = {"id": ex.test.id, "name": ex.test.name, "category": ex.test.category}
    if hasattr(ex, "steps") and ex.steps is not None:
        data["stepCount"] = len(ex.steps)
        data["stepsPassed"] = sum(1 for step in ex.steps if step.passed)
        if include_results:
            data["steps"] = [_serialize_step(step) for step in ex.steps]
    # Backward compat: also check legacy 'results' relation name
    elif hasattr(ex, "results") and ex.results is not None:
        data["stepCount"] = len(ex.results)
        data["stepsPassed"] = sum(1 for r in ex.results if r.passed)
        if include_results:
            data["steps"] = [_serialize_step(r) for r in ex.results]
    return data


def _serialize_step(step: Any) -> dict:
    return {
        "id": step.id,
        "executionId": step.executionId,
        "stepIndex": step.stepIndex,
        "name": step.name if hasattr(step, "name") else None,
        "status": step.status if hasattr(step, "status") else None,
        "passed": step.passed,
        "errorMessage": step.errorMessage if hasattr(step, "errorMessage") else None,
        "measurements": step.measurements if hasattr(step, "measurements") else None,
        "durationMs": step.durationMs if hasattr(step, "durationMs") else None,
        "startedAt": step.startedAt.isoformat() if hasattr(step, "startedAt") and step.startedAt else None,
        "finishedAt": step.finishedAt.isoformat() if hasattr(step, "finishedAt") and step.finishedAt else None,
        "createdAt": step.createdAt.isoformat(),
    }


def _serialize_build_job(b: Any) -> dict:
    # Calculate duration from timestamps if available
    duration_seconds = None
    if b.startedAt and b.finishedAt:
        duration_seconds = int((b.finishedAt - b.startedAt).total_seconds())

    data = {
        "id": b.id,
        "product": b.product,
        "board": b.board,
        "target": b.target,
        "variant": b.variant,
        "mtibRev": b.mtibRev,
        "branch": b.branch,
        "commitSha": b.commitSha,
        "status": b.status,
        "versionMajor": b.versionMajor,
        "versionMinor": b.versionMinor,
        "buildNum": b.buildNum,
        "versionString": b.versionString,
        "errorMessage": b.errorMessage,
        "logOutput": b.buildLog,  # Schema uses buildLog, frontend expects logOutput
        "durationSeconds": duration_seconds,
        "startedAt": b.startedAt.isoformat() if b.startedAt else None,
        "finishedAt": b.finishedAt.isoformat() if b.finishedAt else None,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "artifacts") and b.artifacts is not None:
        data["artifacts"] = [
            {
                "id": a.id,
                "name": a.name,
                "storageKey": a.storageKey,
                "sizeBytes": str(a.sizeBytes),
            }
            for a in b.artifacts
        ]
    return data


def _serialize_pipeline_run(p: Any) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "product": p.product,
        "board": p.board,
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerType": p.triggerType,
        "expectedBuilds": p.expectedBuilds,
        "completedBuilds": p.completedBuilds,
        "startedAt": p.startedAt.isoformat() if p.startedAt else None,
        "finishedAt": p.finishedAt.isoformat() if p.finishedAt else None,
        "createdAt": p.createdAt.isoformat(),
        "updatedAt": p.updatedAt.isoformat(),
    }
    if hasattr(p, "builds") and p.builds is not None:
        data["builds"] = [_serialize_build_job(b) for b in p.builds]
    return data


# -------------------------------------------------
#                                 Public Endpoints
# -------------------------------------------------

@require_permissions(Permissions.VALIDATION_RUN)
def create_run():
    """POST /v2/validation/runs — Create a new validation run."""
    from flask import g

    data, error = RunCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Validate product exists
    product = db.product.find_unique(where={"id": data.product_id})
    if not product:
        return not_found("Product not found")

    # Validate node exists
    node = db.node.find_unique(where={"id": data.node_id})
    if not node:
        return not_found("Node not found")

    # Build session config
    session_config = data.config or {}
    if data.firmware_variant:
        session_config["firmwareVariant"] = data.firmware_variant
    session_config["nodeId"] = data.node_id
    session_config["serialNumber"] = data.serial_number

    user_id = g.current_user["sub"]

    try:
        # Create Session
        session = db.session.create(
            data={
                "name": data.name,
                "type": data.type,
                "productId": data.product_id,
                "status": "ACTIVE",
                "config": Json(session_config) if session_config else None,
                "notes": data.notes,
                "createdById": user_id,
            },
            include={"product": True, "createdBy": True},
        )

        # Create Device (the DUT being tested)
        device = db.device.create(
            data={
                "serialNumber": data.serial_number,
                "sessionId": session.id,
                "status": "PENDING",
            },
        )

        # Find enabled tests for this product, optionally filtered
        test_where = {"productId": data.product_id, "enabled": True}
        if data.test_filter:
            test_where["name"] = {"in": data.test_filter}

        tests = db.test.find_many(
            where=test_where,
            order={"sortOrder": "asc"},
        )

        # Create TestExecution for each test
        executions = []
        for test in tests:
            execution = db.testexecution.create(
                data={
                    "testId": test.id,
                    "nodeId": data.node_id,
                    "deviceId": device.id,
                    "status": "QUEUED",
                    "triggeredById": user_id,
                },
            )
            executions.append(execution)

        # Update session target count
        db.session.update(
            where={"id": session.id},
            data={"targetCount": len(executions)},
        )

        log_audit("validation.run.create", "Session", session.id, {
            "name": data.name,
            "productId": data.product_id,
            "nodeId": data.node_id,
            "serialNumber": data.serial_number,
            "testCount": len(executions),
        })

        result = _serialize_session(session)
        result["devices"] = [_serialize_device(device)]
        result["targetCount"] = len(executions)
        result["executionCount"] = len(executions)

        return jsonify(ApiResponse.created(result).to_dict()), 201

    except Exception as e:
        logger.error(f"Failed to create validation run: {e}")
        return internal_error("Failed to create validation run")


@require_permissions(Permissions.VALIDATION_VIEW)
def list_runs():
    """GET /v2/validation/runs — List validation runs with pagination and filters."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Build filter
    where = {}
    status = request.args.get("status")
    if status:
        where["status"] = status.upper()

    product_id = request.args.get("productId")
    if product_id:
        where["productId"] = product_id

    # Filter by session type (VALIDATION, MANUFACTURING)
    session_type = request.args.get("type")
    if session_type:
        where["type"] = session_type.upper()

    total = db.session.count(where=where)
    sessions = db.session.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={
            "product": True,
            "createdBy": True,
            "devices": True,
        },
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_session(s) for s in sessions],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_run(run_id: str):
    """GET /v2/validation/runs/<id> — Run detail with devices, executions, and build pipeline."""
    db = get_db_client()

    session = db.session.find_unique(
        where={"id": run_id},
        include={
            "product": True,
            "createdBy": True,
            "pipelineRun": {
                "include": {
                    "builds": {
                        "include": {
                            "artifacts": True,
                        },
                        "order_by": {"createdAt": "asc"},
                    },
                },
            },
            "devices": {
                "include": {
                    "executions": {
                        "include": {
                            "test": True,
                            "steps": True,
                        },
                    },
                },
            },
        },
    )

    if not session:
        return not_found("Validation run not found")

    return jsonify(ApiResponse.ok(_serialize_session(session, include_executions=True)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def cancel_run(run_id: str):
    """POST /v2/validation/runs/<id>/cancel — Cancel a running session."""
    db = get_db_client()

    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return not_found("Validation run not found")

    if session.status not in ("ACTIVE", "PENDING"):
        return conflict(f"Cannot cancel a run with status {session.status}")

    # Cancel all queued/running executions
    db.testexecution.update_many(
        where={
            "device": {"sessionId": run_id},
            "status": {"in": ["QUEUED", "RUNNING"]},
        },
        data={"status": "CANCELLED"},
    )

    # Update session
    session = db.session.update(
        where={"id": run_id},
        data={
            "status": "CANCELLED",
            "finishedAt": datetime.now(timezone.utc),
        },
        include={"product": True, "createdBy": True},
    )

    log_audit("validation.run.cancel", "Session", run_id, {"previousStatus": "ACTIVE"})

    return jsonify(ApiResponse.ok(_serialize_session(session)).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_run_job(run_id: str):
    """GET /v2/validation/runs/<id>/job — Get K8s job and pod info for live log streaming."""
    db = get_db_client()

    session = db.session.find_unique(where={"id": run_id})
    if not session:
        return not_found("Validation run not found")

    # Extract job name from config
    config = session.config if isinstance(session.config, dict) else {}
    trigger_meta = config.get("trigger", {})
    job_name = trigger_meta.get("jobName")

    if not job_name:
        return jsonify(ApiResponse.ok({
            "jobName": None,
            "pod": None,
            "message": "No K8s job associated with this run",
        }).to_dict()), 200

    # Get job and pod info from K8s
    from src.services.kubernetes import jobs as jobs_svc

    # Validation jobs run in staging namespace by default
    namespace = config.get("namespace", "staging")

    job_info = jobs_svc.get_job(namespace, job_name)
    if not job_info:
        # Job may have been cleaned up
        return jsonify(ApiResponse.ok({
            "jobName": job_name,
            "namespace": namespace,
            "pod": None,
            "message": "K8s job not found (may have been cleaned up)",
        }).to_dict()), 200

    # Find the active pod
    pod = None
    containers = []
    if job_info.get("pods"):
        # Prefer running pod, fall back to most recent
        for p in job_info["pods"]:
            if p["status"] == "Running":
                pod = p
                break
        if not pod and job_info["pods"]:
            pod = job_info["pods"][-1]  # Most recent

    # Get container names from the pod
    if pod:
        from src.services.kubernetes.client import get_core_v1_api
        try:
            core = get_core_v1_api()
            pod_obj = core.read_namespaced_pod(pod["name"], namespace)
            containers = [c.name for c in (pod_obj.spec.containers or [])]
        except Exception:
            containers = ["validation"]  # Default container name

    return jsonify(ApiResponse.ok({
        "jobName": job_name,
        "namespace": namespace,
        "job": {
            "status": job_info.get("status"),
            "succeeded": job_info.get("succeeded"),
            "failed": job_info.get("failed"),
            "active": job_info.get("active"),
        },
        "pod": pod,
        "containers": containers,
    }).to_dict()), 200


@require_permissions(Permissions.VALIDATION_RUN)
def rerun_session(session_id: str):
    """POST /v2/sessions/<id>/rerun — Clone a session with optional different pipeline.

    Creates a new Session copying productId, fixtureId, type from the original.
    If pipelineRunId is provided, uses that; otherwise uses the original's pipeline.
    """
    raw = request.get_json() or {}
    data, error = SessionRerunRequest.from_json(raw)
    if error:
        return bad_request(error)

    db = get_db_client()

    # Find original session
    original = db.session.find_unique(
        where={"id": session_id},
        include={"product": True},
    )
    if not original:
        return not_found(f"Session not found: {session_id}")

    # Determine pipeline to use
    pipeline_run_id = data.pipeline_run_id or original.pipelineRunId
    if pipeline_run_id:
        # Validate pipeline exists
        pipeline = db.pipelinerun.find_unique(where={"id": pipeline_run_id})
        if not pipeline:
            return not_found(f"Pipeline not found: {pipeline_run_id}")

    try:
        # Build config for the new session
        original_config = original.config if isinstance(original.config, dict) else {}
        new_config = {
            **original_config,
            "rerunOf": session_id,
        }

        # Create new session
        new_session = db.session.create(
            data={
                "name": f"Rerun of {original.name}",
                "type": original.type,
                "productId": original.productId,
                "fixtureId": original.fixtureId,
                "pipelineRunId": pipeline_run_id,
                "status": "PENDING",
                "config": Json(new_config) if new_config else None,
                "notes": f"Rerun of session {session_id}",
            },
            include={"product": True},
        )

        log_audit("session.rerun", "Session", new_session.id, {
            "originalSessionId": session_id,
            "pipelineRunId": pipeline_run_id,
            "productId": original.productId,
        })

        return jsonify(ApiResponse.created(_serialize_session(new_session)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to rerun session %s: %s", session_id, e)
        return internal_error("Failed to rerun session")
