# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, request, current_app
from prisma import Prisma
import asyncio

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
platforms_create_bp = Blueprint("catalog_platforms_post_bp", __name__)


@platforms_create_bp.route("/v1/catalog/platforms", methods=["POST"])
def handler():
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Parse the request JSON body
        request_data = request.get_json()
        platform_name = request_data.get("name")

        if not platform_name:
            log.error("Platform name is missing in the request.")
            return jsonify({"error": "Platform name is required."}), 400

        # Check if a platform with the same name already exists
        existing_platform = postgres_db.platform.find_first(where={"name": platform_name})

        if existing_platform:
            log.info(f"Platform with name '{platform_name}' already exists.")
            return jsonify({"error": f"Platform with name '{platform_name}' already exists."}), 409

        # Create the new platform if no duplicate exists
        new_platform = postgres_db.platform.create(data={"name": platform_name})

        log.info(f"Platform '{platform_name}' created with ID: {new_platform.id}.")
        return jsonify({"id": new_platform.id, "name": new_platform.name}), 201

    except Exception as e:
        log.error(f"An error occurred while creating the platform: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
