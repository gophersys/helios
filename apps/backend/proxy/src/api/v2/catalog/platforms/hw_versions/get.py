# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
hardware_versions_get_by_id_bp = Blueprint("catalog_hardware_versions_get_by_id_bp", __name__)


@hardware_versions_get_by_id_bp.route(
    "/v1/catalog/platforms/<string:platformId>/hardware-versions/<string:hardware_version_id>", methods=["GET"]
)
def get_hardware_version_by_id(platformId, hardware_version_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Ensure the platform exists
        platform = postgres_db.platform.find_unique(where={"id": platformId})
        if not platform:
            log.info(f"Platform with ID '{platformId}' not found.")
            return jsonify({"error": f"Platform with ID '{platformId}' not found."}), 404

        # Query the hardware version by UUID and check if it belongs to the platform
        hardware_version = postgres_db.hardwareversion.find_first(
            where={"id": hardware_version_id, "platformId": platformId},
            include={"platform": True, "hosts": True, "firmwareVersions": True},  # Include related data
        )

        # Check if the hardware version exists
        if not hardware_version:
            log.info(f"Hardware version with ID '{hardware_version_id}' not found for platform ID '{platformId}'.")
            return (
                jsonify(
                    {
                        "error": f"Hardware version with ID '{hardware_version_id}' not found for platform ID '{platformId}'."
                    }
                ),
                404,
            )

        # Format the response
        response_data = {
            "id": hardware_version.id,
            "version": hardware_version.version,
            "platform": {"id": hardware_version.platform.id, "name": hardware_version.platform.name},
            "hosts": [{"id": host.id, "name": host.name} for host in hardware_version.hosts],
            "firmwareVersions": [
                {"id": fw_version.id, "version": fw_version.version}
                for fw_version in hardware_version.firmwareVersions
            ],
        }

        log.info(f"Returning hardware version with ID: {hardware_version_id} for platform ID: {platformId}.")
        return jsonify(response_data), 200

    except Exception as e:
        log.error(
            f"An error occurred while retrieving hardware version with ID '{hardware_version_id}' for platform ID '{platformId}': {str(e)}"
        )
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
