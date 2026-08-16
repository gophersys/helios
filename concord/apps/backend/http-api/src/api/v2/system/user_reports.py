"""User-facing bug reports — list own error reports with resolution info.

Users see their own submitted bug reports with status and "fixed in version X"
when linked to a release via resolvedInReleaseId.
"""

import logging

from flask import g, jsonify, request

from src.lib.decorators import require_auth
from src.lib.errors import bad_request
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def _serialize_user_report(r) -> dict:
    result = {
        "id": r.id,
        "status": r.status,
        "type": r.type,
        "severity": r.severity,
        "message": r.message,
        "currentPath": getattr(r, "currentPath", None),
        "appVersion": getattr(r, "appVersion", None),
        "adminNotes": getattr(r, "adminNotes", None),
        "resolvedAt": r.resolvedAt.isoformat() if hasattr(r, "resolvedAt") and r.resolvedAt else None,
        "resolvedInReleaseId": getattr(r, "resolvedInReleaseId", None),
        "resolvedInVersion": None,
        "createdAt": r.createdAt.isoformat() if hasattr(r, "createdAt") else None,
        "updatedAt": r.updatedAt.isoformat() if hasattr(r, "updatedAt") else None,
    }

    # Include "fixed in version X" when linked to a release
    if hasattr(r, "resolvedInRelease") and r.resolvedInRelease:
        result["resolvedInVersion"] = r.resolvedInRelease.version

    return result


@require_auth
def list_my_error_reports():
    """GET /v2/my/error-reports — list error reports submitted by current user."""
    user_id = getattr(g, "current_user", {}).get("sub")
    if not user_id:
        return bad_request("User identity not available")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where = {"userId": user_id}

    db = get_db_client()
    total = db.errorreport.count(where=where)
    reports = db.errorreport.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
        include={"resolvedInRelease": True},
    )

    pages = (total + limit - 1) // limit if total > 0 else 0
    return jsonify(ApiResponse.ok({
        "data": [_serialize_user_report(r) for r in reports],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": pages},
    }).to_dict()), 200
