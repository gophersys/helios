"""Trigger endpoint — creates a K8s validation job for an existing run."""
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

from .types import RunTriggerRequest

# Reuse K8s job helpers from the legacy run endpoint
from src.api.v2.sessions.manual import create_kubernetes_job, create_k8s_job_name

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
    """POST /v2/validation/runs/<run_id>/trigger — Create a K8s Job for this run."""
    data, error = RunTriggerRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    # Fetch session
    session = db.session.find_unique(
        where={"id": run_id},
        include={"product": True},
    )
    if not session:
        return not_found("Validation run not found")

    # Must be ACTIVE to trigger
    if session.status != "ACTIVE":
        return bad_request(f"Cannot trigger a run with status {session.status}")

    try:
        # Determine firmware path
        firmware_path = data.firmware_path or ""

        # Build test enable flags from session config or request config
        run_config = data.config or (session.config if isinstance(session.config, dict) else {}) or {}
        test_enable = run_config.get("testEnable", {
            "electrical": True,
            "app_post": True,
            "comm_post": True,
        })

        # Get product name and revision
        product_name = session.product.name if hasattr(session, "product") and session.product else "unknown"
        product_revision = run_config.get("revision", "b0")  # Default to b0

        # Required capabilities from config (optional)
        # Use canonical stage definitions as defaults when stage is specified
        default_caps = []
        if data.stage:
            try:
                from corekinect.stages import get_stage_capabilities, Stage
                default_caps = get_stage_capabilities(Stage(data.stage))
            except (ValueError, KeyError, ImportError):
                default_caps = []
        required_capabilities = run_config.get("requiredCapabilities", default_caps)

        # Find an available fixture for this product
        fixture = _find_available_fixture(db, session.productId, required_capabilities)

        if not fixture:
            return bad_request(
                f"No available fixture for product '{product_name}' "
                f"with capabilities: {required_capabilities}"
            )

        # Lock the fixture for this run
        db.fixture.update(
            where={"id": fixture["id"]},
            data={
                "status": "LOCKED",
                "lockedBy": f"run:{run_id}",
                "lockedAt": datetime.now(timezone.utc),
            },
        )

        # Also link session to fixture
        db.session.update(
            where={"id": run_id},
            data={"fixtureId": fixture["id"]},
        )

        log_audit("validation.fixture.lock", "Fixture", fixture["id"], {
            "lockedBy": f"run:{run_id}",
            "runId": run_id,
        })

        logger.info("Locked fixture %s for run %s", fixture.get("stationId", fixture["id"]), run_id)

        # ── Multi-node: create one Device + one K8s Job per active slot ──
        user_id = g.current_user["sub"]
        api_key = _create_run_api_key(db, user_id, run_id)
        api_url = os.environ.get("CONCORD_API_URL", "http://concord-http-api.staging.svc.cluster.local:9001")

        product_slug = session.product.slug if hasattr(session, "product") and session.product else None

        active_slots = fixture.get("slots", [])
        if not active_slots:
            return bad_request("Fixture has no active slots with assigned nodes")

        # Create a Device for each slot
        devices_created = []
        for slot_info in active_slots:
            device = db.device.create(data={
                "serialNumber": slot_info.get("dutSnr") or f"slot-{slot_info.get('slotIndex', 0)}",
                "sessionId": run_id,
                "status": "PENDING",
                "metadata": Json({
                    "slotIndex": slot_info.get("slotIndex"),
                    "nodeHostname": slot_info.get("nodeHostname"),
                    "nodeIp": slot_info.get("nodeIp"),
                    "dutDeviceId": slot_info.get("dutDeviceId"),
                    "fixtureSlotId": slot_info.get("slotId"),
                }),
            })
            devices_created.append({"device": device, "slot": slot_info})

        # Set session target count for multi-node aggregation
        db.session.update(
            where={"id": run_id},
            data={"targetCount": len(devices_created)},
        )

        # Create a K8s Job for each slot
        job_names = []
        for entry in devices_created:
            slot_info = entry["slot"]
            device = entry["device"]

            mtib_host = (slot_info.get("nodeIp") or "").split(":")[0]

            job_name = create_kubernetes_job(
                product=product_name,
                job_id=f"{run_id}-s{slot_info.get('slotIndex', 0)}",
                firmware_path=firmware_path,
                test_type=session.type.lower() if hasattr(session, "type") else "validation",
                test_enable=test_enable if isinstance(test_enable, dict) else {},
                firmware_version=data.firmware_version,
                run_id=run_id,
                api_key=api_key,
                api_url=api_url,
                mtib_address=mtib_host,
                bench_id=fixture.get("id"),
                device_id=slot_info.get("dutDeviceId"),
                device_snr=slot_info.get("dutSnr"),
                fixture_profile_path=slot_info.get("profilePath"),
                pipeline_id=data.pipeline_id,
                product_slug=product_slug,
                stage=data.stage,
                # Multi-node: pass device ID so reporter knows which device to update
                extra_env={
                    "CONCORD_DEVICE_ID": device.id,
                    "CONCORD_SLOT_INDEX": str(slot_info.get("slotIndex", 0)),
                },
            )
            if job_name:
                job_names.append(job_name)

        if not job_names:
            return internal_error("Failed to create any Kubernetes jobs")

        # Store trigger metadata
        existing_config = session.config if isinstance(session.config, dict) else {}
        existing_config["trigger"] = {
            "jobNames": job_names,
            "slotCount": len(devices_created),
            "firmwareVersion": data.firmware_version,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
        }
        existing_config["apiUrl"] = api_url
        existing_config["concordRunId"] = run_id
        existing_config["fixtureId"] = fixture["id"]
        existing_config["fixtureStationId"] = fixture.get("stationId")

        db.session.update(
            where={"id": run_id},
            data={"config": Json(existing_config)},
        )

        log_audit("validation.run.trigger", "Session", run_id, {
            "jobNames": job_names,
            "slotCount": len(devices_created),
            "firmwareVersion": data.firmware_version,
        })

        return jsonify(ApiResponse.ok({
            "jobNames": job_names,
            "runId": run_id,
            "slotCount": len(devices_created),
        }).to_dict()), 200

    except Exception as e:
        logger.error(f"Failed to trigger validation run {run_id}: {e}")
        return internal_error("Failed to trigger validation run")


