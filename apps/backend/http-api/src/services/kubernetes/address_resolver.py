"""Node ID → MTIB address resolution.

Walks a set of Node ids, reads their hostnames from the DB, asks the K8s
API for the live InternalIP for each, and returns ``{nodeId: ip:port}``.
Used by the validation scheduler when building MTIB_HOSTS for a runner
pod and by the fixture-claim endpoints when answering ``slotBindings``.

The K8s lookup is the source of truth for the IP — never the stored
``Node.ipAddress`` column — because Verdin edge nodes get DHCP leases that
rotate on reboot. ``Node.ipAddress`` is a cache refreshed by the
``node-ip-refresh`` scheduler thread; reading K8s directly here avoids a
write-vs-read race with that thread on first-boot.

If the K8s API is unreachable, falls back to the cached
``Node.ipAddress`` so a fixture isn't immediately disqualified by a
transient cluster glitch.
"""

import logging

from config.env import env_config
from src.services.database.prisma import get_db_client
from src.services.kubernetes.client import resolve_node_ips

logger = logging.getLogger(__name__)


def resolve_node_addresses(
    node_ids: list[str],
    *,
    port: int | None = None,
) -> dict[str, str]:
    """Return ``{nodeId: 'ip:port'}`` for every reachable node id.

    Args:
        node_ids: ``Node.id`` cuids to resolve. Empty / unknown / unbound
            ids are silently dropped from the result — the caller should
            treat ``len(result) < len(node_ids)`` as "some nodes missing"
            and surface that to the user.
        port: MTIB gRPC port. Defaults to ``env_config.MTIB_PORT`` (50053)
            — the only port mtib-server listens on today; the parameter
            exists for future-proofing and tests.

    Returns:
        Dict keyed by ``Node.id``. Values are ``f"{ip}:{port}"`` strings
        ready to drop into ``MTIB_HOST`` / ``MTIB_HOSTS`` env vars.
    """
    if not node_ids:
        return {}

    mtib_port = port if port is not None else env_config.MTIB_PORT

    db = get_db_client()
    nodes = db.node.find_many(where={"id": {"in": list(node_ids)}})

    by_id = {n.id: n for n in nodes}
    hostnames = [n.hostname for n in nodes if getattr(n, "hostname", None)]

    # Ask K8s for live IPs — never the cached column on the row.
    ip_by_hostname: dict[str, str] = {}
    if hostnames:
        try:
            ip_by_hostname = resolve_node_ips(hostnames)
        except Exception as exc:
            logger.warning(
                "K8s IP resolution failed (%s) — falling back to Node.ipAddress cache",
                exc,
            )

    result: dict[str, str] = {}
    for node_id in node_ids:
        node = by_id.get(node_id)
        if node is None:
            continue
        ip = ip_by_hostname.get(getattr(node, "hostname", "")) or getattr(node, "ipAddress", None)
        if not ip:
            continue
        result[node_id] = f"{ip}:{mtib_port}"

    return result
