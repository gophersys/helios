# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
platforms_get_by_id_bp = Blueprint("catalog_platforms_get_by_id_bp", __name__)


@platforms_get_by_id_bp.route("/v1/catalog/platforms/<string:platform_id>", methods=["GET"])
def get_platform_with_details(platform_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Query platform by UUID with all related data
        platform = postgres_db.platform.find_unique(
            where={"id": platform_id},
            include={"hardwareVersions": {"include": {"firmwareVersions": True, "hosts": True}}},
        )

        # Check if the platform exists
        if not platform:
            log.info(f"Platform with ID '{platform_id}' not found.")
            return jsonify({"error": f"Platform with ID '{platform_id}' not found."}), 404

        # Map platform data along with nested hardware versions, firmware versions, and hosts
        response_data = {
            "id": platform.id,
            "name": platform.name,
            "hardwareVersions": [
                {
                    "id": hw_version.id,
                    "version": hw_version.version,
                    "firmwareVersions": [
                        {"id": fw_version.id, "version": fw_version.version}
                        for fw_version in hw_version.firmwareVersions
                    ],
                    "hosts": [{"id": host.id, "name": host.name} for host in hw_version.hosts],
                }
                for hw_version in platform.hardwareVersions
            ],
        }

        log.info(f"Returning platform with details for ID: {platform_id}.")
        return jsonify(response_data), 200

    except Exception as e:
        log.error(f"An error occurred while retrieving platform with ID '{platform_id}': {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
