import logging
import math
from typing import Any

from flask import g, jsonify, request

from config.env import env_config
from src.lib.audit import log_audit
from src.lib.decorators import require_permissions
from src.lib.errors import bad_request, conflict, internal_error, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from .shared import serialize_target as _serialize_target
from .types import ProductCreateRequest, ProductUpdateRequest

logger = logging.getLogger(__name__)


def _collect_targets(p: Any) -> list:
    """Collect all ProductTargets from product.boards[].revisions[].targets[]."""
    targets = []
    if hasattr(p, "boards") and p.boards:
        for b in p.boards:
            if hasattr(b, "revisions") and b.revisions:
                for r in b.revisions:
                    if hasattr(r, "targets") and r.targets:
                        targets.extend(r.targets)
    return targets


def _serialize_product(p: Any, include_children: bool = False) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "active": p.active,
        "fwRepoSlug": getattr(p, "fwRepoSlug", None),
        "mfgFwRepoSlug": getattr(p, "mfgFwRepoSlug", None),
        "builderImage": getattr(p, "builderImage", None),
        # Derived fields for git-poller and build service
        "repoSshUrl": f"git@bitbucket.org:corekinect/{p.fwRepoSlug}.git" if getattr(p, "fwRepoSlug", None) else None,
        "mfgRepoSshUrl": f"git@bitbucket.org:corekinect/{p.mfgFwRepoSlug}.git" if getattr(p, "mfgFwRepoSlug", None) else None,
        "buildConfig": p.buildConfig,
        "metadata": p.metadata,
        "createdAt": p.createdAt.isoformat(),
        "updatedAt": p.updatedAt.isoformat(),
    }
    # Targets live on BoardRevision — collect from boards→revisions→targets
    data["targets"] = [_serialize_target(t) for t in _collect_targets(p)]
    if hasattr(p, "boards") and p.boards is not None:
        data["boardCount"] = len(p.boards)
        if include_children:
            data["boards"] = [_serialize_board_summary(b) for b in p.boards]
    if hasattr(p, "firmwareSets") and p.firmwareSets is not None:
        data["firmwareSetCount"] = len(p.firmwareSets)
        if include_children:
            data["firmwareSets"] = [_serialize_firmware_set(s) for s in p.firmwareSets]
    if hasattr(p, "_count") and p._count is not None:
        data["sessionCount"] = getattr(p._count, "sessions", 0)
        data["testCount"] = getattr(p._count, "tests", 0)
    # Stage config summary (always included for card display)
    if hasattr(p, "stageConfigs") and p.stageConfigs is not None:
        stages = p.stageConfigs
        data["stageConfigs"] = [
            {
                "id": s.id,
                "stage": s.stage,
                "name": s.name,
                "enabled": s.enabled,
                "triggerTypes": getattr(s, "triggerTypes", []) or [],
                "watchBranch": getattr(s, "watchBranch", None),
                "boardRevisionId": getattr(s, "boardRevisionId", None),
                "boardRevision": {
                    "id": s.boardRevision.id,
                    "version": s.boardRevision.version,
                    "ckBoardsName": getattr(s.boardRevision, "ckBoardsName", None),
                    "status": getattr(s.boardRevision, "status", None),
                } if hasattr(s, "boardRevision") and s.boardRevision else None,
                "signingKeyId": getattr(s, "signingKeyId", None),
            }
            for s in sorted(stages, key=lambda x: x.stage)
        ]
        data["enabledStageCount"] = sum(1 for s in stages if s.enabled)
    # Revision summary (always included for card display)
    if hasattr(p, "boards") and p.boards:
        revisions = []
        for board in p.boards:
            if hasattr(board, "revisions") and board.revisions:
                for rev in board.revisions:
                    revisions.append({
                        "version": rev.version,
                        "ckBoardsName": rev.ckBoardsName,
                        "status": rev.status,
                        "targetCount": len(rev.targets) if hasattr(rev, "targets") and rev.targets else 0,
                    })
        data["revisions"] = revisions
    return data


def _serialize_board_summary(b: Any) -> dict:
    result = {
        "id": b.id,
        "productId": b.productId,
        "name": b.name,
        "ckBoardsFamily": getattr(b, "ckBoardsFamily", None),
        "vendor": getattr(b, "vendor", "corekinect"),
        "description": b.description,
        "active": b.active,
        "createdAt": b.createdAt.isoformat(),
        "updatedAt": b.updatedAt.isoformat(),
    }
    if hasattr(b, "revisions") and b.revisions is not None:
        result["revisionCount"] = len(b.revisions)
        result["revisions"] = [_serialize_board_revision(r) for r in b.revisions]
    return result


