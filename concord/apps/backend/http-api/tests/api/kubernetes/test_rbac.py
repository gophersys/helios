"""
Integration tests for Cluster RBAC endpoints:

    GET /v2/cluster/rbac/roles                  — list_roles
    GET /v2/cluster/rbac/cluster-roles           — list_cluster_roles
    GET /v2/cluster/rbac/role-bindings               — list_role_bindings
    GET /v2/cluster/rbac/cluster-role-bindings    — list_cluster_role_bindings
    GET /v2/cluster/rbac/service-accounts        — list_service_accounts
"""

import json
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException


# ---------------------------------------------------------------------------
# GET /v2/cluster/rbac/roles
# ---------------------------------------------------------------------------

class TestListRoles:
    """Tests for the list_roles endpoint."""

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_roles")
    def test_list_roles_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of roles."""
        mock_list.return_value = [
            {"name": "pod-reader", "namespace": "staging", "rules": []},
            {"name": "deploy-manager", "namespace": "staging", "rules": []},
        ]

        response = authed_client.get("/v2/kubernetes/rbac/roles")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert "pagination" in body["data"]

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_roles")
    def test_list_roles_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/roles?namespace=staging")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="staging")

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_roles")
    def test_list_roles_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list and proper pagination."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/roles")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 1

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_roles")
    def test_list_roles_pagination(self, mock_list, authed_client):
        """Should paginate results when page parameter is provided."""
        mock_list.return_value = [
            {"name": f"role-{i}", "namespace": "default", "rules": []}
            for i in range(5)
        ]

        response = authed_client.get("/v2/kubernetes/rbac/roles?page=1&limit=2")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["page"] == 1
        assert body["data"]["pagination"]["limit"] == 2
        assert body["data"]["pagination"]["total"] == 5
        assert body["data"]["pagination"]["pages"] == 3

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_roles")
    def test_list_roles_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s errors."""
        mock_list.side_effect = Exception("Connection refused")

        response = authed_client.get("/v2/kubernetes/rbac/roles")
        assert response.status_code == 500

    def test_list_roles_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/rbac/roles")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/rbac/cluster-roles
# ---------------------------------------------------------------------------

class TestListClusterRoles:
    """Tests for the list_cluster_roles endpoint."""

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_roles")
    def test_list_cluster_roles_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of cluster roles."""
        mock_list.return_value = [
            {"name": "cluster-admin", "rules": []},
            {"name": "system:node", "rules": []},
        ]

        response = authed_client.get("/v2/kubernetes/rbac/cluster-roles")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert "pagination" in body["data"]

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_roles")
    def test_list_cluster_roles_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list and proper pagination."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/cluster-roles")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 1

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_roles")
    def test_list_cluster_roles_pagination(self, mock_list, authed_client):
        """Should paginate results when page parameter is provided."""
        mock_list.return_value = [
            {"name": f"role-{i}", "rules": []}
            for i in range(7)
        ]

        response = authed_client.get("/v2/kubernetes/rbac/cluster-roles?page=2&limit=3")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 3
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["total"] == 7
        assert body["data"]["pagination"]["pages"] == 3

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_roles")
    def test_list_cluster_roles_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/rbac/cluster-roles")
        assert response.status_code == 500

    def test_list_cluster_roles_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/rbac/cluster-roles")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/rbac/role-bindings
# ---------------------------------------------------------------------------

class TestListRoleBindings:
    """Tests for the list_role_bindings endpoint."""

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_role_bindings")
    def test_list_role_bindings_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of role bindings."""
        mock_list.return_value = [
            {"name": "pod-reader-binding", "namespace": "staging", "roleRef": "pod-reader"},
        ]

        response = authed_client.get("/v2/kubernetes/rbac/role-bindings")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 1
        assert "pagination" in body["data"]

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_role_bindings")
    def test_list_role_bindings_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/role-bindings?namespace=production")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="production")

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_role_bindings")
    def test_list_role_bindings_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list and proper pagination."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/role-bindings")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 1

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_role_bindings")
    def test_list_role_bindings_pagination(self, mock_list, authed_client):
        """Should paginate results when page parameter is provided."""
        mock_list.return_value = [
            {"name": f"binding-{i}", "namespace": "default", "roleRef": "role"}
            for i in range(4)
        ]

        response = authed_client.get("/v2/kubernetes/rbac/role-bindings?page=1&limit=2")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["page"] == 1
        assert body["data"]["pagination"]["total"] == 4
        assert body["data"]["pagination"]["pages"] == 2

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_role_bindings")
    def test_list_role_bindings_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/rbac/role-bindings")
        assert response.status_code == 500

    def test_list_role_bindings_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/rbac/role-bindings")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/rbac/cluster-role-bindings
