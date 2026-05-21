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
        abandoned_ids.append(c.id)

    expired = db.fixtureclaim.find_many(
        where={"status": "ACTIVE", "expiresAt": {"lt": now}},
    )
    for c in expired:
        db.fixtureclaim.update(
            where={"id": c.id},
            data={"status": "EXPIRED", "releasedAt": now},
        )
        expired_ids.append(c.id)

    return {"expired": expired_ids, "abandoned": abandoned_ids}
