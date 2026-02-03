from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions


@require_permissions(Permissions.ADMIN_PERMISSION_SETS_VIEW)
def list_permissions():
    """List all available permission strings."""
    return jsonify({"data": Permissions.all()}), 200
