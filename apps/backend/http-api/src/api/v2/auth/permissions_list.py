from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_VIEW)
def list_permissions():
    """List all available permission strings."""
    return jsonify(ApiResponse.ok(Permissions.all()).to_dict()), 200
