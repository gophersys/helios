from flask import Flask

from .list import platforms_list_bp
from .create import platforms_create_bp
from .get import platforms_get_by_id_bp
from .delete import platforms_delete_by_id_bp

from .hw_versions.register import hardware_versions_register
from .fw_versions.register import firmware_versions_register


def platforms_register(api: Flask):
    # List Platforms: GET /v1/catalog/platforms
    api.register_blueprint(platforms_list_bp)

    # Create Platform: POST /v1/catalog/platforms
    api.register_blueprint(platforms_create_bp)

    # Get Platform by UUID: GET /v1/catalog/platforms/{platformId}
    api.register_blueprint(platforms_get_by_id_bp)

    # Delete Platform by UUID: DELETE /v1/catalog/platforms/{platformId}
    api.register_blueprint(platforms_delete_by_id_bp)

    # Sub groups
    hardware_versions_register(api)
    firmware_versions_register(api)
