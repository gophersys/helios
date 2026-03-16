"""CI build script endpoint — serves build scripts to workers."""

import logging
import os
from pathlib import Path

from flask import jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse, ErrorDetail

logger = logging.getLogger(__name__)


# Build scripts stored in Docker container at /app/firmware/products/{product}/scripts/build.sh
# In dev mode (monorepo), resolve from script location
_script_path = Path(__file__)
if _script_path.parts[:2] == ('/', 'app'):
    # Docker container: /app/src/api/v2/builds/scripts.py → /app/firmware/products
    SCRIPTS_DIR = Path("/app/firmware/products")
else:
    # Dev/monorepo: resolve relative to script location
    SCRIPTS_DIR = _script_path.parent.parent.parent.parent.parent / "firmware" / "products"


def _normalize_product_dir(product_key: str) -> str | None:
    """Normalize a product key to a directory name.

    Strips _fw, _mfg suffixes and board variants to get the base product dir.
    e.g., alpha_fw -> alpha, alpha_mfg_fw -> alpha, sigma5_b0 -> sigma5

    Returns None if the key contains path traversal sequences or invalid characters.
    """
    # Reject path traversal attempts and invalid characters
    if ".." in product_key or "/" in product_key or "\\" in product_key:
        return None

    key = product_key.lower().replace("_fw", "").replace("_mfg", "")
    for suffix in ["_b0", "_a0", "_b1", "_a1", "_c0"]:
        key = key.replace(suffix, "")

    # Only allow alphanumeric and underscore
    cleaned = key.strip("_")
    if not cleaned or not all(c.isalnum() or c == "_" for c in cleaned):
        return None
    return cleaned


def _get_script_path(product: str) -> Path | None:
    """Map product key to script path.

    Dynamically normalizes product keys instead of using a static map.
    e.g., alpha_fw -> alpha, alpha_mfg_fw -> alpha, sigma5_fw -> sigma5

    Includes path traversal protection to ensure the resolved path stays within SCRIPTS_DIR.
    """
    product_dir = _normalize_product_dir(product)
    if not product_dir:
        return None

    script_path = (SCRIPTS_DIR / product_dir / "scripts" / "build.sh").resolve()

    # Verify resolved path is within SCRIPTS_DIR (defense in depth)
    try:
        script_path.relative_to(SCRIPTS_DIR.resolve())
    except ValueError:
        logger.warning("Path traversal attempt blocked: %s", product)
        return None

    if script_path.exists():
        return script_path
    return None


@require_permissions(Permissions.BUILDS_VIEW)
def get_build_script(product: str):
    """GET /v2/builds/scripts/<product> — Get build script content for a product."""
    script_path = _get_script_path(product)

    if not script_path:
        return not_found(f"No build script for product: {product}")

    try:
        content = script_path.read_text()
        return jsonify(ApiResponse.ok({
            "product": product,
            "content": content,
            "path": str(script_path.relative_to(SCRIPTS_DIR.parent.parent.parent)),
        }).to_dict()), 200
    except Exception as e:
        logger.error("Failed to read build script for %s: %s", product, e)
        return internal_error("Failed to read build script")


@require_permissions(Permissions.BUILDS_VIEW)
def list_build_scripts():
    """GET /v2/builds/scripts — List available build scripts.

    Dynamically discovers products by scanning the firmware products directory.
    """
    scripts = []

    if SCRIPTS_DIR.exists():
        for product_dir in sorted(SCRIPTS_DIR.iterdir()):
            if not product_dir.is_dir():
                continue
            script_path = product_dir / "scripts" / "build.sh"
            if script_path.exists():
                scripts.append({
                    "product": product_dir.name,
                    "path": str(script_path.relative_to(SCRIPTS_DIR.parent.parent.parent)),
                    "size": script_path.stat().st_size,
                })

    return jsonify(ApiResponse.ok(scripts).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def upload_build_script(product: str):
    """POST /v2/builds/scripts/<product> — Upload a build script (not implemented)."""
    return jsonify(ApiResponse.error(ErrorDetail(message="Script upload not implemented - scripts are managed in git")).to_dict()), 501


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_build_script(product: str):
    """DELETE /v2/builds/scripts/<product> — Delete a build script (not implemented)."""
    return jsonify(ApiResponse.error(ErrorDetail(message="Script deletion not implemented - scripts are managed in git")).to_dict()), 501
