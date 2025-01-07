from flask import Flask

from .list import hardware_versions_list_bp
from .create import hardware_versions_create_bp
from .get import hardware_versions_get_by_id_bp
from .delete import hardware_versions_delete_by_id_bp


def hardware_versions_register(api: Flask):
    # List Hardware Versions for a Platform: GET /v1/catalog/platforms/{platformId}/hardware-versions
    api.register_blueprint(hardware_versions_list_bp)

    # Create Hardware Version for a Platform: POST /v1/catalog/platforms/{platformId}/hardware-versions
    api.register_blueprint(hardware_versions_create_bp)

    # Get Hardware Version by UUID: GET /v1/catalog/platforms/{platformId}/hardware-versions/{hardwareVersionId}
    api.register_blueprint(hardware_versions_get_by_id_bp)

    # Delete Hardware Version by UUID: DELETE /v1/catalog/platforms/{platformId}/hardware-versions/{hardwareVersionId}
    api.register_blueprint(hardware_versions_delete_by_id_bp)
