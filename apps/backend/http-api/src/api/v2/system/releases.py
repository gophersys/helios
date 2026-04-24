"""Release management — create, list, update, delete, and link bugs to releases.

POST/PATCH/DELETE restricted to releases:manage.
GET available to any authenticated user.
"""

import logging
from datetime import datetime, timezone

from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions
from src.lib.errors import bad_request, conflict, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"DRAFT", "STAGED", "RELEASED", "ROLLED_BACK"}


def _serialize(r, resolved_bug_count: int | None = None) -> dict:
    return {
        "id": r.id,
        "version": r.version,
        "status": r.status,
        "commitSha": r.commitSha,
        "branch": getattr(r, "branch", "main"),
        "previousVersion": getattr(r, "previousVersion", None),
        "corekinectVersion": getattr(r, "corekinectVersion", None),
        "corectlMinVersion": getattr(r, "corectlMinVersion", None),
        "protoVersion": getattr(r, "protoVersion", None),
        "migrationHash": getattr(r, "migrationHash", None),
        "changelog": getattr(r, "changelog", None),
        "summary": getattr(r, "summary", None),
        "breakingChanges": getattr(r, "breakingChanges", None),
        "testsPassed": getattr(r, "testsPassed", None),
        "testsFailed": getattr(r, "testsFailed", None),
        "testCoverage": getattr(r, "testCoverage", None),
        "testDurationMs": getattr(r, "testDurationMs", None),
        "testDetails": getattr(r, "testDetails", None),
        "linesAdded": getattr(r, "linesAdded", None),
        "linesRemoved": getattr(r, "linesRemoved", None),
        "prUrl": getattr(r, "prUrl", None),
        "releaseOrigin": getattr(r, "releaseOrigin", None),
        "releaseDurationMs": getattr(r, "releaseDurationMs", None),
        "gateStatus": getattr(r, "gateStatus", None),
        "gateOverrideBy": getattr(r, "gateOverrideBy", None),
        "gateOverrideReason": getattr(r, "gateOverrideReason", None),
        "stagedAt": r.stagedAt.isoformat() if hasattr(r, "stagedAt") and r.stagedAt else None,
        "releasedAt": r.releasedAt.isoformat() if hasattr(r, "releasedAt") and r.releasedAt else None,
        "rolledBackAt": r.rolledBackAt.isoformat() if hasattr(r, "rolledBackAt") and r.rolledBackAt else None,
        "createdById": getattr(r, "createdById", None),
        "createdAt": r.createdAt.isoformat() if hasattr(r, "createdAt") else None,
        "updatedAt": r.updatedAt.isoformat() if hasattr(r, "updatedAt") else None,
        "resolvedBugCount": resolved_bug_count,
    }


@require_permissions(Permissions.RELEASES_MANAGE)
def create_release():
    """POST /v2/releases — create a new release."""
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    version = (data.get("version") or "").strip()
    if not version:
        return bad_request("version is required")

    commit_sha = (data.get("commitSha") or "").strip()
    if not commit_sha:
        return bad_request("commitSha is required")

    db = get_db_client()

    # Check for duplicate version
    existing = db.release.find_unique(where={"version": version})
    if existing:
        return conflict(f"Release version '{version}' already exists")

    user_id = getattr(g, "current_user", {}).get("sub")

    create_data = {
        "version": version,
        "commitSha": commit_sha,
        "branch": (data.get("branch") or "main").strip(),
        "createdById": user_id,
    }

    # Optional fields
    for field in (
        "previousVersion", "corekinectVersion", "corectlMinVersion",
        "protoVersion", "migrationHash", "changelog", "summary",
        "breakingChanges", "gateStatus", "gateOverrideReason",
        "prUrl", "releaseOrigin",
    ):
        val = data.get(field)
        if val is not None:
            create_data[field] = str(val).strip() if isinstance(val, str) else val

    for int_field in ("testsPassed", "testsFailed", "testDurationMs",
                      "linesAdded", "linesRemoved", "releaseDurationMs"):
        val = data.get(int_field)
        if val is not None:
            create_data[int_field] = int(val)

    if data.get("testCoverage") is not None:
        create_data["testCoverage"] = float(data["testCoverage"])

    if data.get("testDetails") is not None and isinstance(data["testDetails"], dict):
        create_data["testDetails"] = data["testDetails"]

    if "status" in data:
        status = (data["status"] or "").strip()
        if status in _VALID_STATUSES:
            create_data["status"] = status
            now = datetime.now(timezone.utc)
            if status == "STAGED":
                create_data["stagedAt"] = now
            elif status == "RELEASED":
                create_data["releasedAt"] = now

    release = db.release.create(data=create_data)

    log_audit("release.create", "Release", release.id, {
        "version": version,
    })

    return jsonify(ApiResponse.ok(_serialize(release)).to_dict()), 201


