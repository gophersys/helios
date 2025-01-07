from flask import Flask

from .list import firmware_versions_list_bp
from .create import firmware_versions_create_bp
from .update import firmware_versions_update_bp
from .get import firmware_versions_get_by_id_bp
from .delete import firmware_versions_delete_by_id_bp


def firmware_versions_register(api: Flask):
    # List Firmware Versions for a Platform: GET /v1/catalog/platforms/{platformId}/firmware-versions
    api.register_blueprint(firmware_versions_list_bp)

    # Create Firmware Version: POST /v1/catalog/platforms/{platformId}/firmware-versions
    api.register_blueprint(firmware_versions_create_bp)

    # Update Firmware Version: PATCH /v1/catalog/platforms/{platformId}/firmware-versions
    api.register_blueprint(firmware_versions_update_bp)

    # Get Firmware Version: GET /v1/catalog/platforms/{platformId}/firmware-versions/{firmwareVersionId}
    api.register_blueprint(firmware_versions_get_by_id_bp)

    # Delete Firmware Version by UUID: DELETE /v1/catalog/platforms/{platformId}/firmware-versions/{firmwareVersionId}
    api.register_blueprint(firmware_versions_delete_by_id_bp)
