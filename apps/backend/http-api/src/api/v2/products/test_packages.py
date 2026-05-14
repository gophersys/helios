"""Test package endpoints — upload, list, get latest, download.

A TestPackage is a versioned tar.gz archive containing the validation or
manufacturing test suite for a product. Development packages are mutable
(overwritten on each upload); released packages are immutable.

On upload, fixture profiles (fixtures/*/fixture.yaml) are auto-extracted
and used to create/update TestBedDesign records — the test app is the
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

from database import Json
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


# ── TestBed Design Auto-Extraction ──────────────────────────────────


def _extract_testbed_designs(
    file_data: bytes,
    test_package_id: str,
    package_status: str,
    product_id: str,
    package_type: str = "VALIDATION",
) -> Optional[str]:
    """Extract a fixture's metadata from the uploaded test package.

    The test app declares its DUT-side wiring in a Python class:

        # fixtures/<board_rev>/fixture.py
        class AlphaB0TestBed(TestBed):
            name = "alpha_b0-fixture"
            revision = "1.0"
            adcs = {"battery": ADC(channel=1, ...)}

    The path comes from ``concord.yaml`` ``fixture.module``
    (``testbeds.alpha_b0.testbed:AlphaB0TestBed`` →
    ``fixtures/alpha_b0/fixture.py``). The class is AST-parsed
    server-side — never executed — so an uploaded test app cannot
    run code in the http-api process.

    Returns the TestBedDesign row id, or ``None`` if no extractable
    fixture is in the archive.
    """
    db = get_db_client()

    try:
        from corekinect.testbed.extractor import (
            TestBedExtractionError,
            extract_testbed,
        )

        buf = BytesIO(file_data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            manifest_data = None
            for member in tar.getmembers():
                if member.isfile() and member.name.split("/")[-1] == "concord.yaml":
                    f = tar.extractfile(member)
                    if f:
                        manifest_data = yaml.safe_load(f.read())
                        break

            if not manifest_data or not isinstance(manifest_data, dict):
                logger.info("No concord.yaml in archive — skipping fixture extraction")
                return None

            fixture_cfg = manifest_data.get("fixture") or {}
            module_ref = fixture_cfg.get("module") or ""
            if not module_ref or ":" not in module_ref:
                logger.info(
                    "concord.yaml ``fixture.module`` missing or malformed "
                    "(expected 'dotted.path:ClassName') — skipping"
                )
                return None
            module_path, _ = module_ref.split(":", 1)
            file_path = module_path.replace(".", "/") + ".py"

            board_name = (manifest_data.get("product") or {}).get("board")
            if not board_name:
                logger.info("concord.yaml ``product.board`` missing — skipping")
                return None

            # Find the file in the archive.
            source: Optional[str] = None
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                normalized = member.name.lstrip("./")
                if normalized == file_path:
                    f = tar.extractfile(member)
                    if f:
                        source = f.read().decode("utf-8")
                    break

            if source is None:
                logger.info(
                    "fixture module %s not found in archive (expected at %s)",
                    module_ref, file_path,
                )
                return None

            try:
                summary = extract_testbed(source, source_path=file_path)
            except TestBedExtractionError as e:
                logger.warning("TestBed extraction rejected: %s", e)
                return None

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
                return None

            node_type = (
                package_type
                if package_type in ("MANUFACTURING", "VALIDATION")
                else "VALIDATION"
            )

            design_name = summary["name"]
            design_revision = summary["revision"]

            # Upsert by testPackageId — one design per test package.
            existing = db.fixturedesign.find_unique(
                where={"testPackageId": test_package_id},
            )
            if existing:
                db.fixturedesign.update(
                    where={"id": existing.id},
                    data={
                        "name": design_name,
                        "revision": design_revision,
                        "profileTemplate": Json(summary),
                        "type": node_type,
                        "status": package_status,
                        "boardRevisionId": board_rev.id,
                    },
                )
                logger.info(
                    "Updated fixture design '%s' rev %s for package %s",
                    design_name, design_revision, test_package_id,
                )
                return existing.id

            design = db.fixturedesign.create(
                data={
                    "testPackageId": test_package_id,
                    "name": design_name,
                    "boardRevisionId": board_rev.id,
                    "revision": design_revision,
                    "type": node_type,
                    "status": package_status,
                    "profileTemplate": Json(summary),
                },
            )
            logger.info(
                "Created fixture design '%s' rev %s for package %s",
                design_name, design_revision, test_package_id,
            )
            return design.id

    except Exception as e:
        logger.warning("TestBed design extraction failed: %s", e)

    return None


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


# Framework artifacts the platform requires in every uploaded test package.
# These ship with the corectl/corekinect wheel and are scaffolded by
# `corectl test init`. Hand-drift is caught locally by `corectl test
# validate`; this gate enforces the same contract server-side so packages
# uploaded out-of-band (CI scripts, third-party tools) cannot bypass it.
_REQUIRED_ARTIFACT_MARKERS = (
    ".claude/.framework-version",
    ".devcontainer/.framework-version",
)


def _check_framework_artifacts(file_data: bytes) -> Optional[str]:
    """Return None if the tarball contains every required framework artifact
    marker, otherwise an error message naming the missing ones.

    Cheap up-front check — only inspects member names, doesn't extract.
    Tarballs may root entries either at the top (``./.claude/...``) or
    via a single wrapper directory (``app/.claude/...``); both shapes are
    accepted as long as the relative tail matches.
    """
    try:
        buf = BytesIO(file_data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            # ``str.lstrip(chars)`` removes any combination of the given
            # characters from the left, NOT the literal prefix — using it
            # here would mangle ``.claude/.framework-version`` into
            # ``claude/.framework-version`` and break the marker check.
            # ``removeprefix`` is the right tool.
            names = {m.name.removeprefix("./") for m in tar.getmembers() if m.isfile()}
    except Exception as exc:
        return f"Could not read uploaded tarball: {exc}"

    missing = []
    for marker in _REQUIRED_ARTIFACT_MARKERS:
        if not any(n == marker or n.endswith("/" + marker) for n in names):
            missing.append(marker)
    if missing:
        return (
            "Missing required framework artifacts: " + ", ".join(missing) + ". "
            "Run `corectl test update --apply` then re-upload."
        )
    return None


def _extract_stage_metadata(db, test_package_id: str, file_bytes: bytes, manifest_version: str):
    """Extract structured stage metadata from the concord.yaml inside the archive.

    Both validation and manufacturing packages use the ``stages:`` dict.
    Optional fields per stage: directory (required), module, timeout_s,
    markers, hardware. Iteration order is the YAML insertion order, which
    becomes the platform's stageIndex. Idempotent — deletes existing
    records before re-creating.
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

        for idx, (name, cfg) in enumerate(manifest_data.get("stages", {}).items()):
            if not isinstance(cfg, dict):
                continue
            db.testpackagestage.create(data={
                "testPackageId": test_package_id,
                "name": name,
                "stageIndex": idx,
                "directory": cfg.get("directory"),
                "module": cfg.get("module"),
                "timeoutS": cfg.get("timeout_s"),
                "markers": cfg.get("markers", []),
                "hardware": cfg.get("hardware", []),
            })

        logger.info("Extracted stage metadata for package %s (manifest %s)", test_package_id, manifest_version)
    except Exception as e:
        logger.warning("Failed to extract stage metadata for package %s: %s", test_package_id, e)


