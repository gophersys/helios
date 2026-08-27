"""
Integration tests for Cluster info, namespaces, nodes, and events endpoints:

    GET  /v2/cluster/info           — get_cluster
    GET  /v2/cluster/namespaces     — get_namespaces
    GET  /v2/cluster/nodes          — list_nodes
    GET  /v2/cluster/nodes/<name>   — get_node
    GET  /v2/cluster/events         — get_events
"""

import json
from unittest.mock import patch, MagicMock

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/info
# ---------------------------------------------------------------------------

class TestClusterInfo:
    """Tests for the get_cluster endpoint."""

    @patch("api.v2.kubernetes.cluster.get_cluster_info")
    def test_cluster_info_success(self, mock_get_info, authed_client):
        """Should return 200 with cluster summary data."""
        mock_get_info.return_value = {
            "kubernetesVersion": "v1.28.4+k3s1",
            "platforms": ["linux/amd64"],
            "nodeCount": 2,
            "namespaceCount": 5,
            "resources": {
                "pods": {"running": 10, "pending": 0, "failed": 1, "succeeded": 3, "total": 14},
                "deployments": {"available": 6, "progressing": 0, "total": 6},
                "services": {"total": 8},
                "jobs": {"active": 1, "succeeded": 5, "failed": 0, "total": 6},
            },
        }

        response = authed_client.get("/v2/kubernetes/info")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        data = body["data"]
        assert data["kubernetesVersion"] == "v1.28.4+k3s1"
        assert data["nodeCount"] == 2
        assert data["resources"]["pods"]["running"] == 10
        assert data["resources"]["deployments"]["total"] == 6

    @patch("api.v2.kubernetes.cluster.get_cluster_info")
    def test_cluster_info_k8s_unavailable(self, mock_get_info, authed_client):
        """Should return 500 when the K8s API raises a generic exception."""
        mock_get_info.side_effect = Exception("Connection refused")

        response = authed_client.get("/v2/kubernetes/info")
        assert response.status_code == 500

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    @patch("api.v2.kubernetes.cluster.get_cluster_info")
    def test_cluster_info_k8s_api_404(self, mock_get_info, authed_client):
        """Should return 404 when the K8s API raises a 404 ApiException."""
        mock_get_info.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/kubernetes/info")
        assert response.status_code == 404

    def test_cluster_info_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/info")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/namespaces
# ---------------------------------------------------------------------------

class TestClusterNamespaces:
    """Tests for the get_namespaces endpoint."""

    @patch("api.v2.kubernetes.cluster.list_namespaces")
    def test_list_namespaces_success(self, mock_list_ns, authed_client):
        """Should return 200 with a list of namespaces."""
        mock_list_ns.return_value = [
            {"name": "default", "status": "Active"},
            {"name": "staging", "status": "Active"},
            {"name": "production", "status": "Active"},
        ]

        response = authed_client.get("/v2/kubernetes/namespaces")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]) == 3
        assert body["data"][0]["name"] == "default"

    @patch("api.v2.kubernetes.cluster.list_namespaces")
    def test_list_namespaces_empty(self, mock_list_ns, authed_client):
        """Should return 200 with an empty list when no namespaces exist."""
        mock_list_ns.return_value = []

        response = authed_client.get("/v2/kubernetes/namespaces")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"] == []

    @patch("api.v2.kubernetes.cluster.list_namespaces")
    def test_list_namespaces_k8s_error(self, mock_list_ns, authed_client):
        """Should return 500 when the K8s API is unreachable."""
        mock_list_ns.side_effect = Exception("K8s unreachable")

        response = authed_client.get("/v2/kubernetes/namespaces")
        assert response.status_code == 500

    def test_list_namespaces_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/namespaces")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/nodes
# ---------------------------------------------------------------------------

