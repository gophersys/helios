from flask import Blueprint, Response, jsonify, current_app
from src.server import ProxyEnvConfig
from corekinect.utils import Logger

health_bp = Blueprint("v2_healthcheck", __name__)


@health_bp.route("/v1/health/proxy", methods=["GET"])
def health_check():
    """
    This route just returns OK. Yes we're alive.
    """
    logger: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)

    logger.info(f"{env_config}")

    return jsonify({"message": "OK Papi"}), 200