def _serialize_package_stage(s) -> dict:
    """Serialize a TestPackageStage DB record to an API response dict."""
    return {
        "id": s.id,
        "name": s.name,
        "stageIndex": s.stageIndex,
        "directory": s.directory,
        "module": s.module,
        "timeoutS": s.timeoutS,
        "markers": s.markers if s.markers else [],
        "hardware": s.hardware if getattr(s, "hardware", None) else [],
    }


def _serialize_test_package(tp: Any) -> dict:
    """Serialize a TestPackage DB record to an API response dict."""
    fixture_design = getattr(tp, "fixtureDesign", None)
    data = {
        "id": tp.id,
        "productId": tp.productId,
        "boardRevisionId": getattr(tp, "boardRevisionId", None),
        "fixtureDesignId": fixture_design.id if fixture_design else None,
        "version": tp.version,
        "type": tp.type,
        "status": tp.status,
        "frameworkVersion": tp.frameworkVersion,
        "testCount": tp.testCount,
        "manifestVersion": getattr(tp, "manifestVersion", "1.0"),
        "message": getattr(tp, "message", None),
        "gitSha": getattr(tp, "gitSha", None),
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
    if hasattr(tp, "fixtureDesign") and tp.fixtureDesign:
        fd = tp.fixtureDesign
        data["fixtureDesign"] = {
            "id": fd.id,
            "name": fd.name,
            "revision": fd.revision,
            "type": getattr(fd, "type", None),
        }
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
    upload_message = (manifest.get("message") or "").strip() or None
    git_sha = (manifest.get("gitSha") or "").strip() or None
    notes = manifest.get("notes")
    manifest_version = (manifest.get("manifestVersion") or "1.0").strip()

    db = get_db_client()

    # Resolve board revision from manifest
    board_name = manifest.get("product", {}).get("board") or manifest.get("product", {}).get("name")
    board_revision_id = None
    if board_name:
        board_rev = db.boardrevision.find_first(
            where={
                "board": {"productId": product.id},
                "OR": [{"ckBoardsName": board_name}, {"version": board_name}],
            }
        )
        if board_rev:
            board_revision_id = board_rev.id

    # Read file and compute hash
    file_data = package_file.read()
    size_bytes = len(file_data)
    manifest_hash = hashlib.sha256(manifest_raw.encode()).hexdigest()

    # Hard gate: every uploaded package MUST carry the framework artifact
    # markers. Drift / customization / older-corectl uploads all fail
    # here. See _REQUIRED_ARTIFACT_MARKERS for the list.
    artifact_error = _check_framework_artifacts(file_data)
    if artifact_error:
        return bad_request(artifact_error)

    # ── Two-phase commit ──
    #
    # Phase 1: cheap duplicate check + create a placeholder row with
    #   status=UPLOADING. Cheap because it doesn't read the request body
    #   beyond the manifest, and atomic against concurrent uploaders
    #   thanks to the ``(productId, version, type)`` unique-by-business-rule
    #   the API enforces. The placeholder row owns the slot — a
    #   simultaneous second upload of the same version sees the
    #   placeholder and 409s.
    #
    # Phase 2: MinIO put. On success, flip status to DEVELOPMENT (or
    #   RELEASED) and stamp the storageKey. On failure, the row stays in
    #   UPLOADING; retention reaps it after the upload window closes.
    #   Compared to the previous "MinIO first → DB second" order, this
    #   never produces an orphan blob with no DB row.

    existing = db.testpackage.find_first(
        where={
            "productId": product.id,
            "version": version,
            "type": package_type,
        }
    )
    if existing:
        # Stuck UPLOADING placeholder from a prior failed upload? Reuse
        # it: same version slot, same content (the operator wouldn't be
        # retrying the upload otherwise), and the row is the orphan
        # marker we'd otherwise reap. Anything DEVELOPMENT/RELEASED is a
        # genuine duplicate.
        if getattr(existing, "status", None) == "UPLOADING":
            tp = existing
        else:
            return conflict(
                f"Test package version '{version}' already exists. "
                f"Re-run corectl upload to generate a fresh dev version."
            )
    else:
        tp = db.testpackage.create(
            data={
                "productId": product.id,
                "version": version,
                "type": package_type,
                "status": "UPLOADING",
                "storageKey": None,
                "frameworkVersion": framework_version,
                "manifestHash": manifest_hash,
                "testCount": test_count,
                "manifestVersion": manifest_version,
                "message": upload_message,
                "gitSha": git_sha,
                "notes": notes,
                "boardRevisionId": board_revision_id,
            },
        )

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
        # Leave the placeholder row in UPLOADING for retention to clean
        # up — operators can also delete it explicitly via the UI/API.
        return internal_error("Failed to upload test package")

    # Phase 2 complete: stamp the storageKey but keep status=UPLOADING
    # until every dependent row (testCount, TestBedDesign, stages) is
    # written AND the joined re-fetch succeeds. Flipping the status
    # earlier — as a previous version of this code did — meant any
    # failure between the flip and the final fetch left a public-but-
    # half-written package in the DB (stuck TestBedDesign in pickers,
    # missing stages, etc.). Now any failure leaves the row in UPLOADING
    # for the retention reaper, and the CASCADE on TestPackage drops
    # TestBedDesign + TestPackageStage rows with it.
    db.testpackage.update(
        where={"id": tp.id},
        data={"storageKey": object_key},
    )

    # testCount comes from counting test_*.py files in the tarball — the
    # manifest is not authoritative because authors don't keep it in sync.
    # If extraction returns 0, the package legitimately has no test files
    # and the UI should show that honestly. Log when this happens so it's
    # not silent.
    extracted_count = _extract_test_count(file_data) or 0
    if not extracted_count:
        logger.warning(
            "Test package %s has 0 test files in archive — testCount left at 0.",
            tp.id,
        )
    _extract_testbed_designs(file_data, tp.id, status, product.id, package_type)
    _extract_stage_metadata(db, tp.id, file_data, manifest_version)

    # Re-fetch with the joined relations. Doing this BEFORE the status
    # flip means a schema/DB drift (e.g., a missing migration on a joined
    # column) surfaces here, while the row is still UPLOADING — the
    # retention reaper will clean it up and no orphaned design ever
    # reaches the picker.
    tp = db.testpackage.find_unique(
        where={"id": tp.id},
        include={"packageStages": True, "fixtureDesign": True},
    )

    # Final commit: testCount + status flip in one update. From this
    # point the package is publicly visible; everything before it stayed
    # gated behind status=UPLOADING.
    db.testpackage.update(
        where={"id": tp.id},
        data={"status": status, "testCount": extracted_count},
    )
    tp.status = status
    tp.testCount = extracted_count

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
    type_filter = request.args.get("type")
    if type_filter:
        type_filter = type_filter.strip().upper()
        if type_filter in ("VALIDATION", "MANUFACTURING"):
            where["type"] = type_filter

    board_revision_id = request.args.get("boardRevisionId")
    if board_revision_id:
        where["boardRevisionId"] = board_revision_id

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    total = db.testpackage.count(where=where)
    packages = db.testpackage.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"packageStages": True, "fixtureDesign": True},
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


