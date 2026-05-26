"""GET /v2/test/nodes — discovery endpoint for ``corectl test list-nodes``.

Surfaces the physical test nodes (MTIBs) visible to the platform along
with the slot/fixture they are bound to and a coarse availability flag.
This is a read-only convenience over the existing Node records — claim
mutations still go through ``/v2/fixture-claims``.

Query parameters:

- ``available`` (bool) — if ``true``, drop nodes that have an ACTIVE
  ``FixtureClaim`` against them. Default: false (return everything).
- ``purpose`` (str) — filter by ``Node.type``. Accepts case-insensitive
  ``manufacturing`` / ``validation``.
- ``product`` (str) — filter to nodes whose ``fixtureSlot.fixture.productId``
  equals the given product id.
- ``page``, ``limit`` — standard pagination, identical to ``/v2/devices/mtibs``.
"""

from __future__ import annotations

import math
from typing import Any

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.types import ApiResponse
from src.services.database.prisma import get_db_client

from ..nodes.nodes import _serialize_node


def _has_active_claim(node: Any) -> bool:
    """Return True if the node has an ACTIVE FixtureClaim through ClaimedNode."""
    cn = getattr(node, "claimedBy", None) or []
    for entry in cn:
        claim = getattr(entry, "claim", None)
        if claim is not None and getattr(claim, "status", None) == "ACTIVE":
            return True
    return False


@require_permissions(Permissions.DEVICES_VIEW)
def list_test_nodes():
    """List test nodes with discovery-oriented filters."""
    db = get_db_client()

    page = max(1, request.args.get("page", 1, type=int))
    limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
    skip = (page - 1) * limit

    where: dict = {}

    purpose = request.args.get("purpose", "").strip().lower()
    if purpose in ("manufacturing", "validation"):
        where["type"] = purpose.upper()

    product_id = request.args.get("product", "").strip()
    if product_id:
        # Prisma nested filter: only nodes whose fixtureSlot is bound to
        # a fixture under this product.
        where["fixtureSlot"] = {"fixture": {"productId": product_id}}

    total = db.node.count(where=where)
    nodes = db.node.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"name": "asc"},
        include={
            "fixtureSlot": {"include": {"fixture": True}},
            "claimedBy": {"include": {"claim": True}},
        },
    )

    available_only = request.args.get("available", "").strip().lower() in ("1", "true", "yes")
    if available_only:
        nodes = [n for n in nodes if not _has_active_claim(n)]

    serialized = []
    for n in nodes:
        row = _serialize_node(n, include_slot=True)
        row["available"] = not _has_active_claim(n) and not row["disabled"]
        serialized.append(row)

    return jsonify(ApiResponse.ok({
        "data": serialized,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": math.ceil(total / limit) if limit > 0 else 0,
        },
    }).to_dict()), 200
