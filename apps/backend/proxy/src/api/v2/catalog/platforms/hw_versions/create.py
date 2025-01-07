# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, request, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
hardware_versions_create_bp = Blueprint("catalog_hardware_versions_create_bp", __name__)


@hardware_versions_create_bp.route("/v1/catalog/platforms/<string:platform_id>/hardware-versions", methods=["POST"])
def handler(platform_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Parse the request JSON body
        data = request.get_json()
        version = data.get("version")
        host_ids = data.get("hostIds", [])

        if not version:
            log.error("Missing hardware version in request.")
            return jsonify({"error": "Hardware version is required."}), 400

        # Check if the platform exists
        platform = postgres_db.platform.find_unique(where={"id": platform_id})
        if not platform:
            log.info(f"Platform with ID '{platform_id}' not found.")
            return jsonify({"error": f"Platform with ID '{platform_id}' not found."}), 404

        # Check if the provided host IDs exist
        valid_hosts = postgres_db.host.find_many(where={"id": {"in": host_ids}})
        if len(valid_hosts) != len(host_ids):
            log.error("One or more host IDs are invalid.")
            return jsonify({"error": "One or more host IDs are invalid."}), 400

        # Create the hardware version with linked hosts
        new_hardware_version = postgres_db.hardwareversion.create(
            data={
                "version": version,
                "platform": {"connect": {"id": platform_id}},
                "hosts": {"connect": [{"id": host_id} for host_id in host_ids]},
            }
        )

        # Format the response
        response_data = {
            "id": new_hardware_version.id,
            "version": new_hardware_version.version,
            "platformId": platform_id,
            "hosts": [{"id": host.id, "name": host.name} for host in valid_hosts],
        }

        log.info(f"Hardware version '{version}' created for platform ID '{platform_id}'.")
        return jsonify(response_data), 201

    except Exception as e:
        log.error(f"An error occurred while creating hardware version for platform ID '{platform_id}': {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
