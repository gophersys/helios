"""Route registration for /v2/asset-sets top-level endpoints."""

from flask import Blueprint

from .asset_sets import (
    get_asset_set, get_latest_asset_set, complete_asset_set,
    delete_asset_set, download_asset_set_zip,
)
from .assets import upload_asset


def register_asset_routes(api: Blueprint):
    api.add_url_rule("/asset-sets/latest",                                                       endpoint="get_latest_asset_set",     view_func=get_latest_asset_set,      methods=["GET"])
    api.add_url_rule("/asset-sets/<asset_set_id>",                                               endpoint="get_asset_set",            view_func=get_asset_set,             methods=["GET"])
    api.add_url_rule("/asset-sets/<asset_set_id>",                                               endpoint="delete_asset_set",         view_func=delete_asset_set,          methods=["DELETE"])
    api.add_url_rule("/asset-sets/<asset_set_id>/assets",                                        endpoint="upload_asset",             view_func=upload_asset,              methods=["POST"])
    api.add_url_rule("/asset-sets/<asset_set_id>/complete",                                      endpoint="complete_asset_set",       view_func=complete_asset_set,        methods=["POST"])
    api.add_url_rule("/asset-sets/<asset_set_id>/download",                                      endpoint="download_asset_set_zip",   view_func=download_asset_set_zip,    methods=["GET"])
