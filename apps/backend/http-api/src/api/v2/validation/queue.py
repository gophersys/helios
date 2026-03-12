"""Stub module for validation queue - required for test suite to run."""

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse


@require_permissions(Permissions.VALIDATION_VIEW)
def list_queue():
    return jsonify(ApiResponse.ok([]).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_queue_entry(entry_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def create_queue_entry():
    return jsonify(ApiResponse.ok(None).to_dict()), 201


@require_permissions(Permissions.VALIDATION_MANAGE)
def update_queue_entry(entry_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def cancel_queue_entry(entry_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def promote_queue_entry(entry_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.VALIDATION_VIEW)
def get_queue_stats():
    return jsonify(ApiResponse.ok({}).to_dict()), 200


@require_permissions(Permissions.VALIDATION_MANAGE)
def trigger_scheduler():
    return jsonify(ApiResponse.ok(None).to_dict()), 200
