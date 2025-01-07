# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
platforms_delete_by_id_bp = Blueprint("catalog_platforms_delete_by_id_bp", __name__)


@platforms_delete_by_id_bp.route("/v1/catalog/platforms/<string:platform_id>", methods=["DELETE"])
def handler(platform_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Query the platform by UUID to check if it exists
        platform = postgres_db.platform.find_unique(where={"id": platform_id})

        if not platform:
            log.info(f"Platform with ID '{platform_id}' not found.")
            return jsonify({"error": f"Platform with ID '{platform_id}' not found."}), 404

        # Delete the platform
        postgres_db.platform.delete(where={"id": platform_id})

        log.info(f"Platform with ID '{platform_id}' deleted successfully.")
        return jsonify({"message": f"Platform with ID '{platform_id}' deleted successfully."}), 200

    except Exception as e:
        log.error(f"An error occurred while deleting platform with ID '{platform_id}': {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