# ── Get Single ─────────────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_VIEW)
def get_test_package(product_id: str, package_id: str):
    """GET /v2/products/<product_id>/test-packages/<package_id> — get a single test package."""
    product, err = _resolve_product(product_id)
    if err:
        return err

    db = get_db_client()
    tp = db.testpackage.find_first(
        where={"id": package_id, "productId": product.id},
        include={"packageStages": True, "fixtureDesign": True},
    )
    if not tp:
        return not_found(f"Test package '{package_id}' not found")

    return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200


# ── Delete ─────────────────────────────────────────────────────


@require_permissions(Permissions.VALIDATION_MANAGE)
def delete_test_package(product_id: str, package_id: str):
    """DELETE /v2/products/<product_id>/test-packages/<package_id> — delete a test package."""
    product, err = _resolve_product(product_id)
    if err:
        return err

    db = get_db_client()
    tp = db.testpackage.find_first(
        where={"id": package_id, "productId": product.id},
    )
    if not tp:
        return not_found(f"Test package '{package_id}' not found")

    if tp.status == "RELEASED":
        return conflict("Cannot delete released packages. They are immutable.")

    # Block deletion if any test runs reference this package
    run_count = db.testrun.count(where={"testPackageId": tp.id})
    if run_count > 0:
        return conflict(f"Cannot delete: package is referenced by {run_count} test run(s)")

    # Delete from MinIO (best-effort — proceed with DB deletion even on failure)
    try:
        storage = get_storage_client()
        bucket = get_bucket_name()
        storage.remove_object(bucket, tp.storageKey)
    except Exception as e:
        logger.warning("Failed to delete MinIO object %s: %s", tp.storageKey, e)

    # Delete related records and the package itself
    db.testpackagestage.delete_many(where={"testPackageId": tp.id})
    db.testpackage.delete(where={"id": tp.id})

    log_audit("testPackage.delete", "TestPackage", tp.id, {
        "productId": product.id,
        "version": tp.version,
        "type": tp.type,
    })

    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


