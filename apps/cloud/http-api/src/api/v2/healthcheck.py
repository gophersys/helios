from flask import Blueprint

v2_healthcheck_bp = Blueprint("v2_healthcheck", __name__)


@v2_healthcheck_bp.route("/v2/healthcheck", methods=["GET"])
def health_check():
    """
    This route just returns OK. Yes we're alive.
    """
    return "", 200
