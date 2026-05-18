"""Tests for services.kubernetes.node_sync.refresh_node_ips_from_k8s."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


def _db_node(**overrides):
    defaults = dict(
        id="node-1", name="MTIB-01", hostname="verdin-imx8mm-001",
        type="VALIDATION", disabled=False, ipAddress="10.4.45.33",
        hardwareRevision="REV1.2", metadata=None,
        createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _k8s_node(name, ip):
    n = MagicMock()
    n.metadata.name = name
    if ip:
        n.status.addresses = [MagicMock(type="InternalIP", address=ip)]
    else:
        n.status.addresses = []
    return n


class TestRefreshNodeIpsFromK8s:
    def test_updates_drifted_ip(self):
        from src.services.kubernetes.node_sync import refresh_node_ips_from_k8s

        core_v1 = MagicMock()
        core_v1.list_node.return_value = MagicMock(items=[_k8s_node("verdin-imx8mm-001", "10.4.45.99")])
        db = MagicMock()
        db.node.find_many.return_value = [_db_node(ipAddress="10.4.45.33")]

        with patch("src.services.kubernetes.node_sync.get_core_v1_api", return_value=core_v1):
            count = refresh_node_ips_from_k8s(db=db)

        assert count == 1
        db.node.update.assert_called_once_with(
            where={"id": "node-1"},
            data={"ipAddress": "10.4.45.99"},
        )

    def test_skips_when_ip_matches(self):
        from src.services.kubernetes.node_sync import refresh_node_ips_from_k8s

        core_v1 = MagicMock()
        core_v1.list_node.return_value = MagicMock(items=[_k8s_node("verdin-imx8mm-001", "10.4.45.33")])
        db = MagicMock()
        db.node.find_many.return_value = [_db_node(ipAddress="10.4.45.33")]

        with patch("src.services.kubernetes.node_sync.get_core_v1_api", return_value=core_v1):
            count = refresh_node_ips_from_k8s(db=db)

        assert count == 0
        db.node.update.assert_not_called()

    def test_does_not_clobber_with_empty(self):
        from src.services.kubernetes.node_sync import refresh_node_ips_from_k8s

        core_v1 = MagicMock()
        core_v1.list_node.return_value = MagicMock(items=[_k8s_node("verdin-imx8mm-001", None)])
        db = MagicMock()
        db.node.find_many.return_value = [_db_node(ipAddress="10.4.45.33")]

        with patch("src.services.kubernetes.node_sync.get_core_v1_api", return_value=core_v1):
            count = refresh_node_ips_from_k8s(db=db)

        assert count == 0
        db.node.update.assert_not_called()

    def test_k8s_unreachable_returns_zero(self):
        from src.services.kubernetes.node_sync import refresh_node_ips_from_k8s

        db = MagicMock()
        with patch("src.services.kubernetes.node_sync.get_core_v1_api", side_effect=Exception("k8s down")):
            count = refresh_node_ips_from_k8s(db=db)

        assert count == 0
        db.node.find_many.assert_not_called()

    def test_per_row_failures_are_isolated(self):
        from src.services.kubernetes.node_sync import refresh_node_ips_from_k8s

        # Two nodes; the first update raises, the second must still run.
        core_v1 = MagicMock()
        core_v1.list_node.return_value = MagicMock(items=[
            _k8s_node("verdin-imx8mm-001", "10.4.45.99"),
            _k8s_node("verdin-imx8mm-002", "10.4.45.100"),
        ])
        db = MagicMock()
        db.node.find_many.return_value = [
            _db_node(id="node-1", hostname="verdin-imx8mm-001", ipAddress="10.4.45.33"),
            _db_node(id="node-2", hostname="verdin-imx8mm-002", ipAddress="10.4.45.34"),
        ]
        db.node.update.side_effect = [Exception("db blip"), MagicMock()]

        with patch("src.services.kubernetes.node_sync.get_core_v1_api", return_value=core_v1):
            count = refresh_node_ips_from_k8s(db=db)

        assert count == 1  # only the second succeeded
        assert db.node.update.call_count == 2
