import logging
from collections import defaultdict

from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.permissions import PERMISSION_REGISTRY, Permissions
from src.lib.types import ApiResponse

logger = logging.getLogger(__name__)


@require_permissions(Permissions.USERS_VIEW)
def list_permissions():
    """List all available permissions with registry metadata grouped by module."""
    # Build module-grouped registry for the UI
    grouped = defaultdict(list)
    for perm_key, meta in PERMISSION_REGISTRY.items():
        grouped[meta["module"]].append({
            "permission": perm_key,
            "label": meta["label"],
            "description": meta["description"],
        })

    return jsonify(ApiResponse.ok({
        "permissions": sorted(Permissions.all()),
        "registry": dict(grouped),
    }).to_dict()), 200
