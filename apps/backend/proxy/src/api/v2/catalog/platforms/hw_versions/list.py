# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
hardware_versions_list_bp = Blueprint("catalog_hardware_versions_list_bp", __name__)


@hardware_versions_list_bp.route("/v1/catalog/platforms/<string:platform_id>/hardware-versions", methods=["GET"])
def handler(platform_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Query platform to ensure it exists
        platform = postgres_db.platform.find_unique(where={"id": platform_id})

        if not platform:
            log.info(f"Platform with ID '{platform_id}' not found.")
            return jsonify({"error": f"Platform with ID '{platform_id}' not found."}), 404

        # Query all hardware versions related to the platform
        hardware_versions = postgres_db.hardwareversion.find_many(where={"platformId": platform_id})

        # Format the response
        response_data = [{"id": hw_version.id, "version": hw_version.version} for hw_version in hardware_versions]

        log.info(f"Returning {len(hardware_versions)} hardware versions for platform ID '{platform_id}'.")
        return jsonify({"hardwareVersions": response_data}), 200

    except Exception as e:
        log.error(f"An error occurred while retrieving hardware versions for platform ID '{platform_id}': {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
