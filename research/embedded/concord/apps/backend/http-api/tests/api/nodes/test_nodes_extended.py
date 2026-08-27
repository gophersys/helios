"""Extended tests for nodes.py — sync_nodes_from_k8s, health check, and delete guards."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


def _node(**overrides):
    defaults = dict(
        id="node-1", name="MTIB-01", hostname="verdin-imx8mm-001",
        type="VALIDATION", disabled=False, ipAddress="192.168.1.1",
        hardwareRevision="REV1.2", metadata=None, fixtureSlot=None,
        createdAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


class TestDeleteNodeGuards:
    """Tests for delete_node — protected by test execution check."""

    def test_delete_node_with_executions_returns_conflict(self, authed_client, mock_db):
        """Cannot delete a node that has associated test executions."""
        node = _node(testExecutions=[make_obj(id="exec-1")])
        mock_db.node.find_unique.return_value = node

        with patch("api.v2.nodes.nodes.log_audit"):
            response = authed_client.delete("/v2/devices/mtibs/node-1")

        assert response.status_code == 409
        body = json.loads(response.data)
        assert "executions" in body["errors"][0]["message"].lower()

    def test_delete_node_no_executions_succeeds(self, authed_client, mock_db):
        """Delete node with empty test executions list succeeds."""
        node = _node(testExecutions=[])
        mock_db.node.find_unique.return_value = node

        with patch("api.v2.nodes.nodes.log_audit"):
            response = authed_client.delete("/v2/devices/mtibs/node-1")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["deleted"] is True


class TestSyncNodesFromK8s:
    """Tests for POST /v2/devices/mtibs/discover — sync_nodes_from_k8s."""

    def test_sync_k8s_unavailable_returns_empty(self, authed_client, mock_db):
        """When K8s client is not available, returns empty result with k8sAvailable=False."""
        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", False):
            response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["k8sAvailable"] is False
        assert body["data"]["registered"] == []
        assert body["data"]["discovered"] == []
        assert body["data"]["offline"] == []

    def test_sync_k8s_api_error_returns_empty(self, authed_client, mock_db):
        """When K8s API raises, returns empty result gracefully."""
        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", side_effect=Exception("K8s down")):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["registered"] == []

    def test_sync_registers_arm64_ready_nodes(self, authed_client, mock_db):
        """Discovers arm64 Ready K8s nodes not yet in DB."""
        k8s_node = MagicMock()
        k8s_node.metadata.name = "verdin-new"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "arm64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = [MagicMock(type="InternalIP", address="192.168.1.99")]
        k8s_node.status.node_info = MagicMock(os_image="TorizonOS", kubelet_version="v1.28")

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        mock_db.node.find_many.return_value = []

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert len(body["data"]["discovered"]) == 1
        assert body["data"]["discovered"][0]["hostname"] == "verdin-new"

    def test_sync_identifies_registered_nodes(self, authed_client, mock_db):
        """K8s nodes already in DB appear in 'registered' list."""
        k8s_node = MagicMock()
        k8s_node.metadata.name = "verdin-known"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "arm64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = [MagicMock(type="InternalIP", address="192.168.1.100")]
        k8s_node.status.node_info = MagicMock(os_image="TorizonOS", kubelet_version="v1.28")

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        existing = _node(hostname="verdin-known")
        mock_db.node.find_many.return_value = [existing]

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert len(body["data"]["registered"]) == 1
        assert body["data"]["registered"][0]["hostname"] == "verdin-known"

    def test_sync_identifies_offline_nodes(self, authed_client, mock_db):
        """DB nodes not found in K8s appear in 'offline' list."""
        k8s_list = MagicMock()
        k8s_list.items = []  # no K8s nodes

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        offline = _node(hostname="verdin-offline")
        mock_db.node.find_many.return_value = [offline]

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert len(body["data"]["offline"]) == 1
        assert body["data"]["offline"][0]["hostname"] == "verdin-offline"

    def test_sync_skips_non_arm64_nodes(self, authed_client, mock_db):
        """x86_64 K8s nodes are not included in discover results."""
        k8s_node = MagicMock()
        k8s_node.metadata.name = "amd-server"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "amd64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = []
        k8s_node.status.node_info = MagicMock()

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        mock_db.node.find_many.return_value = []

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert len(body["data"]["discovered"]) == 0

    def test_sync_unauthorized_returns_401(self, client, mock_db):
        """POST /v2/devices/mtibs/discover without auth returns 401."""
        response = client.post("/v2/devices/mtibs/discover")
        assert response.status_code == 401

    def test_sync_updates_stale_ipAddress_in_db(self, authed_client, mock_db):
        """When K8s reports a different IP than the DB cached value, the
        DB row is updated. This is what makes the stale-IP problem
        self-healing — a Verdin coming back online with a new DHCP lease
        no longer leaves the observability poller stuck on the old IP.
        """
        k8s_node = MagicMock()
        k8s_node.metadata.name = "verdin-roaming"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "arm64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = [MagicMock(type="InternalIP", address="10.4.45.99")]
        k8s_node.status.node_info = MagicMock(os_image="TorizonOS", kubelet_version="v1.28")

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        # DB has the stale IP from a previous DHCP lease
        existing = _node(id="node-roam", hostname="verdin-roaming", ipAddress="10.4.45.33")
        mock_db.node.find_many.return_value = [existing]

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        # The DB row should have been refreshed to the live K8s IP.
        mock_db.node.update.assert_any_call(
            where={"id": "node-roam"},
            data={"ipAddress": "10.4.45.99"},
        )
        # Response also reports the live IP, not the cached one.
        body = json.loads(response.data)
        assert body["data"]["registered"][0]["ipAddress"] == "10.4.45.99"

    def test_sync_does_not_update_when_ipAddress_matches(self, authed_client, mock_db):
        """When K8s IP equals DB IP, no write is issued — avoid pointless
        churn + audit log noise on every sync tick."""
        k8s_node = MagicMock()
        k8s_node.metadata.name = "verdin-stable"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "arm64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = [MagicMock(type="InternalIP", address="10.4.45.50")]
        k8s_node.status.node_info = MagicMock(os_image="TorizonOS", kubelet_version="v1.28")

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        existing = _node(id="node-stable", hostname="verdin-stable", ipAddress="10.4.45.50")
        mock_db.node.find_many.return_value = [existing]

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        mock_db.node.update.assert_not_called()

    def test_sync_writes_ipAddress_for_first_time_when_db_has_null(self, authed_client, mock_db):
        """When the DB row's ipAddress is NULL (newly-created node never
        had its IP backfilled), sync populates it from K8s."""
        k8s_node = MagicMock()
        k8s_node.metadata.name = "verdin-first-time"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "arm64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = [MagicMock(type="InternalIP", address="10.4.45.42")]
        k8s_node.status.node_info = MagicMock(os_image="TorizonOS", kubelet_version="v1.28")

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        existing = _node(id="node-first", hostname="verdin-first-time", ipAddress=None)
        mock_db.node.find_many.return_value = [existing]

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        mock_db.node.update.assert_any_call(
            where={"id": "node-first"},
            data={"ipAddress": "10.4.45.42"},
        )

    def test_sync_does_not_clobber_with_empty_ipAddress(self, authed_client, mock_db):
        """When K8s reports a node with no InternalIP yet (still booting),
        do NOT overwrite the DB's last-known-good IP with an empty string.
        Better to keep a stale value than to lose it."""
        k8s_node = MagicMock()
        k8s_node.metadata.name = "verdin-booting"
        k8s_node.metadata.labels = {"kubernetes.io/arch": "arm64"}
        k8s_node.status.conditions = [MagicMock(type="Ready", status="True")]
        k8s_node.status.addresses = []  # not yet assigned
        k8s_node.status.node_info = MagicMock(os_image="TorizonOS", kubelet_version="v1.28")

        k8s_list = MagicMock()
        k8s_list.items = [k8s_node]

        core_v1 = MagicMock()
        core_v1.list_node.return_value = k8s_list

        existing = _node(id="node-boot", hostname="verdin-booting", ipAddress="10.4.45.77")
        mock_db.node.find_many.return_value = [existing]

        with patch("api.v2.nodes.nodes.K8S_AVAILABLE", True):
            with patch("api.v2.nodes.nodes.get_core_v1_api", return_value=core_v1):
                response = authed_client.post("/v2/devices/mtibs/discover")

        assert response.status_code == 200
        mock_db.node.update.assert_not_called()


class TestCheckNodeHealth:
    """Tests for POST /v2/devices/mtibs/<node_id>/health."""

    def test_health_check_node_not_found(self, authed_client, mock_db):
        """POST returns 404 when node does not exist."""
        mock_db.node.find_unique.return_value = None

        response = authed_client.post("/v2/devices/mtibs/nonexistent/health")

        assert response.status_code == 404

    def test_health_check_no_ip_returns_offline(self, authed_client, mock_db):
        """POST returns healthy=False when node has no IP configured."""
        mock_db.node.find_unique.return_value = _node(ipAddress=None)
        mock_db.node.update.return_value = _node(ipAddress=None, disabled=False)

        response = authed_client.post("/v2/devices/mtibs/node-1/health")

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["healthy"] is False
        assert body["data"]["status"] == "OFFLINE"

    # TODO: test_health_check_grpc_timeout_returns_offline
    # TODO: test_health_check_grpc_success_returns_online


class TestCreateNodeValidation:
    """Tests for POST /v2/devices/mtibs — field validation."""

    def test_create_node_missing_name_returns_400(self, authed_client, mock_db):
        """POST without name field returns 400."""
        response = authed_client.post(
            "/v2/devices/mtibs",
            data=json.dumps({"hostname": "host", "type": "VALIDATION"}),
        )
        assert response.status_code == 400

    def test_create_node_missing_hostname_returns_400(self, authed_client, mock_db):
        """POST without hostname field returns 400."""
        response = authed_client.post(
            "/v2/devices/mtibs",
            data=json.dumps({"name": "MTIB", "type": "VALIDATION"}),
        )
        assert response.status_code == 400

    # TODO: test_create_node_invalid_type_returns_400
