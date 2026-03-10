"""CI build script endpoint — serves build scripts to workers."""

import os
from pathlib import Path

from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse


# Build scripts stored in Docker container at /app/firmware/products/{product}/scripts/build.sh
# In dev mode (monorepo), resolve from script location
_script_path = Path(__file__)
if _script_path.parts[:2] == ('/', 'app'):
    # Docker container: /app/src/api/v2/ci/scripts.py → /app/firmware/products
    SCRIPTS_DIR = Path("/app/firmware/products")
else:
    # Dev/monorepo: resolve relative to script location
    SCRIPTS_DIR = _script_path.parent.parent.parent.parent.parent / "firmware" / "products"


def _get_script_path(product: str) -> Path | None:
    """Map product key to script path.

    Product keys: alpha, alpha_mfg, sigma5, sigma5_mfg
    """
    # Map repo-style names to product directories
    # alpha_fw -> alpha, alpha_mfg_fw -> alpha, sigma5_fw -> sigma5
    product_map = {
        "alpha": "alpha",
        "alpha_fw": "alpha",
        "alpha_mfg": "alpha",
        "alpha_mfg_fw": "alpha",
        "sigma5": "sigma5",
        "sigma5_fw": "sigma5",
        "sigma5_mfg": "sigma5",
        "sigma5_mfg_fw": "sigma5",
    }

    product = product_map.get(product.lower())
    if not product:
        return None

    script_path = SCRIPTS_DIR / product / "scripts" / "build.sh"
    if script_path.exists():
        return script_path
    return None


@require_permissions(Permissions.ADMIN_CI_VIEW)
def get_build_script(product: str):
    """GET /v2/ci/scripts/<product> — Get build script content for a product."""
    script_path = _get_script_path(product)

    if not script_path:
        return jsonify(ApiResponse.error(f"No build script for product: {product}").to_dict()), 404

    try:
        content = script_path.read_text()
        return jsonify(ApiResponse.ok({
            "product": product,
            "content": content,
            "path": str(script_path.relative_to(SCRIPTS_DIR.parent.parent.parent)),
        }).to_dict()), 200
    except Exception as e:
        return jsonify(ApiResponse.error(f"Failed to read script: {e}").to_dict()), 500


@require_permissions(Permissions.ADMIN_CI_VIEW)
def list_build_scripts():
    """GET /v2/ci/scripts — List available build scripts."""
    products = ["alpha", "sigma5"]
    scripts = []

    for product in products:
        script_path = SCRIPTS_DIR / product / "scripts" / "build.sh"
        if script_path.exists():
            scripts.append({
                "product": product,
                "path": str(script_path.relative_to(SCRIPTS_DIR.parent.parent.parent)),
                "size": script_path.stat().st_size,
            })

    return jsonify(ApiResponse.ok(scripts).to_dict()), 200


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def upload_build_script(product: str):
    """POST /v2/ci/scripts/<product> — Upload a build script (not implemented)."""
    return jsonify(ApiResponse.error("Script upload not implemented - scripts are managed in git").to_dict()), 501


@require_permissions(Permissions.ADMIN_CI_MANAGE)
def delete_build_script(product: str):
    """DELETE /v2/ci/scripts/<product> — Delete a build script (not implemented)."""
    return jsonify(ApiResponse.error("Script deletion not implemented - scripts are managed in git").to_dict()), 501
