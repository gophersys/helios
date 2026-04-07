"""Test package endpoints — upload, list, get latest, download.

A TestPackage is a versioned tar.gz archive containing the validation test
suite for a product.  Development packages are mutable (overwritten on each
upload); released packages are immutable.
"""

import hashlib
import json
import logging
import math
from io import BytesIO
from typing import Any

from flask import jsonify, request

from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client
from src.services.storage.client import (
    get_bucket_name,
    get_storage_client,
    presigned_get_url,
    storage_key,
)

logger = logging.getLogger(__name__)

TEST_PACKAGES_PREFIX = "test-packages"


def _serialize_test_package(tp: Any) -> dict:
    """Serialize a TestPackage DB record to an API response dict."""
    return {
        "id": tp.id,
        "productId": tp.productId,
        "version": tp.version,
        "status": tp.status,
        "frameworkVersion": tp.frameworkVersion,
        "testCount": tp.testCount,
        "stagesEnabled": tp.stagesEnabled,
        "manifestHash": tp.manifestHash,
        "notes": tp.notes,
        "createdAt": tp.createdAt.isoformat() if tp.createdAt else None,
        "updatedAt": tp.updatedAt.isoformat() if tp.updatedAt else None,
    }


def _resolve_product(product_id: str):
    """Look up a product by ID or slug, returning (product, error_response)."""
    db = get_db_client()
    # Try by ID first, then by slug
    product = db.product.find_unique(where={"id": product_id})
    if not product:
        product = db.product.find_first(where={"slug": product_id})
    if not product:
        return None, not_found(f"Product '{product_id}' not found")
    return product, None


# ── Upload ───────────────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_MANAGE)
def upload_test_package(product_id: str):
    """POST — upload a test package archive (delegates to _upload_test_package_impl)."""
    try:
        return _upload_test_package_impl(product_id)
    except Exception as e:
        logger.exception("upload_test_package error")
        return internal_error(f"Upload failed: {e}")


def _upload_test_package_impl(product_id: str):
    """POST /v2/products/<slug>/test-packages — upload a test package archive."""
    product, err = _resolve_product(product_id)
    if err:
        return err

    if "package" not in request.files:
        return bad_request("No package file provided")

    package_file = request.files["package"]
    if not package_file.filename:
        return bad_request("No file selected")

    # Validate file extension
    if not package_file.filename.endswith(".tar.gz"):
        return bad_request("Package must be a .tar.gz file")

    # Parse manifest from form field
    manifest_raw = request.form.get("manifest")
    if not manifest_raw:
        return bad_request("manifest field is required")

    try:
        manifest = json.loads(manifest_raw)
    except (json.JSONDecodeError, ValueError):
        return bad_request("manifest must be valid JSON")

    # Validate required manifest fields
    version = (manifest.get("version") or "").strip()
    if not version:
        return bad_request("manifest.version is required")

    framework_version = (manifest.get("frameworkVersion") or "").strip()
    if not framework_version:
        return bad_request("manifest.frameworkVersion is required")

    # Validate manifest slug matches the product
    product_slug = product.slug or product.id
    manifest_slug = (manifest.get("productSlug") or "").strip()
    if manifest_slug and manifest_slug != product_slug and manifest_slug != product_id:
        return bad_request(
            f"manifest.productSlug '{manifest_slug}' does not match product '{product_slug}'"
        )

    status = (manifest.get("status") or "DEVELOPMENT").strip().upper()
    if status not in ("DEVELOPMENT", "RELEASED"):
        return bad_request("manifest.status must be DEVELOPMENT or RELEASED")

    test_count = manifest.get("testCount", 0)
    stages_enabled = manifest.get("stagesEnabled")
    notes = manifest.get("notes")

    db = get_db_client()

    # For RELEASED packages, version must be unique
    if status == "RELEASED":
        existing = db.testpackage.find_first(
            where={
                "productId": product.id,
                "version": version,
                "status": "RELEASED",
            }
        )
        if existing:
            return conflict(
                f"Released test package version '{version}' already exists for this product"
            )

    # Read file and compute hash
    file_data = package_file.read()
    size_bytes = len(file_data)
    manifest_hash = hashlib.sha256(manifest_raw.encode()).hexdigest()

    # Upload to MinIO
    object_key = storage_key(
        TEST_PACKAGES_PREFIX,
        f"{product_slug}/{version}/package.tar.gz",
    )

    try:
        client = get_storage_client()
        bucket = get_bucket_name()
        client.put_object(
            bucket,
            object_key,
            BytesIO(file_data),
            length=size_bytes,
            content_type="application/gzip",
        )
    except Exception as e:
        logger.error("Failed to upload test package to storage: %s", e)
        return internal_error("Failed to upload test package")

    # For DEVELOPMENT packages, upsert (overwrite existing dev version)
    if status == "DEVELOPMENT":
        existing_dev = db.testpackage.find_first(
            where={
                "productId": product.id,
                "version": version,
            }
        )
        if existing_dev:
            from database import Json

            update_data = {
                    "storageKey": object_key,
                    "frameworkVersion": framework_version,
                    "manifestHash": manifest_hash,
                    "testCount": test_count,
                    "notes": notes,
                }
            if stages_enabled:
                update_data["stagesEnabled"] = Json(stages_enabled)

            tp = db.testpackage.update(
                where={"id": existing_dev.id},
                data=update_data,
            )
            log_audit("testPackage.update", "TestPackage", tp.id, {
                "productSlug": product_slug,
                "version": version,
                "status": status,
                "sizeBytes": size_bytes,
            })
            return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200

    # Create new record
    from database import Json

    create_data = {
        "productId": product.id,
        "version": version,
        "status": status,
        "storageKey": object_key,
        "frameworkVersion": framework_version,
        "manifestHash": manifest_hash,
        "testCount": test_count,
        "notes": notes,
    }
    if stages_enabled is not None:
        create_data["stagesEnabled"] = Json(stages_enabled)

    tp = db.testpackage.create(data=create_data)

    log_audit("testPackage.create", "TestPackage", tp.id, {
        "productSlug": product_slug,
        "version": version,
        "status": status,
        "sizeBytes": size_bytes,
    })
    return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 201


