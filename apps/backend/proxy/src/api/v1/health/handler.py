from flask import Blueprint, Response, jsonify

health_bp = Blueprint("healthcheck", __name__)


@health_bp.route("/v1/health/proxy", methods=["GET"])
def health_check():
    """
    This route just returns OK. Yes we're alive.
    """
    return jsonify({"message": "OK"}), 200
