# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
hardware_versions_delete_by_id_bp = Blueprint("catalog_hardware_versions_delete_by_id_bp", __name__)


@hardware_versions_delete_by_id_bp.route(
    "/v1/catalog/platforms/<string:platformId>/hardware-versions/<string:hardware_version_id>", methods=["DELETE"]
)
def delete_hardware_version_by_id(platformId, hardware_version_id):
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
            where={"id": hardware_version_id, "platformId": platformId}
        )
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

        # Delete the hardware version
        postgres_db.hardwareversion.delete(where={"id": hardware_version_id})

        log.info(f"Hardware version with ID '{hardware_version_id}' deleted for platform ID '{platformId}'.")
        return (
            jsonify(
                {
                    "message": f"Hardware version with ID '{hardware_version_id}' deleted for platform ID '{platformId}'."
                }
            ),
            200,
        )

    except Exception as e:
        log.error(
            f"An error occurred while deleting hardware version with ID '{hardware_version_id}' for platform ID '{platformId}': {str(e)}"
        )
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
