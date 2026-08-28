"""Route registration for /v2/products endpoints."""

from flask import Blueprint

from .access import (
    grant_product_access, list_product_access,
    revoke_product_access, update_product_access,
)
from .board_discovery import (
    check_repo, discover_board_detail, discover_boards,
    list_board_branches, list_repo_branches,
)
from .products import (
    archive_product, batch_products_action, create_product, delete_product,
    export_product, get_product, get_product_by_slug, list_products,
    unarchive_product, update_product, sync_product_revisions,
)
from .boards import create_board, delete_board, get_board, list_boards, update_board
from .board_revisions import (
    get_board_revision, create_board_revision, create_target,
    delete_board_revision, delete_modem_firmware, delete_target,
    list_modem_firmwares, update_board_revision, update_target,
    upload_modem_firmware,
)
from .firmware_builds import (
    list_firmware_sets, get_firmware_set, create_firmware_set,
    update_firmware_set, delete_firmware_set, upload_firmware_build,
    download_firmware_build,
)
from .test_packages import (
    upload_test_package, list_test_packages, get_test_package,
    download_test_package, get_latest_test_package, delete_test_package,
    release_test_package,
)
from .manufacturing_config import (
    get_manufacturing_config, create_manufacturing_config,
    update_manufacturing_config, delete_manufacturing_config,
)
from ..builds.stage_config import (
    list_stage_configs, get_stage_config, create_stage_config,
    update_stage_config, delete_stage_config, initialize_stages,
    get_stage_build_matrix, update_stage_build_matrix, reset_stage_build_matrix,
)
from ..builds.stage_trigger import trigger_stage_run
from ..builds.recipes import (
    get_recipe, update_recipe, validate_recipe,
    list_recipe_versions, get_recipe_version, get_recipe_version_by_id,
    save_recipe_version, publish_recipe, diff_recipe_versions, test_recipe_build,
)
from ..builds.manifest import get_run_manifest
from ..assets.asset_sets import (
    list_asset_sets, create_asset_set, create_external_asset_set,
)
from ..assets.zip_upload import (
    validate_asset_zip, upload_asset_set_zip, analyze_asset_files, upload_asset_files,
)


