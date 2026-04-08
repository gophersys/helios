import io
import json
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
from src.services.storage.client import StoragePrefixes, get_bucket_name, get_storage_client, storage_key

from .types import RunCreateRequest, SessionRerunRequest

logger = logging.getLogger(__name__)


# -------------------------------------------------
#                                      Serializers
# -------------------------------------------------

def _serialize_session(s: Any, include_executions: bool = False) -> dict:
    """Serialize a Session DB record to an API response dict."""
    data = {
        "id": s.id,
        "name": s.name,
        "type": s.type if hasattr(s, "type") else "VALIDATION",
        "productId": s.productId,
        "fixtureId": s.fixtureId,
        "buildRunId": s.buildRunId if hasattr(s, "buildRunId") else None,
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
    if hasattr(s, "buildRun") and s.buildRun is not None:
        data["buildRun"] = _serialize_build_run(s.buildRun)
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
    """Serialize a SessionDevice DB record to an API response dict."""
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
    """Serialize a TestExecution DB record to an API response dict."""
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
    return data


def _serialize_step(step: Any) -> dict:
    """Serialize a TestStep DB record to an API response dict."""
    return {
        "id": step.id,
        "executionId": step.executionId,
        "stepIndex": step.stepIndex,
        "name": step.name if hasattr(step, "name") else None,
        "status": step.status if hasattr(step, "status") else None,
        "passed": step.passed,
        "errorMessage": step.errorMessage if hasattr(step, "errorMessage") else None,
        "measurements": step.measurements if hasattr(step, "measurements") else None,
        "logOutput": step.logOutput if hasattr(step, "logOutput") else None,
        "durationMs": step.durationMs if hasattr(step, "durationMs") else None,
        "startedAt": step.startedAt.isoformat() if hasattr(step, "startedAt") and step.startedAt else None,
        "finishedAt": step.finishedAt.isoformat() if hasattr(step, "finishedAt") and step.finishedAt else None,
        "createdAt": step.createdAt.isoformat(),
    }


def _serialize_build_job(b: Any) -> dict:
    """Serialize a BuildJob DB record to an API response dict."""
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


def _serialize_build_run(p: Any) -> dict:
    """Serialize a BuildRun DB record to an API response dict."""
    data = {
        "id": p.id,
        "name": p.name,
        "product": p.product,
        "board": p.board,
        "branch": p.branch,
        "commitSha": p.commitSha,
        "status": p.status,
        "triggerTypes": p.triggerTypes,
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
            "pipeline": {
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

    # Kill the K8s job if one exists
    config = session.config if isinstance(session.config, dict) else {}
    job_name = (config.get("trigger") or {}).get("jobName")
    if job_name:
        try:
            from src.services.kubernetes.client import get_batch_v1_api
            from config.env import env_config
            batch_v1 = get_batch_v1_api()
            from kubernetes.client import V1DeleteOptions
            batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=env_config.VALIDATION_NAMESPACE,
                body=V1DeleteOptions(propagation_policy="Foreground"),
            )
            logger.info("Deleted K8s job %s for cancelled run %s", job_name, run_id)
        except Exception as e:
            logger.warning("Could not delete K8s job %s: %s", job_name, e)

    # Unlock the fixture
    if session.fixtureId:
        try:
            db.fixture.update(
                where={"id": session.fixtureId},
                data={"status": "AVAILABLE", "lockedBy": None, "lockedAt": None},
            )
        except Exception:
            pass

    # Mark the queue entry as CANCELLED if one exists for this session
    try:
        queue_entry = db.validationqueueentry.find_first(
            where={"sessionId": run_id},
        )
        if queue_entry and queue_entry.status == "RUNNING":
            db.validationqueueentry.update(
                where={"id": queue_entry.id},
                data={
                    "status": "CANCELLED",
                    "completedAt": datetime.now(timezone.utc),
                },
            )
    except Exception as e:
        logger.warning("Failed to update queue entry for cancelled run %s: %s", run_id, e)

    # Process the queue — start the next pending entry if a fixture is now free
    try:
        from src.api.v2.sessions.queue import process_queue
        process_queue(db)
    except Exception as e:
        logger.warning("Queue processing after run cancel failed: %s", e)

    # Reset build run status from VALIDATING back to SUCCESS
    if session.buildRunId:
        try:
            db.buildrun.update(
                where={"id": session.buildRunId},
                data={"status": "SUCCESS"},
            )
        except Exception:
            pass

    # Update session
    session = db.session.update(
        where={"id": run_id},
        data={
            "status": "CANCELLED",
            "finishedAt": datetime.now(timezone.utc),
        },
        include={"product": True, "createdBy": True},
    )

    # Notify WebSocket subscribers
    from .reporter import _emit_validation_event
    _emit_validation_event("validation_run_finish", {
        "runId": run_id,
        "status": "CANCELLED",
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
    }, run_id)

    # Generate synthetic manifest from test execution timestamps
    # so the cancelled run can enter post-analysis mode
    try:
        device = db.device.find_first(
            where={"sessionId": run_id},
            include={"executions": {"include": {"test": True}}},
        )
        if device and device.executions:
            steps = []
            for ex in device.executions:
                if ex.startedAt:
                    steps.append({
                        "name": ex.test.name if ex.test else "unknown",
                        "module": ex.test.category if ex.test else None,
                        "startedAt": ex.startedAt.timestamp(),
                        "finishedAt": ex.finishedAt.timestamp() if ex.finishedAt else datetime.now(timezone.utc).timestamp(),
                        "status": ex.status,
                    })
            if steps:
                manifest = {
                    "version": 1,
                    "runId": run_id,
                    "startedAt": min(s["startedAt"] for s in steps),
                    "finishedAt": max(s["finishedAt"] for s in steps),
                    "totalSamples": 0,
                    "channels": {},
                    "steps": steps,
                }
                # Save manifest to MinIO
                storage = get_storage_client()
                bucket = get_bucket_name()
                manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
                object_name = storage_key(StoragePrefixes.SESSIONS, f"{run_id}/telemetry/manifest.json")
                storage.put_object(bucket, object_name, io.BytesIO(manifest_bytes), length=len(manifest_bytes), content_type="application/json")
    except Exception as e:
        logger.warning("Failed to generate synthetic manifest for cancelled run %s: %s", run_id, e)

    log_audit("validation.run.cancel", "Session", run_id, {"previousStatus": "ACTIVE"})

    return jsonify(ApiResponse.ok(_serialize_session(session)).to_dict()), 200


def _resolve_active_pod(job_info: dict, namespace: str):
    """Find the active pod from job info and resolve its container names."""
    pod = None
    containers = []
    pods = job_info.get("pods") or []

    # Prefer running pod, fall back to most recent
    for p in pods:
        if p["status"] == "Running":
            pod = p
            break
    if not pod and pods:
        pod = pods[-1]

    if pod:
        from src.services.kubernetes.client import get_core_v1_api
        try:
            core = get_core_v1_api()
            pod_obj = core.read_namespaced_pod(pod["name"], namespace)
            containers = [c.name for c in (pod_obj.spec.containers or [])]
        except Exception:
            containers = ["validation"]

    return pod, containers


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

    pod, containers = _resolve_active_pod(job_info, namespace)

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
    If buildRunId is provided, uses that; otherwise uses the original's pipeline.
    """
    raw = request.get_json() or {}
    data, error = SessionRerunRequest.from_json(raw)
    if error or data is None:
        return bad_request(error)

    db = get_db_client()

    # Find original session
    original = db.session.find_unique(
        where={"id": session_id},
        include={"product": True},
    )
    if not original:
        return not_found(f"Session not found: {session_id}")

    # Determine build run to use
    build_run_id = data.build_run_id or original.buildRunId
    if build_run_id:
        # Validate build run exists
        build_run = db.buildrun.find_unique(where={"id": build_run_id})
        if not build_run:
            return not_found(f"Build run not found: {build_run_id}")

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
                "buildRunId": build_run_id,
                "status": "PENDING",
                "config": Json(new_config) if new_config else None,
                "notes": f"Rerun of session {session_id}",
            },
            include={"product": True},
        )

        log_audit("session.rerun", "Session", new_session.id, {
            "originalSessionId": session_id,
            "buildRunId": build_run_id,
            "productId": original.productId,
        })

        return jsonify(ApiResponse.created(_serialize_session(new_session)).to_dict()), 201

    except Exception as e:
        logger.error("Failed to rerun session %s: %s", session_id, e)
        return internal_error("Failed to rerun session")
