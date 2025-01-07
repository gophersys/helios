# Standard includes

# 3rd party includes
from flask import Blueprint, jsonify, current_app, request
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
firmware_versions_update_bp = Blueprint("firmware_versions_update_bp", __name__)


@firmware_versions_update_bp.route(
    "/v1/catalog/platforms/<string:platform_id>/firmware-versions/<string:firmwareVersionId>", methods=["PATCH"]
)
def handler(platform_id, firmwareVersionId):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Parse the request JSON body
        data = request.get_json()
        hardware_version_ids = data.get("hardwareVersionIds", [])
        socket_server_version_ids = data.get("socketServerVersionIds", [])
        socket_server_messages = data.get("socketServerMessages", [])

        # Validate firmware version
        firmware_version = postgres_db.firmwareversion.find_first(where={"id": firmwareVersionId})
        if not firmware_version:
            log.error(f"Firmware version with ID '{firmwareVersionId}' not found.")
            return jsonify({"error": f"Firmware version with ID '{firmwareVersionId}' not found."}), 404

        # Validate hardware versions
        valid_hardware_versions = postgres_db.hardwareversion.find_many(
            where={"id": {"in": hardware_version_ids}, "platformId": platform_id}
        )
        if len(valid_hardware_versions) != len(hardware_version_ids):
            log.error("One or more hardware version IDs are invalid.")
            return jsonify({"error": "One or more hardware version IDs are invalid."}), 400

        # Validate socket server versions
        valid_socket_server_versions = postgres_db.socketserverversion.find_many(
            where={"id": {"in": socket_server_version_ids}}
        )
        if len(valid_socket_server_versions) != len(socket_server_version_ids):
            log.error("One or more socket server version IDs are invalid.")
            return jsonify({"error": "One or more socket server version IDs are invalid."}), 400

        # Validate socket server messages
        valid_messages = []
        for socket_version in valid_socket_server_versions:
            valid_messages.extend(socket_version.messages)

        for msg in socket_server_messages:
            if msg not in valid_messages:
                log.error(f"Invalid socket server message: '{msg}'")
                return jsonify({"error": f"Invalid socket server message: '{msg}'"}), 400

        # Update the firmware version with new associations
        updated_firmware_version = postgres_db.firmwareversion.update(
            where={"id": firmwareVersionId},
            data={
                "hardwareVersions": {"connect": [{"id": hw_id} for hw_id in hardware_version_ids]},
                "socketServerVersions": {"connect": [{"id": sv_id} for sv_id in socket_server_version_ids]},
                "socketServerMessages": socket_server_messages,
            },
        )

        log.info(f"Firmware version '{firmwareVersionId}' updated.")
        return jsonify({"message": "Firmware version updated successfully."}), 200

    except Exception as e:
        log.error(f"An error occurred while updating firmware version '{firmwareVersionId}': {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
