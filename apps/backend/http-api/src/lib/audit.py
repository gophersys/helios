"""Audit logging helper.

Usage:
    from src.lib.audit import log_audit

    log_audit("user.create", "User", user.id, {"name": user.name, "email": user.email})
"""

from database import Json
from flask import g, request

from src.services.database.prisma import get_db_client


def log_audit(
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Write an entry to the audit_logs table.

    Args:
        action:      dot-notation verb, e.g. "user.create", "component.delete"
        entity_type: model name, e.g. "User", "HardwareComponent"
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
            data["ipAddress"] = request.remote_addr

        db.auditlog.create(data=data)
    except Exception:
        # Audit logging should never break the request
        pass