def _find_available_fixture(
    db,
    product_id: str,
    capabilities: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Find an available Fixture matching the product, with slot DUT info.

    Returns a dict with fixture fields merged with the first slot's hardware
    paths and DUT identity, or None if no match found.
    """
    where: Dict[str, Any] = {
        "productId": product_id,
        "status": "AVAILABLE",
        "active": True,
    }

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

        # Check capabilities if required (from fixture design)
        if capabilities and hasattr(fixture, "design") and fixture.design:
            design_caps = fixture.design.capabilities or []
            if not all(cap in design_caps for cap in capabilities):
                # Try to find another fixture with matching capabilities
                all_fixtures = db.fixture.find_many(
                    where=where,
                    include={
                        "slots": {
                            "where": {"active": True},
                            "order_by": {"slotIndex": "asc"},
                        },
                        "design": True,
                    },
                )
                fixture = None
                for f in all_fixtures:
                    if hasattr(f, "design") and f.design:
                        f_caps = f.design.capabilities or []
                        if all(cap in f_caps for cap in capabilities):
                            fixture = f
                            break
                if not fixture:
                    return None

        # Compute profile path from fixture design
        profile_path = None
        if hasattr(fixture, "design") and fixture.design:
            profile_path = f"/app/fixtures/{fixture.design.revision}.json"
        elif fixture.metadata and isinstance(fixture.metadata, dict):
            profile_path = fixture.metadata.get("profilePath")

        # Build result with per-slot info for multi-node execution
        result: Dict[str, Any] = {
            "id": fixture.id,
            "stationId": fixture.stationId,
            "name": fixture.name,
            "productId": fixture.productId,
            "status": fixture.status,
            "slots": [],
        }

        # Include node info with each slot (need include for node relation)
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
