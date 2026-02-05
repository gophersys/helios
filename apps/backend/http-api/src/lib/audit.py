"""Audit logging helper.

Usage:
    from src.lib.audit import log_audit

    log_audit("user.create", "User", user.id, {"name": user.name, "email": user.email})
"""

import logging

from database import Json
from flask import g, request

from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


def log_audit(
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Write an entry to the audit_logs table.

    Args:
        action:      dot-notation verb, e.g. "user.create", "component.delete"
        entity_type: model name, e.g. "User", "InventoryComponent"
        entity_id:   primary key of the affected entity (nullable for bulk ops)
        details:     freeform context — label, before/after, changed fields, etc.
    """
    try:
        db = get_db_client()
        user = getattr(g, "current_user", None)

        data: dict = {
            "action": action,
            "entityType": entity_type,
        }
        if user:
            data["userId"] = user["sub"]
        if entity_id is not None:
            data["entityId"] = entity_id
        if details is not None:
            data["details"] = Json(details)
        if request:
            # Prefer the client IP from X-Forwarded-For when behind a reverse proxy
            forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            data["ipAddress"] = forwarded or request.remote_addr

        db.auditlog.create(data=data)
    except Exception as e:
        # Audit logging should never break the request
        logger.warning("Failed to write audit log for action '%s': %s", action, e)
