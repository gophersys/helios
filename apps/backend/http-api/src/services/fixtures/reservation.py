"""Reservation gate — single source of truth for "is this fixture busy?".

Three things can hold a fixture / node:

1. An ACTIVE ``TestRun`` whose ``fixtureId`` matches.
2. An ACTIVE ``ManufacturingSession`` whose ``fixtureId`` matches.
3. An ACTIVE ``FixtureClaim`` (DEV_HOLD) that either binds the fixture
   directly (``fixtureId``) or claims one of the fixture's slot nodes
   (``ClaimedNode.nodeId``).

The same gate is consulted before a TestRun starts (scheduler.py), before
a ManufacturingSession starts, and before a new ``FixtureClaim`` is
created. Keeping the union in one place means future "busy" sources
(maintenance hold, lab quarantine, etc.) only need to extend this module.
"""

import logging
from typing import Optional


logger = logging.getLogger(__name__)


# Reason codes returned by ``is_fixture_busy``. The HTTP layer surfaces
# these verbatim in 409 responses so callers can branch on them without
# string-matching English.
REASON_TEST_RUN = "TEST_RUN_ACTIVE"
REASON_MFG_SESSION = "MFG_SESSION_ACTIVE"
REASON_CLAIM = "CLAIM_ACTIVE"


def is_fixture_busy(db, fixture_id: str) -> tuple[bool, Optional[str]]:
    """Return ``(busy, reason)`` for a fixture.

    A fixture is busy if any ACTIVE TestRun, ManufacturingSession, or
    FixtureClaim references it — either directly via ``fixtureId`` or, in
    the case of node-mode claims, indirectly via one of the fixture's
    bound slot nodes.

    ``reason`` is None when ``busy`` is False; otherwise one of
    :data:`REASON_TEST_RUN`, :data:`REASON_MFG_SESSION`, :data:`REASON_CLAIM`.

    The function never raises on a missing fixture — that's a 404 the
    caller surfaces separately. We just return ``(False, None)`` so the
    downstream "load fixture" path can produce a clean error.
    """
    if not fixture_id:
        return False, None

    # 1. Direct TestRun on the fixture
    if db.testrun.count(where={"fixtureId": fixture_id, "status": "ACTIVE"}) > 0:
        return True, REASON_TEST_RUN

    # 2. Direct ManufacturingSession on the fixture
    if db.manufacturingsession.count(
        where={"fixtureId": fixture_id, "status": "ACTIVE"},
    ) > 0:
        return True, REASON_MFG_SESSION

    # 3a. Direct FixtureClaim on the fixture (fixture-mode)
    if db.fixtureclaim.count(
        where={"fixtureId": fixture_id, "status": "ACTIVE"},
    ) > 0:
        return True, REASON_CLAIM

    # 3b. Node-mode FixtureClaim where one of the fixture's slot nodes
    # is currently held. Load slot nodes for the fixture, then probe
    # claimednode for an active claim that includes any of them.
    fixture = db.fixture.find_unique(
        where={"id": fixture_id},
        include={"slots": True},
    )
    if fixture is None:
        return False, None

    node_ids = [
        s.nodeId for s in (fixture.slots or [])
        if getattr(s, "active", True) and getattr(s, "nodeId", None)
    ]
    if node_ids and _any_node_claimed(db, node_ids):
        return True, REASON_CLAIM

    return False, None


def are_nodes_busy(db, node_ids: list[str]) -> tuple[bool, Optional[str], Optional[str]]:
    """Return ``(busy, reason, holding_node_id)`` for a list of nodes.

    A node is busy if any ACTIVE FixtureClaim already binds it (direct
    node-mode hold), OR if it is wired into a slot whose fixture has an
    ACTIVE TestRun / ManufacturingSession (transitive hold).

    Used by the create-claim endpoint when the request is in node-mode:
    even though the caller never names a fixture, we still need to refuse
    if those raw nodes are wired into a fixture that's currently busy.

    Returns the offending ``Node.id`` so the caller can mention which
    node blocked the claim.
    """
    if not node_ids:
        return False, None, None

    # 1. Already held by an active node-mode claim
    held = db.claimednode.find_first(
        where={
            "nodeId": {"in": list(node_ids)},
            "claim": {"is": {"status": "ACTIVE"}},
        },
    )
    if held is not None:
        return True, REASON_CLAIM, getattr(held, "nodeId", None)

    # 2. Wired into a slot whose fixture has an ACTIVE TestRun or
    # ManufacturingSession. Walk slots → fixture id → check both.
    slots = db.fixtureslot.find_many(
        where={"nodeId": {"in": list(node_ids)}},
    )
    fixture_ids = {s.fixtureId for s in slots if getattr(s, "fixtureId", None)}
    if not fixture_ids:
        return False, None, None

    busy_run = db.testrun.find_first(
        where={"fixtureId": {"in": list(fixture_ids)}, "status": "ACTIVE"},
    )
    if busy_run is not None:
        # Best-effort: identify which node the offending fixture holds.
        offending = next(
            (s.nodeId for s in slots if s.fixtureId == busy_run.fixtureId),
            None,
        )
        return True, REASON_TEST_RUN, offending

    busy_sess = db.manufacturingsession.find_first(
        where={"fixtureId": {"in": list(fixture_ids)}, "status": "ACTIVE"},
    )
    if busy_sess is not None:
        offending = next(
            (s.nodeId for s in slots if s.fixtureId == busy_sess.fixtureId),
            None,
        )
        return True, REASON_MFG_SESSION, offending

    return False, None, None


def _any_node_claimed(db, node_ids: list[str]) -> bool:
    """True if any of the given nodes is held by an ACTIVE node-mode claim."""
    if not node_ids:
        return False
    held = db.claimednode.find_first(
        where={
            "nodeId": {"in": list(node_ids)},
            "claim": {"is": {"status": "ACTIVE"}},
        },
    )
    return held is not None
