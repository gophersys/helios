# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
firmware_versions_delete_by_id_bp = Blueprint("catalog_firmware_versions_delete_bp", __name__)


@firmware_versions_delete_by_id_bp.route(
    "/v1/catalog/platforms/<string:platform_id>/firmware-versions/<string:firmware_version_id>", methods=["DELETE"]
)
def handler(platform_id, firmware_version_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Validate that the platform exists
        platform = postgres_db.platform.find_unique(where={"id": platform_id})
        if not platform:
            log.info(f"Platform with ID '{platform_id}' not found.")
            return jsonify({"error": f"Platform with ID '{platform_id}' not found."}), 404

        # Query the firmware version by UUID and ensure it belongs to the platform
        firmware_version = postgres_db.firmwareversion.find_first(
            where={"id": firmware_version_id, "hardwareVersions": {"some": {"platformId": platform_id}}}
        )
        if not firmware_version:
            log.info(f"Firmware version with ID '{firmware_version_id}' not found for platform ID '{platform_id}'.")
            return (
                jsonify(
                    {
                        "error": f"Firmware version with ID '{firmware_version_id}' not found for platform ID '{platform_id}'."
                    }
                ),
                404,
            )

        # Delete the firmware version
        postgres_db.firmwareversion.delete(where={"id": firmware_version_id})

        log.info(f"Firmware version with ID '{firmware_version_id}' deleted for platform ID '{platform_id}'.")
        return (
            jsonify(
                {
                    "message": f"Firmware version with ID '{firmware_version_id}' deleted for platform ID '{platform_id}'."
                }
            ),
            200,
        )

    except Exception as e:
        log.error(
            f"An error occurred while deleting firmware version with ID '{firmware_version_id}' for platform ID '{platform_id}': {str(e)}"
        )
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
