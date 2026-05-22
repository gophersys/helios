"""Business logic for DEV_HOLD fixture claims.

Pure, side-effect-free where possible — the route handlers in ``routes.py``
own request parsing, permission checks, audit logging, and HTTP responses.
This module owns the lifecycle of the FixtureClaim row plus the
node-address resolution that turns slot bindings into MTIB host strings.

Lifecycle summary:

    create  → row inserted with status=ACTIVE, expiresAt = now+ttl,
              hardCeilingAt = now+8h
    heartbeat → bumps lastHeartbeatAt, recomputes expiresAt (capped to
                hardCeilingAt). 410 from the route layer if the row is
                no longer ACTIVE.
    release → sets status=RELEASED, releasedAt=now. Idempotent: a
              second release returns the same payload.
    expire  → background sweeper transitions ACTIVE → EXPIRED past
              expiresAt, ACTIVE → ABANDONED past hardCeilingAt. The
              route layer never does this itself — the sweeper is the
              only writer for those terminal states.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.api.v2.fixture_claims.validators import (
    HARDCEILING_TTL_SECONDS,
    HEARTBEAT_WINDOW_SECONDS,
    CreateClaimRequest,
)
from src.services.kubernetes.address_resolver import resolve_node_addresses
from src.services.kubernetes.mtib_deployments import (
    create_mtib_deployment,
    delete_mtib_deployments_for_claim,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission classification
# ---------------------------------------------------------------------------


def is_validation_target(db, req: CreateClaimRequest) -> bool:
    """Decide which permission gates the create — VALIDATION_RUN vs MANUFACTURING_MANAGE.

    A claim is "validation-typed" if the target fixture is VALIDATION, or
    if all of the requested nodes are bound to validation slots. Anything
    else (manufacturing fixture, manufacturing nodes, or unbound nodes) is
    treated as manufacturing. The split matches the existing permission
    sets: validation:run is what test authors carry, manufacturing:manage
    is what mfg ops engineers carry.
    """
    if req.fixtureId:
        fixture = db.fixture.find_unique(where={"id": req.fixtureId})
        if fixture is None:
            # Caller surfaces 404 next; default to validation so a
            # 401/403 doesn't beat the 404 in the error chain.
            return True
        return getattr(fixture, "type", None) == "VALIDATION"

    node_ids = [n.nodeId for n in req.nodes]
    if not node_ids:
        return True

    nodes = db.node.find_many(where={"id": {"in": node_ids}})
    # All nodes must be VALIDATION-type — a single MANUFACTURING node
    # bumps the requirement to MANUFACTURING_MANAGE.
    if not nodes:
        return True
    return all(getattr(n, "type", None) == "VALIDATION" for n in nodes)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_claim(
    db,
    user_id: str,
    req: CreateClaimRequest,
) -> Any:
    """Insert a FixtureClaim + ClaimedNode rows. Returns the created row.

    Caller is responsible for the reservation gate check and the perm
    check. We just write the row and return it with the relations
    needed by ``serialize_claim`` already eager-loaded.
    """
    now = datetime.now(timezone.utc)
    ttl = min(int(req.ttlSeconds), HARDCEILING_TTL_SECONDS)
    expires_at = now + timedelta(seconds=ttl)
    hard_ceiling_at = now + timedelta(seconds=HARDCEILING_TTL_SECONDS)
    # Sliding window clamp: expiresAt never exceeds the hard ceiling.
    if expires_at > hard_ceiling_at:
        expires_at = hard_ceiling_at

    data: dict = {
        "userId": user_id,
        "status": "ACTIVE",
        "acquiredAt": now,
        "lastHeartbeatAt": now,
        "expiresAt": expires_at,
        "hardCeilingAt": hard_ceiling_at,
    }
    if req.fixtureId:
        data["fixtureId"] = req.fixtureId
    if req.description:
        data["description"] = req.description
    if req.nodes:
        data["claimedNodes"] = {
            "create": [
                {"nodeId": n.nodeId, "label": n.label}
                for n in req.nodes
            ],
        }

    claim = db.fixtureclaim.create(
        data=data,
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
    return claim


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def heartbeat_claim(db, claim: Any) -> Any:
    """Bump ``lastHeartbeatAt`` and recompute ``expiresAt``.

    Returns the updated claim row. The caller is responsible for verifying
    the claim is still ACTIVE — see ``routes.heartbeat`` which returns 410
    otherwise.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=HEARTBEAT_WINDOW_SECONDS)
    hard_ceiling = claim.hardCeilingAt
    if hard_ceiling and expires_at > hard_ceiling:
        expires_at = hard_ceiling

    return db.fixtureclaim.update(
        where={"id": claim.id},
        data={"lastHeartbeatAt": now, "expiresAt": expires_at},
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


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------


def release_claim(db, claim: Any) -> Any:
    """Transition an ACTIVE claim to RELEASED. Idempotent: re-releasing
    a non-ACTIVE claim is a no-op and returns the row as-is.
    """
    if claim.status != "ACTIVE":
        return claim

    now = datetime.now(timezone.utc)
    return db.fixtureclaim.update(
        where={"id": claim.id},
        data={"status": "RELEASED", "releasedAt": now},
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


# ---------------------------------------------------------------------------
# MTIB provisioning — make dev claims "just work"
# ---------------------------------------------------------------------------


def _claimed_targets(claim: Any) -> list[tuple[Any, int]]:
    """Return ``[(node, slot_index), ...]`` for every node held by the claim.

    Fixture-mode claims walk the bound slots; node-mode claims walk
    ``claimedNodes``. Either way, missing nodes are silently dropped — the
    serializer surfaces those as ``mtibHost=None`` so callers can render
    partial state without us raising here.
    """
    targets: list[tuple[Any, int]] = []
    if getattr(claim, "fixtureId", None):
        fixture = getattr(claim, "fixture", None)
        if fixture is None:
            return targets
        for slot in (getattr(fixture, "slots", None) or []):
            node = getattr(slot, "node", None)
            if node is None:
                continue
            targets.append((node, getattr(slot, "slotIndex", 0) or 0))
        return targets

    for idx, cn in enumerate(getattr(claim, "claimedNodes", None) or []):
        node = getattr(cn, "node", None)
        if node is None:
            continue
        targets.append((node, idx))
    return targets


def _motion_enabled_for_node(node: Any) -> str:
    """Mirror the fixture/node-registration rule: VALIDATION → motion, else off.

    Matches ``_mtib_env_for_fixture`` in ``api/v2/fixtures/fixtures.py`` and
    ``_deploy_mtib_for_node`` in ``api/v2/nodes/nodes.py``. Keep all three in
    sync if the rule ever changes.
    """
    return "true" if getattr(node, "type", None) == "VALIDATION" else "false"


def provision_mtibs_for_claim(claim: Any) -> dict[str, list[str]]:
    """Ensure every node held by ``claim`` has a healthy mtib-server pod.

    Idempotent: ``create_mtib_deployment`` returns the existing deploy name
    on 409, so an existing fixture-bound or standalone deployment is
    reused untouched (its ``claim-id`` label stays empty and it survives
    claim teardown). Only freshly-created pods get tagged with the claim id.

    Returns ``{"created": [...], "reused": [...], "failed": [...]}`` keyed by
    node hostname. The caller should treat a non-empty ``failed`` as a
    provisioning failure and release the claim — see route layer.
    """
    result: dict[str, list[str]] = {"created": [], "reused": [], "failed": []}
    claim_id = getattr(claim, "id", "") or ""

    fixture = getattr(claim, "fixture", None)
    fixture_id_for_deploy = getattr(fixture, "id", None) or "claim-standalone"

    for node, slot_index in _claimed_targets(claim):
        hostname = getattr(node, "hostname", None)
        if not hostname:
            continue
        existing_name = None
        meta = getattr(node, "metadata", None)
        if isinstance(meta, dict):
            existing_name = meta.get("deployment_name")

        config: dict = {"env": {"MOTION_ENABLED": _motion_enabled_for_node(node)}}
        deploy_id = (
            f"fixture-{fixture_id_for_deploy[:8]}"
            if getattr(claim, "fixtureId", None)
            else f"claim-{claim_id[:8]}"
        )
        deploy_name = create_mtib_deployment(
            node_hostname=hostname,
            fixture_id=fixture_id_for_deploy,
            deployment_id=deploy_id,
            slot_index=slot_index,
            config=config,
            claim_id=claim_id,
        )
        if deploy_name is None:
            logger.error("Provisioning mtib-server failed for node %s", hostname)
            result["failed"].append(hostname)
            continue
        # Distinguish reused-existing from newly-created: if Node.metadata
        # already pointed at the same deploy_name, it pre-existed.
        if existing_name and existing_name == deploy_name:
            result["reused"].append(hostname)
        else:
            result["created"].append(hostname)
    return result


def teardown_claim_mtibs(claim: Any) -> list[str]:
    """Delete only the mtib-server Deployments this claim spun up.

    Matches by the ``corekinect.com/claim-id`` label, so fixture-bound and
    standalone-node deployments (which set the label to empty) are
    untouched. Idempotent — re-calling after a previous teardown returns
    ``[]``.
    """
    claim_id = getattr(claim, "id", None)
    if not claim_id:
        return []
    deleted = delete_mtib_deployments_for_claim(claim_id)
    if deleted:
        logger.info("Tore down %d claim-owned mtib deployments for claim %s: %s",
                    len(deleted), claim_id, deleted)
    return deleted


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


def serialize_claim(claim: Any, *, include_bindings: bool = True) -> dict:
    """Render a FixtureClaim row into the v2 response shape.

    ``slotBindings`` is the list the client cares about — for fixture-mode
    it's the live slot→node→MTIB-host triples; for node-mode it's the
    claimed nodes resolved the same way. When ``include_bindings=False``
    the bindings array is omitted (used by list responses to avoid one K8s
    call per row).
    """
    out: dict = {
        "id": claim.id,
        "userId": claim.userId,
        "status": claim.status,
        "fixtureId": getattr(claim, "fixtureId", None),
        "description": getattr(claim, "description", None),
        "acquiredAt": _iso(getattr(claim, "acquiredAt", None)),
        "lastHeartbeatAt": _iso(getattr(claim, "lastHeartbeatAt", None)),
        "expiresAt": _iso(getattr(claim, "expiresAt", None)),
        "hardCeilingAt": _iso(getattr(claim, "hardCeilingAt", None)),
        "releasedAt": _iso(getattr(claim, "releasedAt", None)),
        "createdAt": _iso(getattr(claim, "createdAt", None)),
        "updatedAt": _iso(getattr(claim, "updatedAt", None)),
    }
    if include_bindings:
        out["slotBindings"] = _build_slot_bindings(claim)
    return out


def _build_slot_bindings(claim: Any) -> list[dict]:
    """Walk the claim's bound nodes (whether via fixture or claimedNodes)
    and resolve each to ``{label, nodeId, mtibHost}``.

    Skipped entries (unresolvable nodeId, no IP) appear with mtibHost=None
    so the client can render a partial view rather than swallowing data.
    """
    bindings: list[dict] = []

    if getattr(claim, "fixtureId", None):
        fixture = getattr(claim, "fixture", None)
        if fixture is None:
            return bindings
        for slot in (getattr(fixture, "slots", None) or []):
            node = getattr(slot, "node", None)
            bindings.append({
                "label": getattr(slot, "label", None) or f"slot-{slot.slotIndex}",
                "slotIndex": getattr(slot, "slotIndex", None),
                "nodeId": getattr(node, "id", None),
                "nodeHostname": getattr(node, "hostname", None),
                "mtibHost": None,  # filled in below
            })
        node_ids = [b["nodeId"] for b in bindings if b["nodeId"]]
    else:
        for cn in (getattr(claim, "claimedNodes", None) or []):
            node = getattr(cn, "node", None)
            bindings.append({
                "label": getattr(cn, "label", None),
                "slotIndex": None,
                "nodeId": getattr(cn, "nodeId", None),
                "nodeHostname": getattr(node, "hostname", None),
                "mtibHost": None,
            })
        node_ids = [b["nodeId"] for b in bindings if b["nodeId"]]

    if not node_ids:
        return bindings

    addr_map = resolve_node_addresses(node_ids)
    for b in bindings:
        if b["nodeId"]:
            b["mtibHost"] = addr_map.get(b["nodeId"])
    return bindings


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO 8601 with timezone if possible — None passes through."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Sweeper
# ---------------------------------------------------------------------------


def sweep_expired_claims(db) -> dict[str, list[str]]:
    """Transition expired / abandoned ACTIVE claims to terminal states.

    Returns a dict ``{"expired": [...], "abandoned": [...]}`` with the
    claim ids that flipped. Idempotent — running twice in a row produces
    an empty result the second time.

    Called by the background scheduler thread (see
    ``services/scheduling/scheduler.py``) and by tests that want to drive
    the sweep deterministically.
    """
    now = datetime.now(timezone.utc)
    expired_ids: list[str] = []
    abandoned_ids: list[str] = []

    # Hard-ceiling lapses take precedence over sliding-window lapses —
    # a claim that hit the 8h ceiling should be ABANDONED, not EXPIRED.
    abandoned = db.fixtureclaim.find_many(
        where={"status": "ACTIVE", "hardCeilingAt": {"lt": now}},
    )
    for c in abandoned:
        db.fixtureclaim.update(
            where={"id": c.id},
            data={"status": "ABANDONED", "releasedAt": now},
        )
        teardown_claim_mtibs(c)
        abandoned_ids.append(c.id)

    expired = db.fixtureclaim.find_many(
        where={"status": "ACTIVE", "expiresAt": {"lt": now}},
    )
    for c in expired:
        db.fixtureclaim.update(
            where={"id": c.id},
            data={"status": "EXPIRED", "releasedAt": now},
        )
        teardown_claim_mtibs(c)
        expired_ids.append(c.id)

    return {"expired": expired_ids, "abandoned": abandoned_ids}
