"""CI overlay files endpoint — serves DTS overlays to build workers."""

import logging
import tarfile
from io import BytesIO
from pathlib import Path

from flask import Response, jsonify

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse

logger = logging.getLogger(__name__)


# Overlays stored in monorepo at apps/firmware/products/{product}/overlays/
PRODUCTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "firmware" / "products"


def _get_overlays_dir(product: str) -> Path | None:
    """Map product key to overlays directory.

    Product keys: alpha, sigma5
    """
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

    product_dir = product_map.get(product.lower())
    if not product_dir:
        return None

    overlays_dir = PRODUCTS_DIR / product_dir / "overlays"
    if overlays_dir.exists() and overlays_dir.is_dir():
        return overlays_dir
    return None


@require_permissions(Permissions.BUILDS_VIEW)
def get_overlays(product: str):
    """GET /v2/builds/overlays/<product> — Get overlay files as tarball."""
    overlays_dir = _get_overlays_dir(product)

    if not overlays_dir:
        return not_found(f"No overlays for product: {product}")

    try:
        # Create tarball of overlay files
        tar_buffer = BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for overlay_file in overlays_dir.glob("*.overlay"):
                tar.add(overlay_file, arcname=overlay_file.name)

        tar_buffer.seek(0)
        return Response(
            tar_buffer.getvalue(),
            mimetype="application/gzip",
            headers={"Content-Disposition": f"attachment; filename={product}_overlays.tar.gz"},
        )

    except Exception as e:
        logger.error("Failed to package overlays for %s: %s", product, e)
        return internal_error("Failed to package overlays")


@require_permissions(Permissions.BUILDS_VIEW)
def list_overlays(product: str):
    """GET /v2/builds/overlays/<product>/list — List overlay files for a product."""
    overlays_dir = _get_overlays_dir(product)

    if not overlays_dir:
        return not_found(f"No overlays for product: {product}")

    try:
        overlays = []
        for overlay_file in overlays_dir.glob("*.overlay"):
            overlays.append({
                "name": overlay_file.name,
                "size": overlay_file.stat().st_size,
            })

        return jsonify(ApiResponse.ok({
            "product": product,
            "overlays": overlays,
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to list overlays for %s: %s", product, e)
        return internal_error("Failed to list overlays")
