# Standard includes
from io import BytesIO
import zipfile
import os

# 3rd party includes
from flask import Blueprint, jsonify, current_app, send_file
from prisma import Prisma

# Corekinect includes
from corekinect.utils import Logger

# App includes
from src.server import ProxyEnvConfig

# Create blueprint
firmware_versions_get_by_id_bp = Blueprint("catalog_firmware_versions_get_by_id_bp", __name__)


@firmware_versions_get_by_id_bp.route(
    "/v1/catalog/platforms/<string:platformId>/firmware-versions/<string:firmwareVersionId>", methods=["GET"]
)
def handler(platformId, firmwareVersionId):
    # Get global server objects
    log: Logger = current_app.config.get("logger", None)
    env_config: ProxyEnvConfig = current_app.config.get("env_config", None)
    postgres_db: Prisma = current_app.config.get("postgres_db", None)

    try:
        # Validate that the platform exists
        platform = postgres_db.platform.find_unique(where={"id": platformId})
        if not platform:
            log.info(f"Platform with ID '{platformId}' not found.")
            return jsonify({"error": f"Platform with ID '{platformId}' not found."}), 404

        # Query the firmware version by UUID and ensure it belongs to the platform
        firmware_version = postgres_db.firmwareversion.find_first(
            where={"id": firmwareVersionId, "hardwareVersions": {"some": {"platformId": platformId}}}
        )
        if not firmware_version:
            log.info(f"Firmware version with ID '{firmwareVersionId}' not found for platform ID '{platformId}'.")
            return (
                jsonify(
                    {
                        "error": f"Firmware version with ID '{firmwareVersionId}' not found for platform ID '{platformId}'."
                    }
                ),
                404,
            )

        # Assuming the firmware assets are stored in a specific directory structure
        firmware_assets_dir = f"/path/to/firmware_assets/{firmwareVersionId}/"  # Directory where assets are stored
        if not os.path.exists(firmware_assets_dir):
            log.error(f"Assets for firmware version ID '{firmwareVersionId}' not found.")
            return jsonify({"error": f"Assets for firmware version ID '{firmwareVersionId}' not found."}), 404

        # Create a ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add firmware files to the zip
            for root, dirs, files in os.walk(firmware_assets_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, firmware_assets_dir)  # Preserve directory structure
                    zip_file.write(file_path, arcname)

            # Add metadata file to the zip
            metadata = {
                "id": firmware_version.id,
                "version": firmware_version.version,
                "platform": {"id": platform.id, "name": platform.name},
                "hardwareVersions": [{"id": hw.id, "version": hw.version} for hw in firmware_version.hardwareVersions],
                "socketServerVersions": [
                    {"id": sv.id, "version": sv.version, "messages": sv.messages}
                    for sv in firmware_version.socketServerVersions
                ],
                "socketServerMessages": firmware_version.socketServerMessages,
            }

            # Convert metadata to JSON and add it as a file in the zip
            zip_file.writestr("metadata.json", jsonify(metadata).get_data(as_text=True))

        zip_buffer.seek(0)

        # Send the ZIP file as a response
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"{firmware_version.version}_firmware.zip",
            mimetype="application/zip",
        )

    except Exception as e:
        log.error(
            f"An error occurred while retrieving firmware version '{firmwareVersionId}' for platform '{platformId}': {str(e)}"
        )
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
