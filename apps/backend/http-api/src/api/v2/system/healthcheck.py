from flask import jsonify

from src.lib.types import ApiResponse


def healthcheck():
    """GET /v2/healthcheck — service health status."""
    return jsonify(ApiResponse.ok({
        "status": "healthy",
        "service": "http-api",
    }).to_dict()), 200
