"""Build queue priority management endpoints."""

import logging

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

# Statuses that allow priority changes
_MUTABLE_STATUSES = ("QUEUED", "BLOCKED")


@require_permissions(Permissions.BUILDS_MANAGE)
def set_build_priority(build_id: str):
    """PATCH /v2/builds/<build_id>/priority — Set explicit priority on a queued build."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    if build.status not in _MUTABLE_STATUSES:
        return conflict(f"Cannot change priority of build in {build.status} state")

    data = request.get_json() or {}

    if "priority" not in data:
        return bad_request("priority is required")

    try:
        priority = int(data["priority"])
    except (TypeError, ValueError):
        return bad_request("priority must be an integer")

    if priority < 0 or priority > 1000:
        return bad_request("priority must be between 0 and 1000")

    db.buildjob.update(
        where={"id": build_id},
        data={"priority": priority},
    )

    log_audit("build.priority.set", "BuildJob", build_id, {"priority": priority})

    return jsonify(ApiResponse.ok({"id": build_id, "priority": priority}).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def promote_build(build_id: str):
    """POST /v2/builds/<build_id>/promote — Promote build to top of queue."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    if build.status not in _MUTABLE_STATUSES:
        return conflict(f"Cannot promote build in {build.status} state")

    # Find the current max priority among queued/blocked jobs
    top_jobs = db.buildjob.find_many(
        where={"status": {"in": list(_MUTABLE_STATUSES)}},
        order={"priority": "desc"},
        take=1,
    )

    max_priority = top_jobs[0].priority if top_jobs else 50
    new_priority = max_priority + 1

    db.buildjob.update(
        where={"id": build_id},
        data={"priority": new_priority},
    )

    log_audit("build.priority.promote", "BuildJob", build_id, {"priority": new_priority})

    return jsonify(ApiResponse.ok({"id": build_id, "priority": new_priority}).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def demote_build(build_id: str):
    """POST /v2/builds/<build_id>/demote — Demote build to bottom of queue."""
    db = get_db_client()

    build = db.buildjob.find_unique(where={"id": build_id})
    if not build:
        return not_found("Build job not found")

    if build.status not in _MUTABLE_STATUSES:
        return conflict(f"Cannot demote build in {build.status} state")

    # Find the current min priority among queued/blocked jobs
    bottom_jobs = db.buildjob.find_many(
        where={"status": {"in": list(_MUTABLE_STATUSES)}},
        order={"priority": "asc"},
        take=1,
    )

    min_priority = bottom_jobs[0].priority if bottom_jobs else 50
    new_priority = max(0, min_priority - 1)

    db.buildjob.update(
        where={"id": build_id},
        data={"priority": new_priority},
    )

    log_audit("build.priority.demote", "BuildJob", build_id, {"priority": new_priority})

    return jsonify(ApiResponse.ok({"id": build_id, "priority": new_priority}).to_dict()), 200
