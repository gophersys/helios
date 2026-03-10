"""Admin endpoints for data retention management.

Provides:
- Manual cleanup trigger for old validation runs
- Storage usage statistics
"""

import logging

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import bad_request
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.retention import (
    DEFAULT_RETENTION_DAYS,
    cleanup_old_validation_runs,
    get_storage_usage,
)

logger = logging.getLogger(__name__)


@require_permissions(Permissions.ADMIN_SYSTEM_MANAGE)
def cleanup_validation_runs():
    """POST /v2/system/retention/validation/cleanup — Manually trigger cleanup.

    Query params:
        retention_days: Number of days to retain (default: 60)
        dry_run: If true, only report what would be deleted (default: false)
    """
    retention_days = request.args.get("retention_days", DEFAULT_RETENTION_DAYS, type=int)
    if retention_days < 1:
        return bad_request("retention_days must be at least 1")

    dry_run = request.args.get("dry_run", "false").lower() == "true"

    if dry_run:
        # TODO: Implement dry-run mode that returns what would be deleted
        return jsonify(ApiResponse.ok({
            "dryRun": True,
            "message": "Dry run not yet implemented"
        }).to_dict()), 200

    try:
        result = cleanup_old_validation_runs(retention_days)
        return jsonify(ApiResponse.ok(result).to_dict()), 200
    except Exception as e:
        logger.error(f"Retention cleanup failed: {e}")
        return jsonify(ApiResponse.error(f"Cleanup failed: {str(e)}").to_dict()), 500


@require_permissions(Permissions.ADMIN_SYSTEM_VIEW)
def get_validation_storage_usage():
    """GET /v2/system/retention/validation/usage — Get storage usage stats."""
    try:
        usage = get_storage_usage()
        return jsonify(ApiResponse.ok(usage).to_dict()), 200
    except Exception as e:
        logger.error(f"Failed to get storage usage: {e}")
        return jsonify(ApiResponse.error(f"Failed to get usage: {str(e)}").to_dict()), 500