# ---------------------------------------------------------------------------

class TestListClusterRoleBindings:
    """Tests for the list_cluster_role_bindings endpoint."""

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_role_bindings")
    def test_list_cluster_role_bindings_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of cluster role bindings."""
        mock_list.return_value = [
            {"name": "cluster-admin-binding", "roleRef": "cluster-admin"},
        ]

        response = authed_client.get("/v2/kubernetes/rbac/cluster-role-bindings")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 1
        assert "pagination" in body["data"]

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_role_bindings")
    def test_list_cluster_role_bindings_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list and proper pagination."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/cluster-role-bindings")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 1

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_role_bindings")
    def test_list_cluster_role_bindings_pagination(self, mock_list, authed_client):
        """Should paginate results when page parameter is provided."""
        mock_list.return_value = [
            {"name": f"binding-{i}", "roleRef": "cluster-admin"}
            for i in range(6)
        ]

        response = authed_client.get("/v2/kubernetes/rbac/cluster-role-bindings?page=2&limit=2")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["total"] == 6
        assert body["data"]["pagination"]["pages"] == 3

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_cluster_role_bindings")
    def test_list_cluster_role_bindings_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/rbac/cluster-role-bindings")
        assert response.status_code == 500

    def test_list_cluster_role_bindings_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/rbac/cluster-role-bindings")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/cluster/rbac/service-accounts
# ---------------------------------------------------------------------------

class TestListServiceAccounts:
    """Tests for the list_service_accounts endpoint."""

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_service_accounts")
    def test_list_service_accounts_success(self, mock_list, authed_client):
        """Should return 200 with a paginated list of service accounts."""
        mock_list.return_value = [
            {"name": "default", "namespace": "staging"},
            {"name": "concord-api", "namespace": "staging"},
        ]

        response = authed_client.get("/v2/kubernetes/rbac/service-accounts")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert len(body["data"]["data"]) == 2
        assert "pagination" in body["data"]

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_service_accounts")
    def test_list_service_accounts_with_namespace(self, mock_list, authed_client):
        """Should pass namespace query param to the service layer."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/service-accounts?namespace=staging")
        assert response.status_code == 200

        mock_list.assert_called_once_with(namespace="staging")

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_service_accounts")
    def test_list_service_accounts_empty(self, mock_list, authed_client):
        """Should return 200 with an empty list and proper pagination."""
        mock_list.return_value = []

        response = authed_client.get("/v2/kubernetes/rbac/service-accounts")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 1

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_service_accounts")
    def test_list_service_accounts_pagination(self, mock_list, authed_client):
        """Should paginate results when page parameter is provided."""
        mock_list.return_value = [
            {"name": f"sa-{i}", "namespace": "default"}
            for i in range(5)
        ]

        response = authed_client.get("/v2/kubernetes/rbac/service-accounts?page=2&limit=3")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert len(body["data"]["data"]) == 2  # 5 items, page 2 with limit 3 = items 3-4
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["total"] == 5
        assert body["data"]["pagination"]["pages"] == 2

    @patch("api.v2.kubernetes.rbac.rbac_svc.list_service_accounts")
    def test_list_service_accounts_k8s_error(self, mock_list, authed_client):
        """Should return 500 on K8s errors."""
        mock_list.side_effect = Exception("Timeout")

        response = authed_client.get("/v2/kubernetes/rbac/service-accounts")
        assert response.status_code == 500

    def test_list_service_accounts_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/kubernetes/rbac/service-accounts")
        assert response.status_code == 401
