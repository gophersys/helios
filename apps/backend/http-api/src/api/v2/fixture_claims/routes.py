"""HTTP routes for /v2/fixture-claims (DEV_HOLD lifecycle).

Endpoint cheat-sheet:

    POST   /v2/fixture-claims            → create (fixture- or node-mode)
    POST   /v2/fixture-claims/<id>/heartbeat
    POST   /v2/fixture-claims/<id>/release
    GET    /v2/fixture-claims            → list, filtered by user/status/fixture
    GET    /v2/fixture-claims/<id>       → fetch one

Every mutating endpoint is guarded by an explicit permission check and
emits an ``AuditLog`` row via ``log_audit``. Heartbeat is the exception —
by design it is too hot to audit (one row per minute per developer).

The codebase ``@require_permissions(*perms)`` decorator requires ALL of
the listed permissions; the claim endpoints want ANY-of semantics (a
developer with only ``VALIDATION_RUN`` should be able to claim a
validation fixture, and a manufacturing engineer with
``MANUFACTURING_MANAGE`` should be able to claim a manufacturing one).
So we run ``@require_auth`` (decorator-style) for the JWT plumbing and
then call ``_check_any_permission`` to do the precise gate by hand.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, g, jsonify, request

from src.api.v2.fixture_claims.service import (
    create_claim,
    heartbeat_claim,
    is_validation_target,
    provision_mtibs_for_claim,
    release_claim,
    serialize_claim,
    teardown_claim_mtibs,
)
from src.api.v2.fixture_claims.validators import (
    CreateClaimRequest,
    ListClaimsQuery,
)
from src.lib.audit import log_audit
from src.lib.decorators import require_auth
from src.lib.errors import bad_request, conflict, forbidden, not_found
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse, ErrorDetail
from src.services.database.prisma import get_db_client
from src.services.fixtures.reservation import (
    REASON_CLAIM,
    REASON_MFG_SESSION,
    REASON_TEST_RUN,
    are_nodes_busy,
    is_fixture_busy,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# POST /v2/fixture-claims — create
# ---------------------------------------------------------------------------


@require_auth
def create():
    """Create a new ACTIVE FixtureClaim. Permission depends on target type.

    A claim targeting VALIDATION-typed nodes/fixture needs ``VALIDATION_RUN``;
    a claim targeting MANUFACTURING-typed hardware needs ``MANUFACTURING_MANAGE``.
    """
    body = request.get_json(silent=True) or {}
    req, err = CreateClaimRequest.from_json(body)
    if err:
        return bad_request(err)

    db = get_db_client()
    user = g.current_user or {}
    user_id = user.get("sub")
    if not user_id:
        return forbidden("Missing user identity")

    # ── Existence checks ──
    if req.fixtureId:
        fixture = db.fixture.find_unique(where={"id": req.fixtureId})
        if fixture is None:
            return not_found("Fixture not found")

    if req.nodes:
        node_ids = [n.nodeId for n in req.nodes]
        loaded = db.node.find_many(where={"id": {"in": node_ids}})
        loaded_ids = {n.id for n in loaded}
        missing = [nid for nid in node_ids if nid not in loaded_ids]
        if missing:
            return not_found(f"Node not found: {missing[0]}")

    # ── Permission check (depends on target) ──
    needs_validation = is_validation_target(db, req)
    required = Permissions.VALIDATION_RUN if needs_validation else Permissions.MANUFACTURING_MANAGE
    if not _user_has_permission(db, user, required):
        return forbidden("Forbidden")

    # ── Reservation gate ──
    if req.fixtureId:
        busy, reason = is_fixture_busy(db, req.fixtureId)
        if busy:
            return conflict(_reason_message(reason, fixture_id=req.fixtureId))
    else:
        busy, reason, holding_node = are_nodes_busy(
            db, [n.nodeId for n in req.nodes],
        )
        if busy:
            return conflict(_reason_message(reason, node_id=holding_node))

    # ── Create ──
    claim = create_claim(db, user_id=user_id, req=req)

    log_audit(
        "fixture.claim.create",
        "FixtureClaim",
        claim.id,
        {
            "fixtureId": req.fixtureId,
            "nodeIds": [n.nodeId for n in req.nodes],
            "ttlSeconds": req.ttlSeconds,
            "description": req.description,
        },
    )

    # ── Provision mtib-server on each held node ──
    # The point of DEV_HOLD: claiming a node means it's ready for dev. We
    # call create_mtib_deployment for each held node (idempotent: returns
    # the existing deploy name on 409). If anything fails, release the
    # claim so the caller doesn't get a half-broken lease they have to
    # debug.
    provisioning = provision_mtibs_for_claim(claim)
    if provisioning["failed"]:
        teardown_claim_mtibs(claim)
        release_claim(db, claim)
        log_audit(
            "fixture.claim.release",
            "FixtureClaim",
            claim.id,
            {"reason": "provisioning_failed", "failedNodes": provisioning["failed"]},
        )
        return jsonify(
            ApiResponse.error(ErrorDetail(
                code="MTIB_PROVISIONING_FAILED",
                message=(
                    "Claim was released because mtib-server failed to deploy on: "
                    + ", ".join(provisioning["failed"])
                ),
            )).to_dict()
        ), 502

    if provisioning["created"]:
        log_audit(
            "mtib.deployment.create",
            "FixtureClaim",
            claim.id,
            {
                "claimId": claim.id,
                "createdOnNodes": provisioning["created"],
                "reusedOnNodes": provisioning["reused"],
            },
        )

    return jsonify(ApiResponse.created(serialize_claim(claim)).to_dict()), 201


# ---------------------------------------------------------------------------
# POST /v2/fixture-claims/<id>/heartbeat
# ---------------------------------------------------------------------------


@require_auth
def heartbeat(claim_id: str):
    """Extend the claim's sliding TTL. Returns 410 if claim is not ACTIVE."""
    db = get_db_client()
    claim = db.fixtureclaim.find_unique(where={"id": claim_id})
    if claim is None:
        return not_found("Fixture claim not found")

    if not _caller_can_act_on_claim(db, claim):
        return forbidden("Forbidden")

    if claim.status != "ACTIVE":
        return _gone(f"Claim is {claim.status}; heartbeat ignored")

    updated = heartbeat_claim(db, claim)
    # No audit log — heartbeats are once-a-minute and would drown the table.
    return jsonify(ApiResponse.ok({
        "id": updated.id,
        "lastHeartbeatAt": _iso(updated.lastHeartbeatAt),
        "expiresAt": _iso(updated.expiresAt),
    }).to_dict()), 200


