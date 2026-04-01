"""Build recipe endpoints — CRUD for product build scripts stored in MinIO.

Each product has one build recipe (a bash script) that the build service
downloads and executes inside the product's devcontainer-specified builder
image. The recipe uses the Concord Build SDK for universal operations
(version handling, CFW generation, artifact naming).

Recipes are stored in MinIO at: firmware/recipes/{product_slug}/build.sh
"""

import io
import logging

from flask import jsonify, request, Response

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, not_found, internal_error
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import get_storage_client, get_bucket_name, storage_key, StoragePrefixes

logger = logging.getLogger(__name__)

RECIPE_PREFIX = "firmware/recipes"


def _recipe_key(product_slug: str) -> str:
    return f"{RECIPE_PREFIX}/{product_slug}/build.sh"


@require_permissions(Permissions.BUILDS_VIEW)
def get_recipe(product_id: str):
    """GET /v2/products/<id>/recipe — Download the product's build recipe."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    slug = product.slug or product.name.lower().replace(" ", "_")
    key = _recipe_key(slug)

    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        response = client.get_object(bucket, key)
        content = response.read().decode("utf-8")
        response.close()

        return jsonify(ApiResponse.ok({
            "product": product.name,
            "slug": slug,
            "storageKey": key,
            "content": content,
        }).to_dict()), 200

    except Exception as e:
        error_str = str(e)
        if "NoSuchKey" in error_str or "not found" in error_str.lower():
            return jsonify(ApiResponse.ok({
                "product": product.name,
                "slug": slug,
                "storageKey": key,
                "content": None,
            }).to_dict()), 200
        logger.error("Failed to fetch recipe for %s: %s", slug, e)
        return internal_error("Failed to fetch recipe")


@require_permissions(Permissions.BUILDS_MANAGE)
def update_recipe(product_id: str):
    """PUT /v2/products/<id>/recipe — Upload or update the build recipe."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data = request.get_json()
    if not data or not data.get("content"):
        return bad_request("Request must include 'content' (the build recipe script)")

    content = data["content"]
    if not isinstance(content, str) or len(content) < 10:
        return bad_request("Recipe content too short")

    slug = product.slug or product.name.lower().replace(" ", "_")
    key = _recipe_key(slug)

    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        content_bytes = content.encode("utf-8")
        client.put_object(
            bucket, key,
            io.BytesIO(content_bytes),
            length=len(content_bytes),
            content_type="text/x-shellscript",
        )

        log_audit("recipe.update", "Product", product_id, {
            "product": product.name,
            "slug": slug,
            "size": len(content_bytes),
        })

        logger.info("Recipe updated for %s (%d bytes)", slug, len(content_bytes))

        return jsonify(ApiResponse.ok({
            "product": product.name,
            "slug": slug,
            "storageKey": key,
            "size": len(content_bytes),
        }).to_dict()), 200

    except Exception as e:
        logger.error("Failed to save recipe for %s: %s", slug, e)
        return internal_error("Failed to save recipe")


@require_permissions(Permissions.BUILDS_MANAGE)
def validate_recipe(product_id: str):
    """POST /v2/products/<id>/recipe/validate — Validate a recipe's structure.

    Checks that the script:
    1. Sources concord-build.sh
    2. Calls concord_init
    3. Calls concord_collect_hex for expected target roles
    4. Calls concord_finalize
    """
    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={"boards": {"include": {"revisions": {"include": {"targets": True}}}}},
    )
    if not product:
        return not_found("Product not found")

    data = request.get_json()
    content = (data or {}).get("content", "")
    if not content:
        return bad_request("Request must include 'content'")

    errors = []
    warnings = []

    # Check SDK sourcing
    if "concord-build.sh" not in content:
        errors.append("Recipe must source the Concord Build SDK: source /app/sdk/concord-build.sh")

    if "concord_init" not in content:
        errors.append("Recipe must call concord_init")

    if "concord_finalize" not in content:
        errors.append("Recipe must call concord_finalize")

    # Check that concord_collect_hex is called for each target role
    expected_roles = set()
    for board in (product.boards or []):
        for rev in (board.revisions or []):
            for target in (rev.targets or []):
                expected_roles.add(target.role)

    for role in expected_roles:
        if f"concord_collect_hex {role}" not in content:
            warnings.append(f"Recipe should call 'concord_collect_hex {role}' for target role '{role}'")

    if "west build" not in content:
        warnings.append("Recipe doesn't contain 'west build' — is this a Zephyr project?")

    valid = len(errors) == 0

    return jsonify(ApiResponse.ok({
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
    }).to_dict()), 200
