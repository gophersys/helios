# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma
import asyncio

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
platforms_list_bp = Blueprint("catalog_platforms_get_bp", __name__)


@platforms_list_bp.route("/v1/catalog/platforms", methods=["GET"])
def handler():
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Run the async function using the event loop
        platforms = postgres_db.platform.find_many()

        # If no platforms found
        if not platforms:
            log.info("No platforms found.")
            return jsonify({"message": "No platforms available."}), 200

        # Map platforms to response format
        response_data = [{"id": platform.id, "name": platform.name} for platform in platforms]

        log.info(f"Returning {len(platforms)} platforms.")
        return jsonify({"platforms": response_data}), 200

    except Exception as e:
        log.error(f"An error occurred while retrieving platforms: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
