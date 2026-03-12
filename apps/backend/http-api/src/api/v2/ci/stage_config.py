"""Stub module for stage config - required for test suite to run."""

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse


@require_permissions(Permissions.BUILDS_VIEW)
def list_stage_configs():
    return jsonify(ApiResponse.ok([]).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_stage_config(product_id: str, stage_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def create_stage_config(product_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 201


@require_permissions(Permissions.BUILDS_MANAGE)
def update_stage_config(product_id: str, stage_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_stage_config(product_id: str, stage_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def initialize_stages(product_id: str):
    return jsonify(ApiResponse.ok(None).to_dict()), 200