# ---------------------------------------------------------------------------
# POST /v2/fixture-claims/<id>/release
# ---------------------------------------------------------------------------


@require_auth
def release(claim_id: str):
    """Finalize a claim. Idempotent — releasing a non-ACTIVE claim is a no-op."""
    db = get_db_client()
    claim = db.fixtureclaim.find_unique(
        where={"id": claim_id},
        include={
            "claimedNodes": {"include": {"node": True}},
            "fixture": {
                "include": {
                    "slots": {
                        "where": {"active": True},
                        "include": {"node": True},
                    },
                },
            },
        },
    )
    if claim is None:
        return not_found("Fixture claim not found")

    if not _caller_can_act_on_claim(db, claim):
        return forbidden("Forbidden")

    was_active = claim.status == "ACTIVE"
    updated = release_claim(db, claim)

    if was_active:
        log_audit(
            "fixture.claim.release",
            "FixtureClaim",
            updated.id,
            {"reason": "explicit"},
        )
        # Tear down only the mtib deployments we created on claim — fixture-
        # bound and standalone-node deployments (claim-id label empty) survive.
        deleted = teardown_claim_mtibs(updated)
        if deleted:
            log_audit(
                "mtib.deployment.delete",
                "FixtureClaim",
                updated.id,
                {"claimId": updated.id, "deletedDeployments": deleted},
            )

    return jsonify(ApiResponse.ok(serialize_claim(updated)).to_dict()), 200


# ---------------------------------------------------------------------------
# GET /v2/fixture-claims — list
# ---------------------------------------------------------------------------


@require_auth
def list_claims():
    """List FixtureClaims matching the query filters.

    Defaults:
      * userId = caller (so a developer's CLI sees just their own claims)
      * status = ACTIVE
    """
    db = get_db_client()
    user = g.current_user or {}
    if not _user_has_permission_any(
        db, user, (Permissions.VALIDATION_VIEW, Permissions.MANUFACTURING_MANAGE),
    ):
        return forbidden("Forbidden")

    q = ListClaimsQuery.from_args(request.args)
    user_id = q.userId or user.get("sub")

    where: dict = {}
    if user_id:
        where["userId"] = user_id
    where["status"] = q.status or "ACTIVE"
    if q.fixtureId:
        where["fixtureId"] = q.fixtureId

    rows = db.fixtureclaim.find_many(
        where=where,
        order={"acquiredAt": "desc"},
        include={
            "claimedNodes": {"include": {"node": True}},
            "fixture": {
                "include": {
                    "slots": {
                        "where": {"active": True},
                        "include": {"node": True},
                    },
                },
            },
        },
    )

    # Bindings include an MTIB host resolution which hits K8s — skip on
    # list to avoid one round-trip per row. Callers that need bindings
    # call the detail endpoint.
    claims = [serialize_claim(c, include_bindings=False) for c in rows]
    return jsonify(ApiResponse.ok({"claims": claims}).to_dict()), 200


# ---------------------------------------------------------------------------
# GET /v2/fixture-claims/<id> — fetch
# ---------------------------------------------------------------------------


