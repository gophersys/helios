"""Stub module for manifest - required for test suite to run."""

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse


@require_permissions(Permissions.VALIDATION_VIEW)
def get_run_manifest(run_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200