def _serialize_board_revision(r: Any) -> dict:
    result = {
        "id": r.id,
        "boardId": r.boardId,
        "version": r.version,
        "ckBoardsName": getattr(r, "ckBoardsName", None),
        "socs": getattr(r, "socs", []),
        "deviceType": getattr(r, "deviceType", None),
        "deviceVariant": getattr(r, "deviceVariant", None),
        "status": r.status,
        "notes": r.notes,
        "createdAt": r.createdAt.isoformat(),
        "updatedAt": r.updatedAt.isoformat(),
    }
    if hasattr(r, "targets") and r.targets is not None:
        result["targets"] = [_serialize_target(t) for t in r.targets]
    else:
        result["targets"] = []
    return result


def _serialize_firmware_set(s: Any) -> dict:
    data = {
        "id": s.id,
        "productId": s.productId,
        "version": s.version,
        "releaseTrack": getattr(s, "releaseTrack", "bench"),
        "isManufacturing": getattr(s, "isManufacturing", False),
        "source": getattr(s, "source", "upload"),
        "status": getattr(s, "status", "active"),
        "createdAt": s.createdAt.isoformat(),
        "updatedAt": s.updatedAt.isoformat(),
    }
    return data


# ── Products CRUD ─────────────────────────────────────────


@require_permissions(Permissions.PRODUCTS_VIEW)
def list_products():
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    # Filter by product access for Developer/Operator roles
    # Uses effective_role (set by require_permissions → _resolve_effective_role)
    # so the X-View-As-Role header works for product filtering too.
    where = {}
    if env_config.AUTH_ENABLED:
        user = getattr(g, "current_user", None)
        if user:
            effective_role = getattr(g, "effective_role", user.get("role", "DEVELOPER"))
            if effective_role not in ("ADMIN", "MAINTAINER"):
                # Only show products the user has explicit access to
                access_entries = db.productaccess.find_many(
                    where={"userId": user["sub"]},
                )
                accessible_ids = [a.productId for a in access_entries]
                where = {"id": {"in": accessible_ids}}

    total = db.product.count(where=where)
    products = db.product.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={
            "boards": {"include": {"revisions": {"include": {"targets": True}}}},
            "firmwareSets": True,
            "stageConfigs": True,
        },
    )
    return jsonify(ApiResponse.ok({
        "data": [_serialize_product(p) for p in products],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def create_product():
    data, error = ProductCreateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()

    existing = db.product.find_unique(where={"name": data.name})
    if existing:
        return conflict("Product with this name already exists")

    # Check slug uniqueness if provided
    if data.slug:
        existing_slug = db.product.find_unique(where={"slug": data.slug})
        if existing_slug:
            return conflict("Product with this slug already exists")

    from database import Json

    create_data = {
        "name": data.name,
        "description": data.description,
        "active": data.active,
    }
    if data.slug is not None:
        create_data["slug"] = data.slug
    if data.fwRepoSlug is not None:
        create_data["fwRepoSlug"] = data.fwRepoSlug
    if data.mfgFwRepoSlug is not None:
        create_data["mfgFwRepoSlug"] = data.mfgFwRepoSlug
    if data.buildConfig is not None:
        create_data["buildConfig"] = Json(data.buildConfig)
    if data.metadata is not None:
        create_data["metadata"] = Json(data.metadata)

    # Inline board creation from wizard
    if data.board:
        board_data = {
            "name": data.board.ckBoardsFamily,
            "ckBoardsFamily": data.board.ckBoardsFamily,
            "vendor": data.board.vendor,
        }
        if data.board.revisions:
            rev_creates = []
            for r in data.board.revisions:
                rev_data = {
                    "version": r["version"],
                    "ckBoardsName": r["ckBoardsName"],
                    "socs": r["socs"],
                }
                if r.get("deviceType") is not None:
                    rev_data["deviceType"] = r["deviceType"]
                if r.get("deviceVariant") is not None:
                    rev_data["deviceVariant"] = r["deviceVariant"]
                if r.get("targets"):
                    rev_data["targets"] = {
                        "create": [
                            {"role": t.role, "soc": t.soc, "appId": t.appId}
                            for t in r["targets"]
                        ],
                    }
                rev_creates.append(rev_data)
            board_data["revisions"] = {"create": rev_creates}
        create_data["boards"] = {"create": [board_data]}

    product = db.product.create(
        data=create_data,
        include={
            "boards": {"include": {"revisions": {"include": {"targets": True}}}},
            "firmwareSets": True,
        },
    )
    log_audit("product.create", "Product", product.id, {
        "name": data.name,
    })
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 201


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_product(product_id: str):
    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={
            "boards": {
                "order_by": {"name": "asc"},
                "include": {
                    "revisions": {
                        "order_by": {"version": "asc"},
                        "include": {"targets": True},
                    },
                },
            },
            "firmwareSets": {
                "order_by": {"createdAt": "desc"},
                "include": {
                    "builds": {"include": {"target": True}},
                    "boardRevision": True,
                },
            },
            "stageConfigs": {
                "order_by": {"stage": "asc"},
                "include": {"boardRevision": True},
            },
        },
    )
    if not product:
        return not_found("Product not found")
    return jsonify(ApiResponse.ok(_serialize_product(product, include_children=True)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def update_product(product_id: str):
    data, error = ProductUpdateRequest.from_json(request.get_json())
    if error:
        return bad_request(error)

    db = get_db_client()
    existing = db.product.find_unique(where={"id": product_id})
    if not existing:
        return not_found("Product not found")

    if data.name and data.name != existing.name:
        dup = db.product.find_unique(where={"name": data.name})
        if dup:
            return conflict("Product with this name already exists")

    # Check slug uniqueness if being changed
    if data._has_slug and data.slug and data.slug != existing.slug:
        dup_slug = db.product.find_unique(where={"slug": data.slug})
        if dup_slug:
            return conflict("Product with this slug already exists")

    update_data = data.to_update_data()

    product = db.product.update(
        where={"id": product_id},
        data=update_data,
        include={
            "boards": {"include": {"revisions": {"include": {"targets": True}}}},
            "firmwareSets": True,
        },
    )
    log_audit("product.update", "Product", product_id, {"name": existing.name, "changes": data.to_update_data()})
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def delete_product(product_id: str):
    db = get_db_client()
    existing = db.product.find_unique(where={"id": product_id})
    if not existing:
        return not_found("Product not found")

    # Check if product has sessions
    session_ref = db.session.find_first(where={"productId": product_id})
    if session_ref:
        return conflict("Cannot delete product: it has associated sessions")

    # Check if product has tests
    test_ref = db.test.find_first(where={"productId": product_id})
    if test_ref:
        return conflict("Cannot delete product: it has associated tests")

    db.product.delete(where={"id": product_id})
    log_audit("product.delete", "Product", product_id, {"name": existing.name})
    return jsonify(ApiResponse.ok({"deleted": True}).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_VIEW)
def get_product_by_slug(slug: str):
    """GET /v2/catalog/products/by-slug/<slug> — Find product by slug (for API consumers)."""
    db = get_db_client()
    product = db.product.find_first(
        where={"slug": slug},
        include={
            "boards": {"include": {"revisions": {"include": {"targets": True}}}},
            "stageConfigs": {"order_by": {"stage": "asc"}},
        },
    )
    if not product:
        return not_found(f"Product with slug '{slug}' not found")
    return jsonify(ApiResponse.ok(_serialize_product(product)).to_dict()), 200


@require_permissions(Permissions.PRODUCTS_MANAGE)
def sync_product_revisions(product_id: str):
    """POST /v2/products/<id>/sync-revisions — Sync hardware revisions from ck_boards repo.

    Discovers board revisions on the main branch of ck_boards and creates
    any that don't already exist in the database. Does not modify existing revisions.
    AppIDs are left at 0 for the user to fill in via the UI.
    """
    db = get_db_client()
    product = db.product.find_unique(
        where={"id": product_id},
        include={"boards": {"include": {"revisions": True}}},
    )
    if not product:
        return not_found("Product not found")

    board = product.boards[0] if product.boards else None
    if not board:
        return bad_request("Product has no board configured")

    from api.v2.products.board_discovery import get_ck_boards_service
    svc = get_ck_boards_service()
    if svc is None or not svc.is_ready:
        return internal_error("Board discovery service not configured")

    # Try main, then master (ck_boards uses master)
    detail = None
    for branch in ("main", "master"):
        try:
            detail = svc.discover_board_detail(board.ckBoardsFamily, branch)
            break
        except ValueError:
            continue
        except Exception:
            logger.exception("Failed to discover boards for %s on %s", board.ckBoardsFamily, branch)
    if detail is None:
        return not_found(f"Board family '{board.ckBoardsFamily}' not found in ck_boards repo")

    existing_versions = {r.version for r in (board.revisions or [])}
    discovered_revisions = detail.get("revisions", []) if isinstance(detail, dict) else []

    added = []
    for rev_data in discovered_revisions:
        version = rev_data.get("version", "")
        if not version or version in existing_versions:
            continue

        ck_name = rev_data.get("ckBoardsName") or f"{board.ckBoardsFamily}_{version.lower()}"
        socs = rev_data.get("socs", [])

        try:
            new_rev = db.boardrevision.create(data={
                "boardId": board.id,
                "version": version,
                "ckBoardsName": ck_name,
                "socs": socs,
                "status": "DRAFT",
                "notes": "Auto-discovered from ck_boards main branch",
            })
            for i, soc in enumerate(socs):
                role = "app" if i == 0 else "comms" if i == 1 else f"target_{i}"
                try:
                    db.producttarget.create(data={
                        "boardRevisionId": new_rev.id,
                        "role": role,
                        "soc": soc,
                        "appId": 0,
                    })
                except Exception:
                    pass
            added.append({"version": version, "ckBoardsName": ck_name, "socs": socs})
            log_audit("product.revision.sync", "BoardRevision", new_rev.id,
                      {"productId": product_id, "version": version, "source": "ck_boards"})
        except Exception:
            logger.exception("Failed to create revision %s for %s", version, product_id)

    return jsonify(ApiResponse.ok({
        "synced": len(added),
        "added": added,
        "existing": list(existing_versions),
    }).to_dict()), 200