# ── Release (promote DEVELOPMENT → RELEASED) ─────────────────


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

    # Optional inputs from request body
    body = request.get_json(silent=True) or {}
    notes = body.get("notes")

    # Released version: caller can pass an explicit semver (e.g. "1.2.0").
    # Otherwise strip the misleading "dev-" prefix from the current version
    # so the released label drops a notion that no longer applies. The
    # epoch suffix is kept — it makes the release uniquely identifiable
    # without colliding with other clean-tree releases of the same SHA.
    explicit_version = (body.get("releasedVersion") or "").strip()
    if explicit_version:
        released_version = explicit_version
    else:
        released_version = tp.version[len("dev-"):] if tp.version.startswith("dev-") else tp.version

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
        include={"packageStages": True, "fixtureDesign": True},
    )

    # The fixture design is extracted at upload time (per-package ownership)
    # so on release we just propagate the status. If a dev upload didn't
    # have a fixtures dir, no design exists — that's fine, nothing to update.
    if tp.fixtureDesign is not None:
        db.fixturedesign.update(
            where={"id": tp.fixtureDesign.id},
            data={"status": "RELEASED"},
        )

    # Bind this package to every matching ProductStageConfig as its
    # blessed release. Validation auto-runs gate on this binding; without
    # it a stage stays unschedulable. Match by product + stage type +
    # board revision (if the package targeted one), so a package built
    # for board "alpha_b0" doesn't accidentally bind to "alpha_b1" stages.
    stage_where: dict = {"productId": product.id, "type": tp.type}
    if tp.boardRevisionId:
        stage_where["boardRevisionId"] = tp.boardRevisionId
    bound_count = db.productstageconfig.update_many(
        where=stage_where,
        data={"releasedTestPackageId": tp.id},
    )

    tp = db.testpackage.find_unique(
        where={"id": tp.id},
        include={"packageStages": True, "fixtureDesign": True},
    )

    fixture_design_id = tp.fixtureDesign.id if tp.fixtureDesign is not None else None
    log_audit("testPackage.release", "TestPackage", tp.id, {
        "productId": product.id,
        "type": tp.type,
        "releasedVersion": released_version,
        "fixtureDesignId": fixture_design_id,
        "stageBindings": bound_count,
        "previousStatus": "DEVELOPMENT",
    })

    return jsonify(ApiResponse.ok(_serialize_test_package(tp)).to_dict()), 200