@require_auth
def list_releases():
    """GET /v2/releases — paginated list with optional status filter."""
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}

    status = request.args.get("status")
    if status and status in _VALID_STATUSES:
        where["status"] = status

    db = get_db_client()
    total = db.release.count(where=where)
    releases = db.release.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )

    # Batch-count resolved bugs per release
    release_ids = [r.id for r in releases]
    bug_counts: dict[str, int] = {}
    if release_ids:
        for rid in release_ids:
            bug_counts[rid] = db.errorreport.count(where={"resolvedInReleaseId": rid})

    pages = (total + limit - 1) // limit if total > 0 else 0
    return jsonify(ApiResponse.ok({
        "data": [_serialize(r, resolved_bug_count=bug_counts.get(r.id, 0)) for r in releases],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": pages},
    }).to_dict()), 200


@require_auth
def get_release(release_id: str):
    """GET /v2/releases/<id> — full release with resolved bugs."""
    db = get_db_client()
    release = db.release.find_unique(
        where={"id": release_id},
        include={"resolvedErrorReports": True},
    )
    if not release:
        return not_found("Release not found")

    bugs = list(release.resolvedErrorReports) if hasattr(release, "resolvedErrorReports") and release.resolvedErrorReports else []
    result = _serialize(release, resolved_bug_count=len(bugs))

    result["resolvedErrorReports"] = [
        {
            "id": r.id,
            "status": r.status,
            "type": r.type,
            "severity": r.severity,
            "message": r.message,
            "currentPath": getattr(r, "currentPath", None),
            "appVersion": getattr(r, "appVersion", None),
            "createdAt": r.createdAt.isoformat() if hasattr(r, "createdAt") and r.createdAt else None,
            "resolvedAt": r.resolvedAt.isoformat() if hasattr(r, "resolvedAt") and r.resolvedAt else None,
        }
        for r in bugs
    ]

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.RELEASES_MANAGE)
def update_release(release_id: str):
    """PATCH /v2/releases/<id> — update status, changelog, gate info."""
    db = get_db_client()
    release = db.release.find_unique(where={"id": release_id})
    if not release:
        return not_found("Release not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    update_data: dict = {}

    if "status" in data:
        new_status = (data["status"] or "").strip()
        if new_status not in _VALID_STATUSES:
            return bad_request(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        update_data["status"] = new_status

        now = datetime.now(timezone.utc)
        if new_status == "STAGED":
            update_data["stagedAt"] = now
        elif new_status == "RELEASED":
            update_data["releasedAt"] = now
        elif new_status == "ROLLED_BACK":
            update_data["rolledBackAt"] = now

    # Text fields
    for field in ("changelog", "summary", "breakingChanges", "gateOverrideReason"):
        if field in data:
            update_data[field] = (data[field] or "").strip() or None

    # String fields
    for field in ("commitSha", "branch", "gateStatus", "previousVersion",
                  "corekinectVersion", "corectlMinVersion", "protoVersion",
                  "migrationHash", "prUrl", "releaseOrigin"):
        if field in data:
            update_data[field] = (data[field] or "").strip() or None

    # Gate override
    if "gateStatus" in data and data["gateStatus"] == "overridden":
        user_id = getattr(g, "current_user", {}).get("sub")
        update_data["gateOverrideBy"] = user_id

    # Numeric fields
    for int_field in ("testsPassed", "testsFailed", "testDurationMs",
                      "linesAdded", "linesRemoved", "releaseDurationMs"):
        if int_field in data:
            update_data[int_field] = int(data[int_field]) if data[int_field] is not None else None

    if "testCoverage" in data:
        update_data["testCoverage"] = float(data["testCoverage"]) if data["testCoverage"] is not None else None

    if "testDetails" in data:
        update_data["testDetails"] = data["testDetails"] if isinstance(data["testDetails"], dict) else None

    if not update_data:
        return bad_request("No fields to update")

    updated = db.release.update(where={"id": release_id}, data=update_data)
    log_audit("release.update", "Release", release_id, {
        "fields": list(update_data.keys()),
    })
    return jsonify(ApiResponse.ok(_serialize(updated)).to_dict()), 200


@require_permissions(Permissions.RELEASES_MANAGE)
def delete_release(release_id: str):
    """DELETE /v2/releases/<id> — delete draft releases only."""
    db = get_db_client()
    release = db.release.find_unique(where={"id": release_id})
    if not release:
        return not_found("Release not found")

    if release.status != "DRAFT":
        return bad_request("Only DRAFT releases can be deleted")

    db.release.delete(where={"id": release_id})
    log_audit("release.delete", "Release", release_id, {
        "version": release.version,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.RELEASES_MANAGE)
def link_bugs_to_release(release_id: str):
    """POST /v2/releases/<id>/link-bugs — link resolved error reports.

    Atomically marks the reports as RESOLVED and stamps resolvedAt/resolvedById
    alongside the FK. Linking == fixing — this is the single source of truth.
    """
    db = get_db_client()
    release = db.release.find_unique(where={"id": release_id})
    if not release:
        return not_found("Release not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    error_report_ids = data.get("errorReportIds")
    if not error_report_ids or not isinstance(error_report_ids, list):
        return bad_request("errorReportIds is required and must be a list")

    resolver_id = g.current_user.get("sub") if getattr(g, "current_user", None) else None

    db.errorreport.update_many(
        where={"id": {"in": error_report_ids}},
        data={
            "resolvedInReleaseId": release_id,
            "status": "RESOLVED",
            "resolvedAt": datetime.now(timezone.utc),
            "resolvedById": resolver_id,
        },
    )

    log_audit("release.link_bugs", "Release", release_id, {
        "errorReportIds": error_report_ids,
    })
    return jsonify(ApiResponse.ok({"linked": len(error_report_ids)}).to_dict()), 200


@require_permissions(Permissions.RELEASES_MANAGE)
def unlink_bug_from_release(release_id: str, report_id: str):
    """DELETE /v2/releases/<id>/resolved-bugs/<report_id> — reopen a linked bug.

    Clears the release FK and flips the report back to OPEN. Used when a user
    realizes a bug they linked wasn't actually fixed in this release.
    """
    db = get_db_client()
    report = db.errorreport.find_unique(where={"id": report_id})
    if not report:
        return not_found("Error report not found")
    if report.resolvedInReleaseId != release_id:
        return bad_request("Error report is not linked to this release")

    db.errorreport.update(
        where={"id": report_id},
        data={
            "resolvedInReleaseId": None,
            "status": "OPEN",
            "resolvedAt": None,
            "resolvedById": None,
        },
    )
    log_audit("release.unlink_bug", "Release", release_id, {"errorReportId": report_id})
    return jsonify(ApiResponse.ok({"unlinked": report_id}).to_dict()), 200
