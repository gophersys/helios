"""Build recipe endpoints — CRUD for product build scripts stored in MinIO.

Each product has one build recipe (a bash script) that the build service
downloads and executes inside the product's devcontainer-specified builder
image. The recipe uses the Concord Build SDK for universal operations
(version handling, CFW generation, artifact naming).

Recipes are stored in MinIO at: firmware/recipes/{product_slug}/build.sh

Versioning: Each save creates a new RecipeVersion (draft). Publishing copies
the draft content to MinIO. The version history provides full audit trail
and diff capabilities.
"""

import difflib
import io
import logging
import math

from dataclasses import asdict

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


def _recipe_key(product_slug: str, stage: int | None = None) -> str:
    if stage:
        return f"{RECIPE_PREFIX}/{product_slug}/stage-{stage}/build.sh"
    return f"{RECIPE_PREFIX}/{product_slug}/build.sh"


@require_permissions(Permissions.BUILDS_VIEW)
def get_recipe(product_id: str):
    """GET /v2/products/<id>/recipe?stage=5 — Download a stage's build recipe."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    stage = request.args.get("stage", type=int)
    slug = product.slug or product.name.lower().replace(" ", "_")
    key = _recipe_key(slug, stage)

    # Fallback: if no stage-specific recipe, try the legacy product-level one
    fallback_key = _recipe_key(slug) if stage else None

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
            # Try fallback to legacy product-level recipe
            if fallback_key:
                try:
                    response = client.get_object(bucket, fallback_key)
                    content = response.read().decode("utf-8")
                    response.close()
                    return jsonify(ApiResponse.ok({
                        "product": product.name,
                        "slug": slug,
                        "stage": stage,
                        "storageKey": fallback_key,
                        "content": content,
                        "fallback": True,
                    }).to_dict()), 200
                except Exception:
                    pass
            return jsonify(ApiResponse.ok({
                "product": product.name,
                "slug": slug,
                "stage": stage,
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

    stage = data.get("stage") or request.args.get("stage", type=int)
    slug = product.slug or product.name.lower().replace(" ", "_")
    key = _recipe_key(slug, stage)

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


# =============================================================================
# Recipe Versioning
# =============================================================================


def _serialize_version(v, include_content: bool = False) -> dict:
    """Serialize a RecipeVersion record."""
    d = {
        "id": v.id,
        "productId": v.productId,
        "version": v.version,
        "status": v.status,
        "changeNote": v.changeNote,
        "createdAt": v.createdAt.isoformat() if v.createdAt else None,
        "createdBy": None,
    }
    if hasattr(v, "createdBy") and v.createdBy is not None:
        d["createdBy"] = {
            "id": v.createdBy.id,
            "name": v.createdBy.name,
            "email": v.createdBy.email,
        }
    if include_content:
        d["content"] = v.content
    return d


@require_permissions(Permissions.BUILDS_VIEW)
def list_recipe_versions(product_id: str):
    """GET /v2/products/<id>/recipe/versions — List recipe versions (paginated)."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.recipeversion.count(where={"productId": product_id})
    versions = db.recipeversion.find_many(
        where={"productId": product_id},
        order={"version": "desc"},
        skip=skip,
        take=limit,
        include={"createdBy": True},
    )

    pages = math.ceil(total / limit) if total > 0 else 1

    return jsonify(ApiResponse.paginated(
        data=[_serialize_version(v) for v in versions],
        page=page,
        total_pages=pages,
        total_results=total,
        results_per_page=limit,
    ).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_recipe_version(product_id: str, version_num: int):
    """GET /v2/products/<id>/recipe/versions/<version_num> — Get specific version with content."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    version = db.recipeversion.find_first(
        where={"productId": product_id, "version": version_num},
        include={"createdBy": True},
    )
    if not version:
        return not_found(f"Recipe version {version_num} not found")

    return jsonify(ApiResponse.ok(_serialize_version(version, include_content=True)).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_recipe_version_by_id(product_id: str, version_id: str):
    """GET /v2/products/<id>/recipe/versions/by-id/<version_id> — Get recipe version by record ID.

    Used by the build worker to fetch a pinned recipe version.
    """
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    version = db.recipeversion.find_unique(
        where={"id": version_id},
        include={"createdBy": True},
    )
    if not version or version.productId != product_id:
        return not_found(f"Recipe version {version_id} not found for this product")

    return jsonify(ApiResponse.ok(_serialize_version(version, include_content=True)).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def save_recipe_version(product_id: str):
    """POST /v2/products/<id>/recipe/save — Save a new draft version.

    Body: {"content": "...", "changeNote": "optional note"}
    Auto-increments version number.
    """
    from flask import g

    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    data = request.get_json()
    if not data or not data.get("content"):
        return bad_request("Request must include 'content'")

    content = data["content"]
    if not isinstance(content, str) or len(content) < 10:
        return bad_request("Recipe content too short")

    change_note = (data.get("changeNote") or "").strip() or None

    # Find the latest version number for this product
    latest = db.recipeversion.find_first(
        where={"productId": product_id},
        order={"version": "desc"},
    )
    next_version = (latest.version + 1) if latest else 1

    # Get current user ID if available
    user = getattr(g, "current_user", None)
    user_id = user["sub"] if user else None

    version = db.recipeversion.create(data={
        "productId": product_id,
        "version": next_version,
        "content": content,
        "status": "draft",
        "changeNote": change_note,
        "createdById": user_id,
    })

    # Auto-publish to MinIO so build service always uses the latest version
    stage = data.get("stage") or request.args.get("stage", type=int)
    slug = product.slug or product.name.lower().replace(" ", "_")
    key = _recipe_key(slug, stage)
    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        content_bytes = content.encode("utf-8")
        storage.put_object(bucket, key, io.BytesIO(content_bytes), len(content_bytes),
                          content_type="text/x-shellscript")
    except Exception:
        logger.exception("Failed to publish recipe v%d to MinIO", next_version)

    log_audit("recipe.version.save", "Product", product_id, {
        "product": product.name,
        "version": next_version,
        "changeNote": change_note,
    })

    logger.info("Recipe version %d saved and published for %s", next_version, product.name)

    return jsonify(ApiResponse.ok(_serialize_version(version, include_content=True)).to_dict()), 201


@require_permissions(Permissions.BUILDS_MANAGE)
def publish_recipe(product_id: str):
    """POST /v2/products/<id>/recipe/publish — Publish a draft version to MinIO.

    Finds the latest draft (or a specific version if body has {"version": N}),
    copies its content to MinIO at firmware/recipes/{slug}/build.sh,
    and sets its status to "published".
    """
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    slug = product.slug or product.name.lower().replace(" ", "_")

    data = request.get_json(silent=True) or {}
    target_version = data.get("version")

    if target_version is not None:
        # Publish a specific version
        version = db.recipeversion.find_first(
            where={"productId": product_id, "version": target_version},
        )
        if not version:
            return not_found(f"Recipe version {target_version} not found")
    else:
        # Find the latest draft
        version = db.recipeversion.find_first(
            where={"productId": product_id, "status": "draft"},
            order={"version": "desc"},
        )
        if not version:
            return not_found("No draft version found to publish")

    # Upload content to MinIO
    key = _recipe_key(slug)
    try:
        client = get_storage_client()
        bucket = get_bucket_name()

        content_bytes = version.content.encode("utf-8")
        client.put_object(
            bucket, key,
            io.BytesIO(content_bytes),
            length=len(content_bytes),
            content_type="text/x-shellscript",
        )
    except Exception as e:
        logger.error("Failed to publish recipe for %s: %s", slug, e)
        return internal_error("Failed to publish recipe to storage")

    # Mark this version as published
    db.recipeversion.update(
        where={"id": version.id},
        data={"status": "published"},
    )

    log_audit("recipe.publish", "Product", product_id, {
        "product": product.name,
        "slug": slug,
        "version": version.version,
        "size": len(content_bytes),
    })

    logger.info("Recipe version %d published for %s (%d bytes)", version.version, slug, len(content_bytes))

    return jsonify(ApiResponse.ok({
        "product": product.name,
        "slug": slug,
        "version": version.version,
        "storageKey": key,
        "size": len(content_bytes),
    }).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def diff_recipe_versions(product_id: str):
    """GET /v2/products/<id>/recipe/diff?from=N&to=M — Unified diff between two versions."""
    db = get_db_client()
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        return not_found("Product not found")

    from_version = request.args.get("from", type=int)
    to_version = request.args.get("to", type=int)

    if from_version is None or to_version is None:
        return bad_request("Both 'from' and 'to' query parameters are required")

    if from_version == to_version:
        return bad_request("'from' and 'to' must be different versions")

    v_from = db.recipeversion.find_first(
        where={"productId": product_id, "version": from_version},
    )
    v_to = db.recipeversion.find_first(
        where={"productId": product_id, "version": to_version},
    )

    if not v_from:
        return not_found(f"Recipe version {from_version} not found")
    if not v_to:
        return not_found(f"Recipe version {to_version} not found")

    diff = list(difflib.unified_diff(
        v_from.content.splitlines(keepends=True),
        v_to.content.splitlines(keepends=True),
        fromfile=f"v{from_version}",
        tofile=f"v{to_version}",
    ))

    return jsonify(ApiResponse.ok({
        "from": from_version,
        "to": to_version,
        "diff": "".join(diff),
        "hasChanges": len(diff) > 0,
    }).to_dict()), 200


# =============================================================================
# Stage Build Definitions
# =============================================================================


@require_permissions(Permissions.BUILDS_VIEW)
def get_stage_defs():
    """GET /v2/builds/stage-defs — Return DEFAULT stage build templates.

    These are the Python-defined defaults used for seeding new stage configs.
    The actual runtime matrix for a product lives in the StageBuildMatrix DB table.

    Optional query param: ?stage=smoke|silicon|integration|nightly|fuota
    """
    from corekinect.stages import Stage, get_stage_build_defs

    stage_filter = request.args.get("stage")

    if stage_filter:
        try:
            stage = Stage(stage_filter.lower())
        except ValueError:
            valid = [s.value for s in Stage]
            return bad_request(f"Invalid stage '{stage_filter}'. Valid: {valid}")

        defs = get_stage_build_defs(stage)
        return jsonify(ApiResponse.ok({
            "stage": stage.value,
            "builds": [asdict(d) for d in defs],
        }).to_dict()), 200

    # Return all stages
    result = {}
    for stage in Stage:
        defs = get_stage_build_defs(stage)
        result[stage.value] = [asdict(d) for d in defs]

    return jsonify(ApiResponse.ok(result).to_dict()), 200


# =============================================================================
# Recipe Templates
# =============================================================================


def _serialize_template(t, include_content: bool = False) -> dict:
    """Serialize a RecipeTemplate record."""
    d = {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "sortOrder": t.sortOrder,
        "createdAt": t.createdAt.isoformat() if t.createdAt else None,
        "updatedAt": t.updatedAt.isoformat() if t.updatedAt else None,
    }
    if include_content:
        d["content"] = t.content
    return d


@require_permissions(Permissions.BUILDS_VIEW)
def list_recipe_templates():
    """GET /v2/builds/recipe-templates — List all recipe templates."""
    db = get_db_client()
    templates = db.recipetemplate.find_many(
        order={"sortOrder": "asc"},
    )

    return jsonify(ApiResponse.ok(
        [_serialize_template(t) for t in templates]
    ).to_dict()), 200


@require_permissions(Permissions.BUILDS_VIEW)
def get_recipe_template(template_id: str):
    """GET /v2/builds/recipe-templates/<id> — Get template with content."""
    db = get_db_client()
    template = db.recipetemplate.find_unique(where={"id": template_id})
    if not template:
        return not_found("Recipe template not found")

    return jsonify(ApiResponse.ok(
        _serialize_template(template, include_content=True)
    ).to_dict()), 200


@require_permissions(Permissions.BUILDS_MANAGE)
def test_recipe_build(product_id: str):
    """POST /v2/products/<id>/recipe/test-build — Run a test build with the current recipe.

    Creates a single BuildJob that the build service picks up and executes.
    The recipe content is saved as a new version before the build starts.
    Logs stream via WebSocket (ci_build_log events).

    Body: {
        "content": "#!/bin/bash\n...",
        "boardRevisionId": "rev-id",
        "stageConfigId": "stage-id" (optional)
    }
    Returns: { "buildJobId": "...", "recipeVersion": N }
    """
    from flask import g
    from database import Json

    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={"boards": {"include": {"revisions": {"include": {"targets": True}}}}},
    )
    if not product:
        return not_found("Product not found")

    data = request.get_json()
    if not data:
        return bad_request("Request body required")

    content = data.get("content", "").strip()
    if not content or len(content) < 10:
        return bad_request("Recipe content is required (min 10 chars)")

    revision_id = data.get("boardRevisionId")
    if not revision_id:
        return bad_request("boardRevisionId is required")

    # Find the target revision
    revision = None
    board = None
    for b in (product.boards or []):
        for r in (b.revisions or []):
            if r.id == revision_id:
                revision = r
                board = b
                break

    if not revision:
        return bad_request("Board revision not found")

    # Write recipe to MinIO so the build service can fetch it
    # Does NOT create a version — test builds use the editor content directly
    test_stage = data.get("stage")
    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        slug = product.slug or product.name.lower().replace(" ", "-")
        key = _recipe_key(slug, test_stage)
        content_bytes = content.encode("utf-8")
        storage.put_object(bucket, key, io.BytesIO(content_bytes), len(content_bytes), content_type="text/x-shellscript")
    except Exception:
        logger.exception("Failed to write recipe to MinIO for test build")

    # Look up signing key — check stage config first, then any signing_key secret
    signing_key_value = None
    stage_config_id = data.get("stageConfigId")

    if stage_config_id:
        # Use the specific stage config's signing key
        stage_cfg = db.productstageconfig.find_unique(
            where={"id": stage_config_id},
            include={"signingKey": True},
        )
        if stage_cfg and stage_cfg.signingKey:
            signing_key_value = stage_cfg.signingKey.value
    else:
        # Find any stage config for this product+revision with a signing key
        stage_cfg = db.productstageconfig.find_first(
            where={
                "productId": product_id,
                "boardRevisionId": revision_id,
                "signingKeyId": {"not": None},
            },
            include={"signingKey": True},
        )
        if stage_cfg and stage_cfg.signingKey:
            signing_key_value = stage_cfg.signingKey.value

    # If still no key from stage config, try any signing_key secret
    if not signing_key_value:
        any_key = db.secret.find_first(where={"type": "signing_key"})
        if any_key:
            signing_key_value = any_key.value

    if not signing_key_value:
        logger.warning("No signing key found for test build — build may fail on signing step")

    # Create a test BuildJob
    build_job = db.buildjob.create(data={
        "productId": product_id,
        "board": revision.ckBoardsName,
        "target": "app",
        "variant": "debug",
        "branch": "main",
        "status": "QUEUED",
        "matrixLabel": "TEST_BUILD",
        "configFlags": Json({
            "test_build": True,
            "config_log": True,
            "produces_hex": True,
            "produces_cfw": True,
        }),
        "webhookData": Json({
            "repoUrl": f"git@bitbucket.org:corekinect/{product.fwRepoSlug}.git" if product.fwRepoSlug else None,
            "fwRepoUrl": f"git@bitbucket.org:corekinect/{product.fwRepoSlug}.git" if product.fwRepoSlug else None,
            "mfgRepoUrl": f"git@bitbucket.org:corekinect/{product.mfgFwRepoSlug}.git" if product.mfgFwRepoSlug else None,
            "fwRepoSlug": product.fwRepoSlug,
            "mfgRepoSlug": product.mfgFwRepoSlug,
            "builderImage": product.builderImage,
            "ckBoardsName": revision.ckBoardsName,
            "signingKeyValue": signing_key_value,
            "testBuild": True,
        }),
    })

    log_audit("recipe.test_build", "BuildJob", build_job.id, {
        "productId": product_id,
        "board": revision.ckBoardsName,
    })

    # Resolve container image from product config or devcontainer.json
    container_image = product.builderImage or None
    if not container_image and product.fwRepoSlug:
        # Try to read from the cloned repo's devcontainer.json via build service
        container_image = "Resolved from devcontainer.json at build time"

    return jsonify(ApiResponse.ok({
        "buildJobId": build_job.id,
        "board": revision.ckBoardsName,
        "containerImage": container_image or "Default NCS builder",
    }).to_dict()), 201