@require_auth
def get(claim_id: str):
    """Fetch one claim by id."""
    db = get_db_client()
    user = g.current_user or {}
    if not _user_has_permission_any(
        db, user, (Permissions.VALIDATION_VIEW, Permissions.MANUFACTURING_MANAGE),
    ):
        return forbidden("Forbidden")

    claim = db.fixtureclaim.find_unique(
        where={"id": claim_id},
        include={
            "claimedNodes": {"include": {"node": True}},
            "fixture": {
                "include": {
                    "slots": {
                        "where": {"active": True},
                        "include": {"node": True},
                    },
                },
            },
        },
    )
    if claim is None:
        return not_found("Fixture claim not found")

    return jsonify(ApiResponse.ok(serialize_claim(claim)).to_dict()), 200


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_fixture_claim_routes(api: Blueprint):
    """Bind /v2/fixture-claims to the v2 Blueprint."""
    api.add_url_rule(
        "/fixture-claims",
        endpoint="list_fixture_claims",
        view_func=list_claims,
        methods=["GET"],
    )
    api.add_url_rule(
        "/fixture-claims",
        endpoint="create_fixture_claim",
        view_func=create,
        methods=["POST"],
    )
    api.add_url_rule(
        "/fixture-claims/<claim_id>",
        endpoint="get_fixture_claim",
        view_func=get,
        methods=["GET"],
    )
    api.add_url_rule(
        "/fixture-claims/<claim_id>/heartbeat",
        endpoint="heartbeat_fixture_claim",
        view_func=heartbeat,
        methods=["POST"],
    )
    api.add_url_rule(
        "/fixture-claims/<claim_id>/release",
        endpoint="release_fixture_claim",
        view_func=release,
        methods=["POST"],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _user_has_permission(db, user: dict, required: str) -> bool:
    """True when the user can be granted ``required``.

    Admin and Maintainer bypass the permission set check (mirrors the
    decorator). For OPERATOR and DEVELOPER, the permission must appear in
    their ``PermissionSet``.
    """
    effective_role = getattr(g, "effective_role", None) or user.get("role", "DEVELOPER")
    if effective_role in ("ADMIN", "MAINTAINER"):
        return True
    perm_set_id = user.get("permissionSetId")
    if not perm_set_id:
        return False
    perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
    permissions = getattr(perm_set, "permissions", None) if perm_set else None
    if not permissions:
        return False
    return required in permissions


def _user_has_permission_any(db, user: dict, candidates: tuple) -> bool:
    """True when the user can be granted at least one of ``candidates``."""
    effective_role = getattr(g, "effective_role", None) or user.get("role", "DEVELOPER")
    if effective_role in ("ADMIN", "MAINTAINER"):
        return True
    perm_set_id = user.get("permissionSetId")
    if not perm_set_id:
        return False
    perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
    permissions = getattr(perm_set, "permissions", None) if perm_set else None
    if not permissions:
        return False
    return any(c in permissions for c in candidates)


def _caller_can_act_on_claim(db, claim) -> bool:
    """True when the request user is the claim owner, has SYSTEM_VIEW,
    or is an ADMIN/MAINTAINER. Used by heartbeat / release."""
    user = getattr(g, "current_user", None) or {}
    if user.get("sub") == claim.userId:
        return True
    effective_role = getattr(g, "effective_role", None) or user.get("role")
    if effective_role in ("ADMIN", "MAINTAINER"):
        return True
    perm_set_id = user.get("permissionSetId")
    if not perm_set_id:
        return False
    perm_set = db.permissionset.find_unique(where={"id": perm_set_id})
    perms = getattr(perm_set, "permissions", None) if perm_set else None
    return bool(perms and Permissions.SYSTEM_VIEW in perms)


def _reason_message(
    reason: Optional[str],
    *,
    fixture_id: Optional[str] = None,
    node_id: Optional[str] = None,
) -> str:
    """Map an internal reason code to a human-readable 409 message."""
    if reason == REASON_TEST_RUN:
        return (
            f"Fixture {fixture_id} has an active test run"
            if fixture_id else
            f"Node {node_id} is wired to a fixture with an active test run"
        )
    if reason == REASON_MFG_SESSION:
        return (
            f"Fixture {fixture_id} has an active manufacturing session"
            if fixture_id else
            f"Node {node_id} is wired to a fixture with an active manufacturing session"
        )
    if reason == REASON_CLAIM:
        return (
            "Fixture is already held by an active DEV_HOLD claim"
            if fixture_id else
            f"Node {node_id} is already held by an active DEV_HOLD claim"
        )
    return "Resource is busy"


def _gone(message: str):
    """410 Gone — used when heartbeating a non-ACTIVE claim."""
    resp = ApiResponse.error(ErrorDetail(message=message))
    return jsonify(resp.to_dict()), 410


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()
