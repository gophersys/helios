"""Trigger endpoint -- creates a K8s validation job for an existing TestRun."""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from config.env import env_config
from database import Json
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from corekinect.stages import Stage
from src.api.v2.runs.types import RunTriggerRequest

# Reuse K8s job helpers from the new run endpoint
from src.api.v2.runs.manual import create_kubernetes_job, create_k8s_job_name

logger = logging.getLogger(__name__)


def _create_run_api_key(db, user_id: str, run_id: str) -> str:
    """Create a database-backed API key for a validation K8s job.

    Returns the raw key string (to be injected into the K8s Job env).
    The key expires after 24 hours.
    """
    raw_key = f"ck_run_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db.apikey.create(
        data={
            "name": f"Validation run {run_id}",
            "keyHash": key_hash,
            "keyPrefix": raw_key[:12],
            "userId": user_id,
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=24),
        },
    )

    return raw_key


@require_permissions(Permissions.VALIDATION_RUN)
def trigger_run(run_id: str):
    """POST /v2/runs/<run_id>/trigger -- Create a K8s Job for this TestRun."""
    data, error = RunTriggerRequest.from_json(request.get_json())
    if error or data is None:
        return bad_request(error)

    db = get_db_client()

    # Fetch TestRun
    run = db.testrun.find_unique(
        where={"id": run_id},
        include={"product": True},
    )
    if not run:
        return not_found("Validation run not found")

    # Must be ACTIVE to trigger
    if run.status != "ACTIVE":
        return bad_request(f"Cannot trigger a run with status {run.status}")

    try:
        # Determine firmware path
        firmware_path = data.firmware_path or ""

        run_config = data.config or (run.config if isinstance(run.config, dict) else {}) or {}

        # Get product name and revision
        product_name = run.product.name if hasattr(run, "product") and run.product else "unknown"
        product_revision = run_config.get("revision", "b0")

        # Find an available fixture for this product. Fixture <-> test
        # app match is established by per-package design ownership: the
        # caller is expected to have queued runs against a TestPackage
        # whose owned design matches an available fixture's designId.
        # Capability-based filtering went away with the v0.5.x refactor.
        fixture = _find_available_fixture(db, run.productId)

        if not fixture:
            return bad_request(
                f"No available fixture for product '{product_name}'"
            )

        # Link TestRun to fixture. The run's status=ACTIVE row is now what
        # makes the fixture's derived lockState read as IN_USE — there is
        # no separate fixture-lock write to perform.
        db.testrun.update(
            where={"id": run_id},
            data={"fixtureId": fixture["id"]},
        )

        log_audit("validation.fixture.assign", "Fixture", fixture["id"], {
            "runId": run_id,
        })

        logger.info("Assigned fixture %s for run %s", fixture.get("stationId", fixture["id"]), run_id)

        # ── Multi-node: create one RunTarget + one K8s Job per active slot ──
        user_id = g.current_user["sub"]
        api_key = _create_run_api_key(db, user_id, run_id)
        api_url = os.environ.get("CONCORD_API_URL", "http://concord-http-api.staging.svc.cluster.local:9001")

        product_slug = run.product.slug if hasattr(run, "product") and run.product else None

        active_slots = fixture.get("slots", [])
        if not active_slots:
            return bad_request("Fixture has no active slots with assigned nodes")

        # Create a RunTarget for each slot
        targets_created = []
        for slot_info in active_slots:
            target = db.runtarget.create(data={
                "runId": run_id,
                "slotIndex": slot_info.get("slotIndex", 0),
                "slotId": slot_info.get("slotId"),
                "serialNumber": slot_info.get("dutSnr") or f"slot-{slot_info.get('slotIndex', 0)}",
                "deviceId": slot_info.get("dutDeviceId"),
                "status": "PENDING",
                "metadata": Json({
                    "slotIndex": slot_info.get("slotIndex"),
                    "nodeHostname": slot_info.get("nodeHostname"),
                    "nodeIp": slot_info.get("nodeIp"),
                    "dutDeviceId": slot_info.get("dutDeviceId"),
                    "fixtureSlotId": slot_info.get("slotId"),
                }),
            })
            targets_created.append({"target": target, "slot": slot_info})

        # Set run target count for multi-node aggregation
        db.testrun.update(
            where={"id": run_id},
            data={"targetCount": len(targets_created)},
        )

        # Create a K8s Job for each slot
        job_names = []
        for entry in targets_created:
            slot_info = entry["slot"]
            target = entry["target"]

            mtib_host = (slot_info.get("nodeIp") or "").split(":")[0]

            job_name = create_kubernetes_job(
                product=product_name,
                job_id=f"{run_id}-s{slot_info.get('slotIndex', 0)}",
                firmware_path=firmware_path,
                test_type=run.type.lower() if hasattr(run, "type") else "validation",
                firmware_version=data.firmware_version,
                run_id=run_id,
                api_key=api_key,
                api_url=api_url,
                mtib_address=mtib_host,
                fixture_id=fixture.get("id"),
                device_id=slot_info.get("dutDeviceId"),
                device_snr=slot_info.get("dutSnr"),
                build_run_id=data.build_run_id,
                product_slug=product_slug,
                stage=data.stage,
                extra_env={
                    "CONCORD_TARGET_ID": target.id,
                    "CONCORD_SLOT_INDEX": str(slot_info.get("slotIndex", 0)),
                    "CONCORD_SESSION_ID": run_id,
                    "FIXTURE_ID": fixture.get("id", ""),
                },
            )
            if job_name:
                job_names.append(job_name)

        if not job_names:
            return internal_error("Failed to create any Kubernetes jobs")

        # Store trigger metadata
        existing_config = run.config if isinstance(run.config, dict) else {}
        existing_config["trigger"] = {
            "jobNames": job_names,
            "slotCount": len(targets_created),
            "firmwareVersion": data.firmware_version,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
        }
        existing_config["apiUrl"] = api_url
        existing_config["concordRunId"] = run_id
        existing_config["fixtureId"] = fixture["id"]
        existing_config["fixtureStationId"] = fixture.get("stationId")

        db.testrun.update(
            where={"id": run_id},
            data={"config": Json(existing_config)},
        )

        log_audit("validation.run.trigger", "TestRun", run_id, {
            "jobNames": job_names,
            "slotCount": len(targets_created),
            "firmwareVersion": data.firmware_version,
        })

        return jsonify(ApiResponse.ok({
            "jobNames": job_names,
            "runId": run_id,
            "slotCount": len(targets_created),
        }).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to trigger validation run {run_id}: {e}")
        return internal_error("Failed to trigger validation run")


def _find_available_fixture(
    db,
    product_id: str,
) -> Optional[Dict[str, Any]]:
    """Find an available Fixture matching the product, with slot DUT info.

    Returns a dict with fixture fields merged with per-slot hardware
    paths and DUT identity, or None if no match found.
    """
    # "Free" is derived live: not disabled, no active session, no active run.
    held_session_ids = {
        s.fixtureId for s in db.manufacturingsession.find_many(where={"status": "ACTIVE"})
        if getattr(s, "fixtureId", None)
    }
    held_run_ids = {
        r.fixtureId for r in db.testrun.find_many(where={"status": "ACTIVE"})
        if getattr(r, "fixtureId", None)
    }
    held_ids = held_session_ids | held_run_ids
    where: Dict[str, Any] = {
        "productId": product_id,
        "active": True,
        "disabled": False,
    }
    if held_ids:
        where["id"] = {"notIn": list(held_ids)}

    try:
        fixture = db.fixture.find_first(
            where=where,
            include={
                "slots": {
                    "where": {"active": True},
                    "order_by": {"slotIndex": "asc"},
                },
                "design": True,
            },
        )

        if not fixture:
            return None

        # Compute profile path from TestBed design
        profile_path = None
        if hasattr(fixture, "design") and fixture.design:
            profile_path = f"/app/fixtures/{fixture.design.revision}.json"
        elif fixture.metadata and isinstance(fixture.metadata, dict):
            profile_path = fixture.metadata.get("profilePath")

        # Build result with per-slot info for multi-node execution
        # lockState is derived; this picker only ever returns fixtures that
        # were "FREE" at query time, so we hardcode it on the result dict.
        result: Dict[str, Any] = {
            "id": fixture.id,
            "stationId": fixture.stationId,
            "name": fixture.name,
            "productId": fixture.productId,
            "lockState": "FREE",
            "slots": [],
        }

        # Include node info with each slot
        slots = fixture.slots or []
        for slot in slots:
            if not slot.nodeId:
                continue  # Skip unassigned slots
            # Resolve node if not already included
            node = None
            if hasattr(slot, "node") and slot.node:
                node = slot.node
            else:
                node = db.node.find_unique(where={"id": slot.nodeId})

            if not node or not node.ipAddress:
                continue  # Skip nodes without IP (not reachable)

            result["slots"].append({
                "slotId": slot.id,
                "slotIndex": slot.slotIndex,
                "nodeId": slot.nodeId,
                "nodeHostname": node.hostname,
                "nodeIp": f"{node.ipAddress}:50053",
                "dutDeviceId": slot.dutDeviceId,
                "dutSnr": slot.dutSnr,
                "dutImei": slot.dutImei,
                "dutIccids": slot.dutIccids or [],
                "profilePath": profile_path,
            })

        # Also store first-slot data at top level for backward compat
        if result["slots"]:
            first = result["slots"][0]
            result["mtibAddress"] = first["nodeIp"]
            result["dutDeviceId"] = first["dutDeviceId"]
            result["dutSnr"] = first["dutSnr"]

        return result

    except Exception as e:
        logger.error(f"Failed to find available fixture: {e}")
        return None
