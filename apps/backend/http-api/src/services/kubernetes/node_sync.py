"""Periodic refresh of `Node.ipAddress` from the K8s API.

The DB column `Node.ipAddress` is a cache. Two consumers read it
(MTIB observability poller + per-node fixture health check), and
both silently fail if the cache is stale (e.g. a Verdin rebooted
and DHCP gave it a new lease). The HTTP `/v2/devices/mtibs/discover`
endpoint refreshes the cache as a side effect, but it only runs
when an operator opens the fixtures page in the UI. This module
runs the same refresh on a fixed cadence from the background
scheduler so the cache stays warm without manual intervention.

Pure write-back — does NOT classify nodes as registered/offline/
discovered like the HTTP endpoint does. Keeping the scope tight
means the loop is cheap (one `list_node` + N small `UPDATE`s) and
has no surprising side effects.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.services.database.prisma import get_db_client
from src.services.kubernetes.client import get_core_v1_api

logger = logging.getLogger(__name__)


def refresh_node_ips_from_k8s(db=None) -> int:
    """Re-read live InternalIPs from K8s and update drifted DB rows.

    Returns the number of rows actually written. Guards:
      * skip nodes K8s reports without an InternalIP (still booting)
      * skip when cached == live (no audit noise on stable nodes)
      * per-row try/except so one bad write doesn't break the rest
    """
    db = db or get_db_client()
    try:
        core_v1 = get_core_v1_api()
        k8s_nodes = core_v1.list_node()
    except Exception as e:
        logger.warning("node_sync: K8s API unreachable, skipping refresh: %s", e)
        return 0

    live_ip_by_hostname: dict[str, str] = {}
    for k8s_node in k8s_nodes.items:
        name = k8s_node.metadata.name
        for addr in (k8s_node.status.addresses or []):
            if addr.type == "InternalIP" and addr.address:
                live_ip_by_hostname[name] = addr.address
                break

    if not live_ip_by_hostname:
        return 0

    db_nodes = db.node.find_many()
    updates = 0
    for db_node in db_nodes:
        live_ip: Optional[str] = live_ip_by_hostname.get(db_node.hostname)
        if not live_ip:
            continue
        if live_ip == db_node.ipAddress:
            continue
        try:
            db.node.update(where={"id": db_node.id}, data={"ipAddress": live_ip})
            logger.info(
                "node_sync: refreshed %s ipAddress %s → %s",
                db_node.hostname, db_node.ipAddress, live_ip,
            )
            updates += 1
        except Exception as e:
            logger.warning("node_sync: failed to update %s: %s", db_node.hostname, e)
    return updates