def register_product_routes(api: Blueprint):
    # Board Discovery
    api.add_url_rule("/products/boards/branches",                                                  endpoint="list_board_branches",    view_func=list_board_branches,    methods=["GET"])
    api.add_url_rule("/products/boards/discover",                                                  endpoint="discover_boards",        view_func=discover_boards,        methods=["GET"])
    api.add_url_rule("/products/boards/discover/<board_name>",                                     endpoint="discover_board_detail",  view_func=discover_board_detail,  methods=["GET"])
    api.add_url_rule("/products/repos/check",                                                      endpoint="check_repo",             view_func=check_repo,             methods=["GET"])
    api.add_url_rule("/products/repos/branches",                                                  endpoint="list_repo_branches",     view_func=list_repo_branches,     methods=["GET"])

    # Products CRUD
    api.add_url_rule("/products",                                                                   view_func=list_products,          methods=["GET"])
    api.add_url_rule("/products",                                                                   view_func=create_product,         methods=["POST"])
    api.add_url_rule("/products/by-slug/<slug>",                                                    view_func=get_product_by_slug,    methods=["GET"])
    api.add_url_rule("/products/<product_id>",                                                      view_func=get_product,            methods=["GET"])
    api.add_url_rule("/products/<product_id>",                                                      view_func=update_product,         methods=["PUT"])
    api.add_url_rule("/products/<product_id>",                                                      view_func=delete_product,         methods=["DELETE"])
    api.add_url_rule("/products/<product_id>/sync-revisions",                                       view_func=sync_product_revisions, methods=["POST"])
    api.add_url_rule("/products/<product_id>/archive",          endpoint="archive_product",       view_func=archive_product,        methods=["POST"])
    api.add_url_rule("/products/<product_id>/unarchive",        endpoint="unarchive_product",     view_func=unarchive_product,      methods=["POST"])
    api.add_url_rule("/products/<product_id>/export",           endpoint="export_product",        view_func=export_product,         methods=["POST"])
    api.add_url_rule("/products/batch",                           endpoint="batch_products",        view_func=batch_products_action,  methods=["POST"])

    # Boards
    api.add_url_rule("/products/<product_id>/boards",                                               view_func=list_boards,            methods=["GET"])
    api.add_url_rule("/products/<product_id>/boards",                                               view_func=create_board,           methods=["POST"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=get_board,              methods=["GET"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=update_board,           methods=["PUT"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>",                                    view_func=delete_board,           methods=["DELETE"])

    # Board Revisions
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions",                          view_func=create_board_revision,  methods=["POST"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=get_board_revision,     methods=["GET"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=update_board_revision,  methods=["PUT"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>",            view_func=delete_board_revision,  methods=["DELETE"])

    # Modem Firmware
    api.add_url_rule("/products/<product_id>/revisions/<revision_id>/modem-firmware",          view_func=list_modem_firmwares,   methods=["GET"])
    api.add_url_rule("/products/<product_id>/revisions/<revision_id>/modem-firmware",          view_func=upload_modem_firmware,  methods=["POST"])
    api.add_url_rule("/products/<product_id>/revisions/<revision_id>/modem-firmware/<fw_id>",  view_func=delete_modem_firmware,  methods=["DELETE"])

    # Targets
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/targets",              view_func=create_target,  methods=["POST"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/targets/<target_id>",  view_func=update_target,  methods=["PUT"])
    api.add_url_rule("/products/<product_id>/boards/<board_id>/revisions/<revision_id>/targets/<target_id>",  view_func=delete_target,  methods=["DELETE"])

    # Firmware Sets
    api.add_url_rule("/products/<product_id>/firmware",                                             view_func=list_firmware_sets,      methods=["GET"])
    api.add_url_rule("/products/<product_id>/firmware",                                             view_func=create_firmware_set,     methods=["POST"])
    api.add_url_rule("/products/<product_id>/firmware/<set_id>",                                    view_func=get_firmware_set,        methods=["GET"])
    api.add_url_rule("/products/<product_id>/firmware/<set_id>",                                    view_func=update_firmware_set,     methods=["PUT"])
    api.add_url_rule("/products/<product_id>/firmware/<set_id>",                                    view_func=delete_firmware_set,     methods=["DELETE"])
    api.add_url_rule("/products/<product_id>/firmware/<set_id>/builds",                             view_func=upload_firmware_build,   methods=["POST"])
    api.add_url_rule("/firmware/builds/<build_id>/download",                                        view_func=download_firmware_build, methods=["GET"])

    # Test Packages
    api.add_url_rule("/products/<product_id>/test-packages",                                        endpoint="upload_test_package",      view_func=upload_test_package,       methods=["POST"])
    api.add_url_rule("/products/<product_id>/test-packages",                                        endpoint="list_test_packages",       view_func=list_test_packages,        methods=["GET"])
    api.add_url_rule("/products/<product_id>/test-packages/latest",                                 endpoint="get_latest_test_package",  view_func=get_latest_test_package,   methods=["GET"])
    api.add_url_rule("/products/<product_id>/test-packages/<version>/download",                     endpoint="download_test_package",    view_func=download_test_package,     methods=["GET"])
    api.add_url_rule("/products/<product_id>/test-packages/<package_id>/release",                  endpoint="release_test_package",     view_func=release_test_package,      methods=["POST"])
    api.add_url_rule("/products/<product_id>/test-packages/<package_id>",                          endpoint="get_test_package",         view_func=get_test_package,          methods=["GET"])
    api.add_url_rule("/products/<product_id>/test-packages/<package_id>",                          endpoint="delete_test_package",      view_func=delete_test_package,       methods=["DELETE"])

    # Stage Configs
    api.add_url_rule("/products/<product_id>/stages",                                            endpoint="list_stage_configs",       view_func=list_stage_configs,    methods=["GET"])
    api.add_url_rule("/products/<product_id>/stages",                                            endpoint="create_stage_config",      view_func=create_stage_config,   methods=["POST"])
    api.add_url_rule("/products/<product_id>/stages/initialize",                                 endpoint="initialize_stages",        view_func=initialize_stages,     methods=["POST"])
    api.add_url_rule("/products/<product_id>/stages/<stage>",                                    endpoint="get_stage_config",         view_func=get_stage_config,      methods=["GET"])
    api.add_url_rule("/products/<product_id>/stages/<stage>",                                    endpoint="update_stage_config",      view_func=update_stage_config,   methods=["PUT"])
    api.add_url_rule("/products/<product_id>/stages/<stage>",                                    endpoint="delete_stage_config",      view_func=delete_stage_config,   methods=["DELETE"])
    api.add_url_rule("/products/<product_id>/stages/<stage>/trigger-run",                       endpoint="trigger_stage_run",        view_func=trigger_stage_run,     methods=["POST"])

    # Stage Build Matrix
    api.add_url_rule("/products/<product_id>/stages/<stage>/build-matrix",                       endpoint="get_stage_build_matrix",   view_func=get_stage_build_matrix,    methods=["GET"])
    api.add_url_rule("/products/<product_id>/stages/<stage>/build-matrix",                       endpoint="update_stage_build_matrix", view_func=update_stage_build_matrix, methods=["PUT"])
    api.add_url_rule("/products/<product_id>/stages/<stage>/build-matrix/reset",                 endpoint="reset_stage_build_matrix", view_func=reset_stage_build_matrix,  methods=["POST"])

    # Asset Sets (product-scoped)
    api.add_url_rule("/products/<product_id>/asset-sets",                                        endpoint="list_asset_sets",          view_func=list_asset_sets,           methods=["GET"])
    api.add_url_rule("/products/<product_id>/asset-sets",                                        endpoint="create_asset_set",         view_func=create_asset_set,          methods=["POST"])
    api.add_url_rule("/products/<product_id>/asset-sets/external",                               endpoint="create_external_asset_set", view_func=create_external_asset_set, methods=["POST"])
    api.add_url_rule("/products/<product_id>/asset-sets/validate-zip",                           endpoint="validate_asset_zip",       view_func=validate_asset_zip,        methods=["POST"])
    api.add_url_rule("/products/<product_id>/asset-sets/upload-zip",                             endpoint="upload_asset_set_zip",     view_func=upload_asset_set_zip,      methods=["POST"])
    api.add_url_rule("/products/<product_id>/asset-sets/analyze-files",                          endpoint="analyze_asset_files",      view_func=analyze_asset_files,       methods=["POST"])
    api.add_url_rule("/products/<product_id>/asset-sets/upload-files",                           endpoint="upload_asset_files",       view_func=upload_asset_files,        methods=["POST"])

    # Recipe
    api.add_url_rule("/products/<product_id>/recipe",                                             endpoint="get_recipe",               view_func=get_recipe,            methods=["GET"])
    api.add_url_rule("/products/<product_id>/recipe",                                             endpoint="update_recipe",            view_func=update_recipe,         methods=["PUT"])
    api.add_url_rule("/products/<product_id>/recipe/validate",                                    endpoint="validate_recipe",          view_func=validate_recipe,       methods=["POST"])
    api.add_url_rule("/products/<product_id>/recipe/test-build",                                  endpoint="test_recipe_build",        view_func=test_recipe_build,     methods=["POST"])
    api.add_url_rule("/products/<product_id>/recipe/versions",                                    endpoint="list_recipe_versions",     view_func=list_recipe_versions,  methods=["GET"])
    api.add_url_rule("/products/<product_id>/recipe/versions/<int:version_num>",                   endpoint="get_recipe_version",       view_func=get_recipe_version,    methods=["GET"])
    api.add_url_rule("/products/<product_id>/recipe/versions/by-id/<version_id>",                 endpoint="get_recipe_version_by_id", view_func=get_recipe_version_by_id, methods=["GET"])
    api.add_url_rule("/products/<product_id>/recipe/save",                                        endpoint="save_recipe_version",      view_func=save_recipe_version,   methods=["POST"])
    api.add_url_rule("/products/<product_id>/recipe/publish",                                     endpoint="publish_recipe",           view_func=publish_recipe,        methods=["POST"])
    api.add_url_rule("/products/<product_id>/recipe/diff",                                        endpoint="diff_recipe_versions",     view_func=diff_recipe_versions,  methods=["GET"])

    # Manifest
    api.add_url_rule("/products/<product_id>/manifest",                                           endpoint="get_product_manifest",     view_func=get_run_manifest,      methods=["GET"])

    # Manufacturing Config
    api.add_url_rule("/products/<product_id>/manufacturing",                                      endpoint="get_mfg_config",           view_func=get_manufacturing_config,    methods=["GET"])
    api.add_url_rule("/products/<product_id>/manufacturing",                                      endpoint="create_mfg_config",        view_func=create_manufacturing_config, methods=["POST"])
    api.add_url_rule("/products/<product_id>/manufacturing",                                      endpoint="update_mfg_config",        view_func=update_manufacturing_config, methods=["PUT"])
    api.add_url_rule("/products/<product_id>/manufacturing",                                      endpoint="delete_mfg_config",        view_func=delete_manufacturing_config, methods=["DELETE"])

    # Product Access
    api.add_url_rule("/products/<product_id>/access",                                             endpoint="list_product_access",      view_func=list_product_access,         methods=["GET"])
    api.add_url_rule("/products/<product_id>/access",                                             endpoint="grant_product_access",     view_func=grant_product_access,        methods=["POST"])
    api.add_url_rule("/products/<product_id>/access/<access_id>",                                 endpoint="update_product_access",    view_func=update_product_access,       methods=["PUT"])
    api.add_url_rule("/products/<product_id>/access/<access_id>",                                 endpoint="revoke_product_access",    view_func=revoke_product_access,       methods=["DELETE"])
