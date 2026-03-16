"""CI build script endpoint — serves build scripts to workers."""

import logging
import os
from pathlib import Path

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.errors import internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse, ErrorDetail
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)


# Filesystem fallback for scripts not yet migrated to DB
_script_path = Path(__file__)
if _script_path.parts[:2] == ('/', 'app'):
    SCRIPTS_DIR = Path("/app/firmware/products")
else:
    SCRIPTS_DIR = _script_path.parent.parent.parent.parent.parent / "firmware" / "products"


def _normalize_product_key(product_key: str) -> str | None:
    """Normalize a product key to a base product name.

    Strips _fw, _mfg suffixes and board variants.
    e.g., alpha_fw -> alpha, alpha_mfg_fw -> alpha, sigma5_b0 -> sigma5
    """
    if ".." in product_key or "/" in product_key or "\\" in product_key:
        return None

    key = product_key.lower().replace("_fw", "").replace("_mfg", "")
    for suffix in ["_b0", "_a0", "_b1", "_a1", "_c0"]:
        key = key.replace(suffix, "")

    cleaned = key.strip("_")
    if not cleaned or not all(c.isalnum() or c == "_" for c in cleaned):
        return None
    return cleaned


def _get_script_from_db(product_key: str, stage: int | None = None) -> dict | None:
    """Try to find a build script in the DB via ProductStageConfig.

    Looks up the product by slug or repoSlug, then finds the stage config
    with a buildScript set. If stage is None, returns the first stage with a script.
    """
    db = get_db_client()
    normalized = _normalize_product_key(product_key)
    if not normalized:
        return None

    # Find product by slug prefix or repoSlug
    products = db.product.find_many(
        where={
            "OR": [
                {"slug": {"startswith": normalized}},
                {"repoSlug": {"startswith": normalized}},
            ]
        },
        take=1,
    )

    if not products:
        return None

    product = products[0]

    # Find stage config with a build script
    where = {"productId": product.id, "buildScript": {"not": None}}
    if stage is not None:
        where["stage"] = stage

    config = db.productstageconfig.find_first(
        where=where,
        order={"stage": "asc"},
    )

    if not config or not config.buildScript:
        return None

    return {
        "product": product_key,
        "content": config.buildScript,
        "stage": config.stage,
        "stageName": config.name,
        "source": "database",
    }


def _get_script_from_filesystem(product_key: str) -> dict | None:
    """Fallback: read build script from filesystem."""
    normalized = _normalize_product_key(product_key)
    if not normalized:
        return None

    script_path = (SCRIPTS_DIR / normalized / "scripts" / "build.sh").resolve()

    try:
        script_path.relative_to(SCRIPTS_DIR.resolve())
    except ValueError:
        logger.warning("Path traversal attempt blocked: %s", product_key)
        return None

    if not script_path.exists():
        return None

    return {
        "product": product_key,
        "content": script_path.read_text(),
        "source": "filesystem",
    }


@require_permissions(Permissions.BUILDS_VIEW)
def get_build_script(product: str):
    """GET /v2/builds/scripts/<product> — Get build script content.

    Checks DB first (ProductStageConfig.buildScript), falls back to filesystem.
    Optional ?stage=N query param to get a specific stage's script.
    """
    stage_param = request.args.get("stage", type=int)

    # Try DB first
    result = _get_script_from_db(product, stage=stage_param)

    # Fallback to filesystem
    if not result:
        result = _get_script_from_filesystem(product)

    if not result:
        return not_found(f"No build script for product: {product}")

    return jsonify(ApiResponse.ok(result).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def list_build_scripts():
    """GET /v2/builds/scripts — List available build scripts.

    Returns scripts from both DB and filesystem, with DB taking priority.
    """
    db = get_db_client()
    scripts = []
    seen_products = set()

    # DB scripts (from stage configs)
    configs = db.productstageconfig.find_many(
        where={"buildScript": {"not": None}},
        include={"product": True},
        order={"stage": "asc"},
    )

    for cfg in configs:
        product_name = cfg.product.repoSlug or cfg.product.slug if cfg.product else "unknown"
        key = f"{product_name}:{cfg.stage}"
        if key not in seen_products:
            seen_products.add(key)
            scripts.append({
                "product": product_name,
                "stage": cfg.stage,
                "stageName": cfg.name,
                "source": "database",
                "size": len(cfg.buildScript) if cfg.buildScript else 0,
            })

    # Filesystem scripts (fallback for unmigrated products)
    if SCRIPTS_DIR.exists():
        for product_dir in sorted(SCRIPTS_DIR.iterdir()):
            if not product_dir.is_dir():
                continue
            script_path = product_dir / "scripts" / "build.sh"
            if script_path.exists():
                product_name = product_dir.name
                # Skip if already found in DB
                if not any(s["product"].startswith(product_name) for s in scripts):
                    scripts.append({
                        "product": product_name,
                        "source": "filesystem",
                        "size": script_path.stat().st_size,
                    })

    return jsonify(ApiResponse.ok(scripts).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def upload_build_script(product: str):
    """POST /v2/builds/scripts/<product> — Upload a build script (not implemented)."""
    return jsonify(ApiResponse.error(
        ErrorDetail(message="Use PUT /v2/products/{id}/stages/{stage} to update build scripts")
    ).to_dict()), 501


@require_permissions(Permissions.BUILDS_MANAGE)
def delete_build_script(product: str):
    """DELETE /v2/builds/scripts/<product> — Delete a build script (not implemented)."""
    return jsonify(ApiResponse.error(
        ErrorDetail(message="Use PUT /v2/products/{id}/stages/{stage} to manage build scripts")
    ).to_dict()), 501
