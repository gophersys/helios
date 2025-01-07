# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, request, current_app
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
firmware_versions_create_bp = Blueprint("catalog_firmware_versions_create_bp", __name__)


@firmware_versions_create_bp.route("/v1/catalog/platforms/<string:platform_id>/firmware-versions", methods=["POST"])
def create_firmware_version(platform_id):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Parse the request JSON body
        data = request.get_json()
        version = data.get("version")
        hardware_version_ids = data.get("hardwareVersionIds", [])
        socket_server_version_ids = data.get("socketServerVersionIds", [])
        socket_server_messages = data.get("socketServerMessages", [])

        if not version:
            log.error("Missing firmware version in request.")
            return jsonify({"error": "Firmware version is required."}), 400

        # Validate that the platform exists
        platform = postgres_db.platform.find_unique(where={"id": platform_id})
        if not platform:
            log.info(f"Platform with ID '{platform_id}' not found.")
            return jsonify({"error": f"Platform with ID '{platform_id}' not found."}), 404

        # Validate hardware versions
        valid_hardware_versions = postgres_db.hardwareversion.find_many(
            where={"id": {"in": hardware_version_ids}, "platformId": platform_id}
        )
        if len(valid_hardware_versions) != len(hardware_version_ids):
            log.error("One or more hardware version IDs are invalid.")
            return jsonify({"error": "One or more hardware version IDs are invalid."}), 400

        # Check if a firmware version with the same version string already exists
        existing_firmware_version = postgres_db.firmwareversion.find_first(where={"version": version})
        if existing_firmware_version:
            log.error(f"Firmware version '{version}' already exists.")
            return jsonify({"error": f"Firmware version '{version}' already exists."}), 409

        # Validate socket server versions
        valid_socket_server_versions = postgres_db.socketserverversion.find_many(
            where={"id": {"in": socket_server_version_ids}}
        )
        if len(valid_socket_server_versions) != len(socket_server_version_ids):
            log.error("One or more socket server version IDs are invalid.")
            return jsonify({"error": "One or more socket server version IDs are invalid."}), 400

        # Validate socket server messages (must exist in socket server version messages)
        valid_messages = []
        for socket_version in valid_socket_server_versions:
            valid_messages.extend(socket_version.messages)

        for msg in socket_server_messages:
            if msg not in valid_messages:
                log.error(f"Invalid socket server message: '{msg}'")
                return jsonify({"error": f"Invalid socket server message: '{msg}'"}), 400

        # Create the firmware version with the associated hardware versions and socket server versions
        new_firmware_version = postgres_db.firmwareversion.create(
            data={
                "version": version,
                "hardwareVersions": {"connect": [{"id": hw_id} for hw_id in hardware_version_ids]},
                "socketServerVersions": {"connect": [{"id": sv_id} for sv_id in socket_server_version_ids]},
                "socketServerMessages": socket_server_messages,
            }
        )

        # Format the response
        response_data = {
            "id": new_firmware_version.id,
            "version": new_firmware_version.version,
            "hardwareVersions": [{"id": hw.id, "version": hw.version} for hw in valid_hardware_versions],
            "socketServerVersions": [
                {"id": sv.id, "version": sv.version, "messages": sv.messages} for sv in valid_socket_server_versions
            ],
        }

        log.info(f"Firmware version '{version}' created for platform ID '{platform_id}'.")
        return jsonify(response_data), 201

    except Exception as e:
        log.error(f"An error occurred while creating firmware version for platform ID '{platform_id}': {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
