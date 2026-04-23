"""Error reports — stores frontend bug reports and error diagnostics.

POST accepts reports from any authenticated user.
GET/DELETE/PATCH restricted to system:view / system:manage.
"""

import logging
from datetime import datetime, timezone

from database import Json
from flask import g, jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_auth, require_permissions
from src.lib.errors import bad_request, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

_VALID_TYPES = {"js", "api", "websocket", "validation", "unhandled", "user_report"}
_VALID_SEVERITIES = {"critical", "error", "warning", "info"}
_VALID_STATUSES = {"OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"}


def _serialize(r) -> dict:
    return {
        "id": r.id,
        "status": r.status,
        "type": r.type,
        "severity": r.severity,
        "message": r.message,
        "context": r.context if hasattr(r, "context") and r.context else None,
        "currentPath": getattr(r, "currentPath", None),
        "userEmail": getattr(r, "userEmail", None),
        "userId": getattr(r, "userId", None),
        "appVersion": getattr(r, "appVersion", None),
        "resolvedById": getattr(r, "resolvedById", None),
        "resolvedAt": r.resolvedAt.isoformat() if hasattr(r, "resolvedAt") and r.resolvedAt else None,
        "adminNotes": getattr(r, "adminNotes", None),
        "createdAt": r.createdAt.isoformat() if hasattr(r, "createdAt") else None,
        "updatedAt": r.updatedAt.isoformat() if hasattr(r, "updatedAt") else None,
    }


@require_auth
def create_error_report():
    """POST /v2/system/error-reports — submit an error report from the frontend."""
    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    report_type = (data.get("type") or "").strip()
    if report_type not in _VALID_TYPES:
        return bad_request(f"type must be one of: {', '.join(sorted(_VALID_TYPES))}")

    severity = (data.get("severity") or "").strip()
    if severity not in _VALID_SEVERITIES:
        return bad_request(f"severity must be one of: {', '.join(sorted(_VALID_SEVERITIES))}")

    message = (data.get("message") or "").strip()
    if not message:
        return bad_request("message is required")

    db = get_db_client()
    report = db.errorreport.create(data={
        "type": report_type,
        "severity": severity,
        "message": message[:2000],
        "context": Json(data),
        "currentPath": (data.get("currentPath") or "")[:500] or None,
        "userEmail": (data.get("userEmail") or "")[:255] or None,
        "userId": (data.get("userId") or "")[:255] or None,
        "appVersion": (data.get("appVersion") or "")[:100] or None,
    })

    logger.info("Error report created: %s [%s/%s] %s", report.id, report_type, severity, message[:80])
    return jsonify(ApiResponse.ok({"id": report.id}).to_dict()), 201


@require_permissions(Permissions.SYSTEM_VIEW)
def list_error_reports():
    """GET /v2/system/error-reports — paginated list with filters."""
    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}

    status = request.args.get("status")
    if status and status in _VALID_STATUSES:
        where["status"] = status

    report_type = request.args.get("type")
    if report_type and report_type in _VALID_TYPES:
        where["type"] = report_type

    severity = request.args.get("severity")
    if severity and severity in _VALID_SEVERITIES:
        where["severity"] = severity

    search = (request.args.get("search") or "").strip()
    if search:
        where["message"] = {"contains": search, "mode": "insensitive"}

    db = get_db_client()
    total = db.errorreport.count(where=where)
    reports = db.errorreport.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )

    pages = (total + limit - 1) // limit if total > 0 else 0
    return jsonify(ApiResponse.ok({
        "data": [_serialize(r) for r in reports],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": pages},
    }).to_dict()), 200


@require_permissions(Permissions.SYSTEM_VIEW)
def get_error_report(report_id: str):
    """GET /v2/system/error-reports/<id> — full report with context."""
    db = get_db_client()
    report = db.errorreport.find_unique(where={"id": report_id})
    if not report:
        return not_found("Error report not found")
    return jsonify(ApiResponse.ok(_serialize(report)).to_dict()), 200


@require_permissions(Permissions.SYSTEM_MANAGE)
def update_error_report(report_id: str):
    """PATCH /v2/system/error-reports/<id> — update status or add admin notes."""
    db = get_db_client()
    report = db.errorreport.find_unique(where={"id": report_id})
    if not report:
        return not_found("Error report not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    update_data: dict = {}

    if "status" in data:
        new_status = (data["status"] or "").strip()
        if new_status not in _VALID_STATUSES:
            return bad_request(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        update_data["status"] = new_status

        if new_status in ("RESOLVED", "DISMISSED"):
            user_id = getattr(g, "current_user", {}).get("sub")
            update_data["resolvedById"] = user_id
            update_data["resolvedAt"] = datetime.now(timezone.utc)
        elif new_status == "OPEN":
            update_data["resolvedById"] = None
            update_data["resolvedAt"] = None

    if "adminNotes" in data:
        update_data["adminNotes"] = (data["adminNotes"] or "").strip() or None

    if not update_data:
        return bad_request("No fields to update (allowed: status, adminNotes)")

    updated = db.errorreport.update(where={"id": report_id}, data=update_data)
    log_audit("error_report.update", "ErrorReport", report_id, {
        "fields": list(update_data.keys()),
    })
    return jsonify(ApiResponse.ok(_serialize(updated)).to_dict()), 200


@require_permissions(Permissions.SYSTEM_MANAGE)
def delete_error_report(report_id: str):
    """DELETE /v2/system/error-reports/<id>"""
    db = get_db_client()
    report = db.errorreport.find_unique(where={"id": report_id})
    if not report:
        return not_found("Error report not found")

    db.errorreport.delete(where={"id": report_id})
    log_audit("error_report.delete", "ErrorReport", report_id, {
        "type": report.type, "severity": report.severity,
    })
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200
