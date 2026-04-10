"""Test package endpoints — upload, list, get latest, download.

A TestPackage is a versioned tar.gz archive containing the validation or
manufacturing test suite for a product. Development packages are mutable
(overwritten on each upload); released packages are immutable.

On upload, fixture profiles (fixtures/*/fixture.yaml) are auto-extracted
and used to create/update FixtureDesign records — the test app is the
source of truth for fixture hardware configuration.
"""

import hashlib
import io
import json
import logging
import math
import tarfile
from io import BytesIO
from typing import Any, List, Optional

import yaml

from datetime import datetime, timezone

from flask import g, jsonify, request

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


# ── Fixture Design Auto-Extraction ──────────────────────────────────


def _extract_fixture_designs(file_data: bytes, product_id: str) -> int:
    """Extract fixture profiles from the tar.gz and create/update FixtureDesign records.

    Looks for fixtures/*/fixture.yaml files inside the archive.
    The test app is the source of truth for fixture hardware configuration.

    Returns the number of designs created or updated.
    """
    db = get_db_client()
    count = 0

    try:
        buf = BytesIO(file_data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            for member in tar.getmembers():
                # Match fixtures/{board}/fixture.yaml
                parts = member.name.split("/")
                if (
                    len(parts) >= 3
                    and parts[-3] == "fixtures"
                    and parts[-1] in ("fixture.yaml", "fixture.yml")
                    and member.isfile()
                ):
                    board_name = parts[-2]
                    f = tar.extractfile(member)
                    if not f:
                        continue

                    try:
                        profile = yaml.safe_load(f.read())
                    except Exception as e:
                        logger.warning("Failed to parse %s: %s", member.name, e)
                        continue

                    if not isinstance(profile, dict):
                        continue

                    capabilities = profile.get("capabilities", [])
                    if isinstance(capabilities, list):
                        # Normalize capabilities — may be dicts with names or plain strings
                        cap_names = []
                        for cap in capabilities:
                            if isinstance(cap, str):
                                cap_names.append(cap.split("(")[0].strip())
                            elif isinstance(cap, dict) and "name" in cap:
                                cap_names.append(cap["name"])
                        capabilities = cap_names

                    # Find board revision by ckBoardsName or version
                    board_rev = db.boardrevision.find_first(
                        where={
                            "board": {"productId": product_id},
                            "OR": [
                                {"ckBoardsName": board_name},
                                {"version": board_name},
                            ],
                        },
                    )
                    if not board_rev:
                        logger.info(
                            "No board revision found for '%s' — skipping fixture design",
                            board_name,
                        )
                        continue

                    # Design name: "{product_slug}-{board}-fixture"
                    design_name = f"{board_name}-fixture"

                    from database import Json

                    existing = db.fixturedesign.find_first(
                        where={"boardRevisionId": board_rev.id},
                    )
                    if existing:
                        db.fixturedesign.update(
                            where={"id": existing.id},
                            data={
                                "capabilities": capabilities,
                                "profileTemplate": Json(profile),
                            },
                        )
                        logger.info("Updated fixture design '%s' from test package", existing.name)
                    else:
                        db.fixturedesign.create(
                            data={
                                "name": design_name,
                                "boardRevisionId": board_rev.id,
                                "revision": profile.get("mtib_revision", "1.0"),
                                "capabilities": capabilities,
                                "profileTemplate": Json(profile),
                            },
                        )
                        logger.info("Created fixture design '%s' from test package", design_name)
                    count += 1

    except Exception as e:
        logger.warning("Fixture design extraction failed: %s", e)

    return count


def _extract_test_count(file_data: bytes) -> Optional[int]:
    """Count test_*.py files in the archive for the testCount field."""
    try:
        buf = BytesIO(file_data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            count = sum(
                1 for m in tar.getmembers()
                if m.isfile() and m.name.split("/")[-1].startswith("test_") and m.name.endswith(".py")
            )
            return count if count > 0 else None
    except Exception:
        return None


def _extract_v2_metadata(db, test_package_id: str, file_bytes: bytes, schema_version: str):
    """Extract structured stage/step metadata from the concord.yaml inside the archive.

    For validation packages, creates TestPackageStage records from 'stages'.
    For manufacturing packages, creates TestPackageStage records from 'steps'.
    Idempotent — deletes existing records before re-creating.
    """
    try:
        buf = io.BytesIO(file_bytes)
        manifest_data = None

        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            # Look for concord.yaml — try root-level first, then nested paths
            for member in tar.getmembers():
                if member.isfile() and member.name.split("/")[-1] == "concord.yaml":
                    f = tar.extractfile(member)
                    if f:
                        manifest_data = yaml.safe_load(f.read())
                        break

        if not manifest_data or not isinstance(manifest_data, dict):
            logger.debug("No concord.yaml found in archive for package %s", test_package_id)
            return

        # Delete existing stage records (idempotent for dev uploads)
        db.testpackagestage.delete_many(where={"testPackageId": test_package_id})

        # Validation packages: stages dict
        for idx, (name, cfg) in enumerate(manifest_data.get("stages", {}).items()):
            if not isinstance(cfg, dict):
                continue
            db.testpackagestage.create(data={
                "testPackageId": test_package_id,
                "name": name,
                "stageIndex": idx,
                "directory": cfg.get("directory"),
                "timeoutS": cfg.get("timeout_s"),
                "hardware": cfg.get("hardware", []),
                "markers": cfg.get("markers", []),
            })

        # Manufacturing packages: steps list
        for idx, step in enumerate(manifest_data.get("steps", [])):
            if not isinstance(step, dict):
                continue
            db.testpackagestage.create(data={
                "testPackageId": test_package_id,
                "name": step["name"],
                "stageIndex": idx,
                "module": step.get("module"),
                "timeoutS": step.get("timeout_s"),
                "hardware": step.get("hardware", []),
            })

        logger.info("Extracted v2 metadata for package %s (schema %s)", test_package_id, schema_version)
    except Exception as e:
        logger.warning("Failed to extract v2 metadata for package %s: %s", test_package_id, e)


def _serialize_package_stage(s) -> dict:
    """Serialize a TestPackageStage DB record to an API response dict."""
    return {
        "id": s.id,
        "name": s.name,
        "stageIndex": s.stageIndex,
        "directory": s.directory,
        "module": s.module,
        "timeoutS": s.timeoutS,
        "hardware": s.hardware if s.hardware else [],
        "markers": s.markers if s.markers else [],
    }


def _serialize_test_package(tp: Any) -> dict:
    """Serialize a TestPackage DB record to an API response dict."""
    data = {
        "id": tp.id,
        "productId": tp.productId,
        "version": tp.version,
        "type": tp.type,
        "status": tp.status,
        "frameworkVersion": tp.frameworkVersion,
        "testCount": tp.testCount,
        "stagesEnabled": tp.stagesEnabled,
        "schemaVersion": tp.schemaVersion if hasattr(tp, "schemaVersion") else None,
        "message": getattr(tp, "message", None),
        "gitSha": getattr(tp, "gitSha", None),
        "gitDirty": getattr(tp, "gitDirty", None),
        "manifestHash": tp.manifestHash,
        "notes": tp.notes,
        "releasedVersion": getattr(tp, "releasedVersion", None),
        "releasedAt": tp.releasedAt.isoformat() if getattr(tp, "releasedAt", None) else None,
        "releasedById": getattr(tp, "releasedById", None),
        "createdAt": tp.createdAt.isoformat() if tp.createdAt else None,
        "updatedAt": tp.updatedAt.isoformat() if tp.updatedAt else None,
    }
    if hasattr(tp, "packageStages") and tp.packageStages:
        data["packageStages"] = [_serialize_package_stage(s) for s in tp.packageStages]
    return data


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

    if status == "RELEASED":
        return bad_request(
            "Direct release uploads are no longer supported. "
            "Upload as DEVELOPMENT and promote via the UI."
        )

    package_type = (manifest.get("type") or "VALIDATION").strip().upper()
    if package_type not in ("VALIDATION", "MANUFACTURING"):
        return bad_request("manifest.type must be VALIDATION or MANUFACTURING")

    test_count = manifest.get("testCount", 0)
    stages_enabled = manifest.get("stagesEnabled")
    upload_message = (manifest.get("message") or "").strip() or None
    git_sha = (manifest.get("gitSha") or "").strip() or None
    git_dirty = manifest.get("gitDirty", None)
    notes = manifest.get("notes")

    db = get_db_client()

    # Read file and compute hash
    file_data = package_file.read()
    size_bytes = len(file_data)
    manifest_hash = hashlib.sha256(manifest_raw.encode()).hexdigest()

    # Upload to MinIO
    object_key = storage_key(
        TEST_PACKAGES_PREFIX,
        f"{product_slug}/{package_type.lower()}/{version}/package.tar.gz",
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
                "type": package_type,
            }
        )
        if existing_dev:
            from database import Json

            update_data = {
                    "storageKey": object_key,
                    "frameworkVersion": framework_version,
                    "manifestHash": manifest_hash,
                    "testCount": test_count,
                    "schemaVersion": manifest.get("schemaVersion"),
                    "message": upload_message,
                    "gitSha": git_sha,
                    "gitDirty": git_dirty,
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
            # Extract fixture designs and test count from the package
            _extract_fixture_designs(file_data, product.id)
            extracted_count = _extract_test_count(file_data)
            if extracted_count and extracted_count != tp.testCount:
                db.testpackage.update(where={"id": tp.id}, data={"testCount": extracted_count})
            # Extract v2 metadata if schema version is 2.0+
            schema_version = manifest.get("schemaVersion")
            if schema_version:
                _extract_v2_metadata(db, tp.id, file_data, schema_version)
            return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200

    # Create new record
    from database import Json

    create_data = {
        "productId": product.id,
        "version": version,
        "type": package_type,
        "status": status,
        "storageKey": object_key,
        "frameworkVersion": framework_version,
        "manifestHash": manifest_hash,
        "testCount": test_count,
        "schemaVersion": manifest.get("schemaVersion"),
        "message": upload_message,
        "gitSha": git_sha,
        "gitDirty": git_dirty,
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
    # Extract fixture designs and test count from the package
    designs_count = _extract_fixture_designs(file_data, product.id)
    extracted_count = _extract_test_count(file_data)
    if extracted_count:
        db.testpackage.update(where={"id": tp.id}, data={"testCount": extracted_count})
    if designs_count:
        logger.info("Extracted %d fixture design(s) from test package", designs_count)
    # Extract v2 metadata if schema version is 2.0+
    schema_version = manifest.get("schemaVersion")
    if schema_version:
        _extract_v2_metadata(db, tp.id, file_data, schema_version)
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
    type_filter = request.args.get("type")
    if type_filter:
        type_filter = type_filter.strip().upper()
        if type_filter in ("VALIDATION", "MANUFACTURING"):
            where["type"] = type_filter

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.testpackage.count(where=where)
    packages = db.testpackage.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"packageStages": True},
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
    """GET /v2/products/<slug>/test-packages/latest — get the most recent released package.

    Query params:
        type: VALIDATION (default) or MANUFACTURING
    """
    product, err = _resolve_product(product_id)
    if err:
        return err

    package_type = request.args.get("type", "VALIDATION").strip().upper()
    if package_type not in ("VALIDATION", "MANUFACTURING"):
        package_type = "VALIDATION"

    db = get_db_client()
    tp = db.testpackage.find_first(
        where={
            "productId": product.id,
            "type": package_type,
            "status": "RELEASED",
        },
        order={"createdAt": "desc"},
        include={"packageStages": True},
    )
    if not tp:
        # Fall back to latest dev package
        tp = db.testpackage.find_first(
            where={
                "productId": product.id,
                "type": package_type,
            },
            order={"createdAt": "desc"},
            include={"packageStages": True},
        )
    if not tp:
        return not_found(f"No test package found for this product (type={package_type})")

    return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200


# ── Download ─────────────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_VIEW)
def download_test_package(product_id: str, version: str):
    """GET /v2/products/<product_id>/test-packages/<version>/download — presigned download URL.

    Query params:
        type: VALIDATION (default) or MANUFACTURING
    """
    product, err = _resolve_product(product_id)
    if err:
        return err

    product_slug = product.slug or product.id

    where: dict = {"productId": product.id, "version": version}
    type_filter = request.args.get("type")
    if type_filter:
        type_filter = type_filter.strip().upper()
        if type_filter in ("VALIDATION", "MANUFACTURING"):
            where["type"] = type_filter

    db = get_db_client()
    tp = db.testpackage.find_first(where=where)
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


# ── Release (promote DEVELOPMENT → RELEASED) ─────────────────


def _bump_minor(version_str: str) -> str:
    """Parse a semver string and bump the minor version: '1.2.0' → '1.3.0'."""
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version_str}")
    major, minor, _ = int(parts[0]), int(parts[1]), int(parts[2])
    return f"{major}.{minor + 1}.0"


@require_permissions(Permissions.VALIDATION_MANAGE)
def release_test_package(product_id: str, package_id: str):
    """POST /v2/products/<product_id>/test-packages/<package_id>/release

    Promote a DEVELOPMENT test package to RELEASED with auto-versioning.
    """
    product, err = _resolve_product(product_id)
    if err:
        return err

    db = get_db_client()

    tp = db.testpackage.find_first(
        where={"id": package_id, "productId": product.id},
        include={"packageStages": True},
    )
    if not tp:
        return not_found(f"Test package '{package_id}' not found")

    if tp.status == "RELEASED":
        return conflict("This test package has already been released")

    # Auto-version: find the latest released package for this (product, type)
    latest_released = db.testpackage.find_first(
        where={
            "productId": product.id,
            "type": tp.type,
            "status": "RELEASED",
            "releasedVersion": {"not": None},
        },
        order={"releasedAt": "desc"},
    )

    if latest_released and latest_released.releasedVersion:
        try:
            released_version = _bump_minor(latest_released.releasedVersion)
        except ValueError:
            released_version = "1.0.0"
    else:
        released_version = "1.0.0"

    # Optional notes from request body
    body = request.get_json(silent=True) or {}
    notes = body.get("notes")

    now = datetime.now(timezone.utc)
    user_id = g.current_user["sub"]

    update_data: dict = {
        "status": "RELEASED",
        "releasedVersion": released_version,
        "releasedAt": now,
        "releasedById": user_id,
    }
    if notes is not None:
        update_data["notes"] = notes

    tp = db.testpackage.update(
        where={"id": tp.id},
        data=update_data,
        include={"packageStages": True},
    )

    log_audit("testPackage.release", "TestPackage", tp.id, {
        "productId": product.id,
        "type": tp.type,
        "releasedVersion": released_version,
        "previousStatus": "DEVELOPMENT",
    })

    return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200
