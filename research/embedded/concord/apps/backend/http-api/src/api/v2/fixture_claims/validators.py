"""Request validators for /v2/fixture-claims.

The codebase uses dataclasses + ``from_json`` rather than Pydantic; this
module follows the existing v2 convention (see ``api/v2/fixtures/types.py``).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# 1h default lease, 8h hard ceiling. Matches the spec — the hard ceiling
# is also enforced at create time when the caller asks for >8h.
DEFAULT_TTL_SECONDS = 3600
HARDCEILING_TTL_SECONDS = 8 * 3600
HEARTBEAT_WINDOW_SECONDS = 5 * 60


@dataclass
class ClaimedNodeInput:
    """One node in a node-mode claim request."""

    nodeId: str
    label: Optional[str] = None


@dataclass
class CreateClaimRequest:
    """Body for ``POST /v2/fixture-claims``.

    Two mutually-exclusive shapes:
      * fixture-mode: ``fixtureId`` set, ``nodes`` empty
      * node-mode:    ``nodes`` non-empty, ``fixtureId`` empty
    """

    fixtureId: Optional[str] = None
    nodes: List[ClaimedNodeInput] = field(default_factory=list)
    ttlSeconds: int = DEFAULT_TTL_SECONDS
    description: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["CreateClaimRequest"], Optional[str]]:
        """Parse + validate. Returns ``(request, None)`` on success, ``(None, error)`` otherwise."""
        if not data:
            return None, "Request body must contain JSON data"

        fixture_id_raw = data.get("fixtureId")
        if fixture_id_raw is not None:
            fixture_id_raw = str(fixture_id_raw).strip() or None

        nodes_raw = data.get("nodes")
        nodes: List[ClaimedNodeInput] = []
        if nodes_raw is not None:
            if not isinstance(nodes_raw, list):
                return None, "nodes must be an array"
            for i, n in enumerate(nodes_raw):
                if not isinstance(n, dict):
                    return None, f"nodes[{i}] must be an object"
                nid = (n.get("nodeId") or "").strip()
                if not nid:
                    return None, f"nodes[{i}].nodeId is required"
                label = n.get("label")
                if label is not None:
                    label = str(label).strip() or None
                nodes.append(ClaimedNodeInput(nodeId=nid, label=label))

        # XOR — fixture-mode XOR node-mode
        if fixture_id_raw and nodes:
            return None, "Specify either fixtureId or nodes, not both"
        if not fixture_id_raw and not nodes:
            return None, "Specify fixtureId or at least one node"

        # Defaults: 1h, clamped to 8h hard ceiling.
        ttl_raw = data.get("ttlSeconds")
        if ttl_raw is None:
            ttl_seconds = DEFAULT_TTL_SECONDS
        else:
            try:
                ttl_seconds = int(ttl_raw)
            except (TypeError, ValueError):
                return None, "ttlSeconds must be an integer"
            if ttl_seconds <= 0:
                return None, "ttlSeconds must be positive"
            ttl_seconds = min(ttl_seconds, HARDCEILING_TTL_SECONDS)

        description = data.get("description")
        if description is not None:
            description = str(description).strip() or None

        return cls(
            fixtureId=fixture_id_raw,
            nodes=nodes,
            ttlSeconds=ttl_seconds,
            description=description,
        ), None


@dataclass
class ListClaimsQuery:
    """Query params for ``GET /v2/fixture-claims``."""

    userId: Optional[str] = None
    status: Optional[str] = None
    fixtureId: Optional[str] = None

    @classmethod
    def from_args(cls, args) -> "ListClaimsQuery":
        """Parse Flask ``request.args`` into the dataclass."""
        return cls(
            userId=(args.get("userId") or "").strip() or None,
            status=(args.get("status") or "").strip() or None,
            fixtureId=(args.get("fixtureId") or "").strip() or None,
        )