# ── List ─────────────────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_VIEW)
def list_test_packages(product_id: str):
    """GET /v2/products/<product_id>/test-packages — list test packages for a product."""
    product, err = _resolve_product(product_id)
    if err:
        return err

    db = get_db_client()

    where: dict = {"productId": product.id}
    status_filter = request.args.get("status")
    if status_filter:
        status_filter = status_filter.strip().upper()
        if status_filter in ("DEVELOPMENT", "RELEASED"):
            where["status"] = status_filter

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.testpackage.count(where=where)
    packages = db.testpackage.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )

    return jsonify(ApiResponse.ok({
        "data": [_serialize_test_package(tp) for tp in packages],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


# ── Latest Released ──────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_VIEW)
def get_latest_test_package(product_id: str):
    """GET /v2/products/<slug>/test-packages/latest — get the most recent released package."""
    product, err = _resolve_product(product_id)
    if err:
        return err

    db = get_db_client()
    tp = db.testpackage.find_first(
        where={
            "productId": product.id,
            "status": "RELEASED",
        },
        order={"createdAt": "desc"},
    )
    if not tp:
        return not_found("No released test package found for this product")

    return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200


# ── Download ─────────────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_VIEW)
def download_test_package(product_id: str, version: str):
    """GET /v2/products/<product_id>/test-packages/<version>/download — presigned download URL."""
    product, err = _resolve_product(product_id)
    if err:
        return err

    product_slug = product.slug or product.id

    db = get_db_client()
    tp = db.testpackage.find_first(
        where={
            "productId": product.id,
            "version": version,
        },
    )
    if not tp:
        return not_found(f"Test package version '{version}' not found")

    url = presigned_get_url(
        tp.storageKey,
        download_filename=f"{product_slug}-{version}-test-package.tar.gz",
    )
    if not url:
        return not_found("Package file not found in storage")

    return jsonify(ApiResponse.ok({
        "url": url,
        "filename": f"{product_slug}-{version}-test-package.tar.gz",
        "version": tp.version,
    }).to_dict()), 200