class TestClusterNodes:
    """Tests for the list_nodes and get_node endpoints."""

    @patch("api.v2.kubernetes.nodes.nodes_svc.list_nodes")
    def test_list_nodes_success(self, mock_list, authed_client):
        """Should return 200 with node data."""
        mock_list.return_value = [
            {"name": "node-1", "status": "Ready", "allocated": {"podCount": 5}},
            {"name": "node-2", "status": "Ready", "allocated": {"podCount": 3}},
        ]

        response = authed_client.get("/v2/kubernetes/nodes")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]) == 2
        assert body["data"][0]["name"] == "node-1"

    @patch("api.v2.kubernetes.nodes.nodes_svc.list_nodes")
    def test_list_nodes_k8s_error(self, mock_list, authed_client):
        """Should return 500 when the K8s API raises a generic exception."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/nodes")
        assert response.status_code == 500

    @patch("api.v2.kubernetes.nodes.nodes_svc.get_node")
    def test_get_node_success(self, mock_get, authed_client):
        """Should return 200 with detailed node data."""
        mock_get.return_value = {
            "name": "node-1",
            "status": "Ready",
            "allocated": {"cpuRequests": "500m", "memoryRequests": "256Mi", "podCount": 5},
            "pods": [{"name": "pod-a", "namespace": "default", "status": "Running", "restarts": 0}],
        }

        response = authed_client.get("/v2/kubernetes/nodes/node-1")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["name"] == "node-1"
        assert body["data"]["allocated"]["podCount"] == 5

    @patch("api.v2.kubernetes.nodes.nodes_svc.get_node")
    def test_get_node_not_found(self, mock_get, authed_client):
        """Should return 404 when the node does not exist."""
        mock_get.return_value = None

        response = authed_client.get("/v2/kubernetes/nodes/nonexistent-node")
        assert response.status_code == 404

    @patch("api.v2.kubernetes.nodes.nodes_svc.get_node")
    def test_get_node_k8s_api_404(self, mock_get, authed_client):
        """Should return 404 when K8s returns 404 ApiException."""
        mock_get.side_effect = ApiException(status=404, reason="Not Found")

        response = authed_client.get("/v2/kubernetes/nodes/missing")
        assert response.status_code == 404

    def test_list_nodes_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/nodes")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/events
# ---------------------------------------------------------------------------

class TestClusterEvents:
    """Tests for the get_events endpoint."""

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_success(self, mock_events, authed_client):
        """Should return 200 with a paginated list of cluster events."""
        mock_events.return_value = [
            {"type": "Normal", "reason": "Scheduled", "message": "Pod scheduled", "lastSeen": "2026-03-11T10:00:00Z"},
            {"type": "Warning", "reason": "BackOff", "message": "Back-off restarting", "lastSeen": "2026-03-11T09:55:00Z"},
        ]

        response = authed_client.get("/v2/kubernetes/events")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert "pagination" in body["data"]

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_with_namespace_filter(self, mock_events, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_events.return_value = [
            {"type": "Normal", "reason": "Pulled", "message": "Image pulled", "lastSeen": "2026-03-11T10:00:00Z"},
        ]

        response = authed_client.get("/v2/kubernetes/events?namespace=staging")
        assert response.status_code == 200

        mock_events.assert_called_once_with(namespace="staging", limit=50, field_selector=None)

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_with_limit(self, mock_events, authed_client):
        """Should respect the limit query param."""
        mock_events.return_value = []

        response = authed_client.get("/v2/kubernetes/events?limit=10")
        assert response.status_code == 200

        mock_events.assert_called_once_with(namespace=None, limit=10, field_selector=None)

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_limit_clamped(self, mock_events, authed_client):
        """Limit should be clamped to [1, 1000]."""
        mock_events.return_value = []

        response = authed_client.get("/v2/kubernetes/events?limit=5000")
        assert response.status_code == 200

        # The handler clamps to 1000
        mock_events.assert_called_once_with(namespace=None, limit=1000, field_selector=None)

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_pagination(self, mock_events, authed_client):
        """Should paginate results and multiply limit by page for fetching."""
        mock_events.return_value = [
            {"type": "Normal", "reason": f"Event{i}", "message": f"msg{i}"}
            for i in range(20)
        ]

        response = authed_client.get("/v2/kubernetes/events?page=2&limit=10")
        assert response.status_code == 200

        body = json.loads(response.data)
        # limit * page = 10 * 2 = 20 passed to service
        mock_events.assert_called_once_with(namespace=None, limit=20, field_selector=None)
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["limit"] == 10
        assert len(body["data"]["data"]) == 10

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_empty_returns_pagination(self, mock_events, authed_client):
        """Empty results should still include proper pagination structure."""
        mock_events.return_value = []

        response = authed_client.get("/v2/kubernetes/events")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 1

    @patch("api.v2.kubernetes.events.list_events")
    def test_list_events_k8s_error(self, mock_events, authed_client):
        """Should return 500 when the K8s API raises."""
        mock_events.side_effect = Exception("Connection refused")

        response = authed_client.get("/v2/kubernetes/events")
        assert response.status_code == 500

    def test_list_events_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/events")
        assert response.status_code == 401
