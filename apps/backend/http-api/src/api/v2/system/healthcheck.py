from flask import jsonify


def healthcheck():
    """Return service health status."""
    return jsonify({
        "status": "healthy",
        "service": "http-api",
    }), 200
