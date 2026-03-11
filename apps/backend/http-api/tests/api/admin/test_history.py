"""Integration tests for the Admin History API (audit log endpoints).

Endpoints under test:
    GET  /v2/system/history            — list_history (paginated, filterable)
    GET  /v2/system/history/<entry_id> — get_history_entry
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _audit_entry(**overrides):
    """Build a mock AuditLog row with sensible defaults."""
    defaults = {
        "id": "audit-001",
        "userId": "user-abc",
        "action": "product.create",
        "entityType": "Product",
        "entityId": "prod-123",
        "details": {"name": "Widget"},
        "ipAddress": "10.0.0.1",
        "createdAt": datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
        "user": make_obj(
            id="user-abc",
            name="Alice",
            email="alice@example.com",
        ),
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# GET /v2/system/history — list_history
# ---------------------------------------------------------------------------

class TestListHistory:
    """Tests for the list_history endpoint."""

    def test_list_history_success(self, authed_client, mock_db):
        """Should return paginated audit entries with user info."""
        entry1 = _audit_entry(id="audit-001", action="product.create")
        entry2 = _audit_entry(
            id="audit-002",
            userId="user-def",
            action="user.delete",
            entityType="User",
            entityId="user-xyz",
            details={"email": "deleted@example.com"},
            ipAddress="192.168.1.1",
            createdAt=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
            user=make_obj(id="user-def", name="Bob", email="bob@example.com"),
        )

        mock_db.auditlog.count.return_value = 2
        mock_db.auditlog.find_many.return_value = [entry2, entry1]

        response = authed_client.get("/v2/system/history")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        payload = body["data"]
        assert payload["pagination"]["total"] == 2
        assert payload["pagination"]["page"] == 1
        assert len(payload["data"]) == 2

        first = payload["data"][0]
        assert first["id"] == "audit-002"
        assert first["action"] == "user.delete"
        assert first["user"]["name"] == "Bob"

    def test_list_history_empty(self, authed_client, mock_db):
        """Should return empty list with zero total when no audit entries."""
        mock_db.auditlog.count.return_value = 0
        mock_db.auditlog.find_many.return_value = []

        response = authed_client.get("/v2/system/history")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["pages"] == 0

    def test_list_history_pagination(self, authed_client, mock_db):
        """Should respect page and limit query params."""
        mock_db.auditlog.count.return_value = 150
        mock_db.auditlog.find_many.return_value = [_audit_entry()]

        response = authed_client.get("/v2/system/history?page=3&limit=25")
        assert response.status_code == 200

        body = json.loads(response.data)
        pagination = body["data"]["pagination"]
        assert pagination["page"] == 3
        assert pagination["limit"] == 25
        assert pagination["total"] == 150
        assert pagination["pages"] == 6  # ceil(150/25)

        # Verify skip/take passed to find_many
        call_kwargs = mock_db.auditlog.find_many.call_args
        assert call_kwargs.kwargs["skip"] == 50  # (3-1)*25
        assert call_kwargs.kwargs["take"] == 25

    def test_list_history_limit_clamped_to_100(self, authed_client, mock_db):
        """Limit should be capped at 100 even if a larger value is requested."""
        mock_db.auditlog.count.return_value = 0
        mock_db.auditlog.find_many.return_value = []

        response = authed_client.get("/v2/system/history?limit=500")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["pagination"]["limit"] == 100

    def test_list_history_limit_minimum_is_1(self, authed_client, mock_db):
        """Limit should be at least 1 even if 0 or negative is requested."""
        mock_db.auditlog.count.return_value = 0
        mock_db.auditlog.find_many.return_value = []

        response = authed_client.get("/v2/system/history?limit=0")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["pagination"]["limit"] == 1

    def test_list_history_filter_by_entity_type(self, authed_client, mock_db):
        """Should filter by entityType query param."""
        mock_db.auditlog.count.return_value = 1
        mock_db.auditlog.find_many.return_value = [_audit_entry(entityType="User")]

        response = authed_client.get("/v2/system/history?entityType=User")
        assert response.status_code == 200

        call_kwargs = mock_db.auditlog.find_many.call_args
        where = call_kwargs.kwargs["where"]
        assert where["entityType"] == "User"

    def test_list_history_filter_by_action(self, authed_client, mock_db):
        """Should filter by action (partial match via contains)."""
        mock_db.auditlog.count.return_value = 1
        mock_db.auditlog.find_many.return_value = [_audit_entry(action="product.create")]

        response = authed_client.get("/v2/system/history?action=product")
        assert response.status_code == 200

        call_kwargs = mock_db.auditlog.find_many.call_args
        where = call_kwargs.kwargs["where"]
        assert where["action"] == {"contains": "product"}

    def test_list_history_filter_by_user_id(self, authed_client, mock_db):
        """Should filter by userId query param."""
        mock_db.auditlog.count.return_value = 1
        mock_db.auditlog.find_many.return_value = [_audit_entry()]

        response = authed_client.get("/v2/system/history?userId=user-abc")
        assert response.status_code == 200

        call_kwargs = mock_db.auditlog.find_many.call_args
        where = call_kwargs.kwargs["where"]
        assert where["userId"] == "user-abc"

    def test_list_history_filter_by_date_range(self, authed_client, mock_db):
        """Should filter by from/to date range."""
        mock_db.auditlog.count.return_value = 1
        mock_db.auditlog.find_many.return_value = [_audit_entry()]

        response = authed_client.get(
            "/v2/system/history?from=2026-03-01T00:00:00&to=2026-03-31T23:59:59"
        )
        assert response.status_code == 200

        call_kwargs = mock_db.auditlog.find_many.call_args
        where = call_kwargs.kwargs["where"]
        assert "createdAt" in where
        assert "gte" in where["createdAt"]
        assert "lte" in where["createdAt"]

    def test_list_history_invalid_from_date(self, authed_client, mock_db):
        """Should return 400 for invalid 'from' date format."""
        response = authed_client.get("/v2/system/history?from=not-a-date")
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "from" in body["errors"][0]["message"].lower()

    def test_list_history_invalid_to_date(self, authed_client, mock_db):
        """Should return 400 for invalid 'to' date format."""
        response = authed_client.get("/v2/system/history?to=garbage")
        assert response.status_code == 400

        body = json.loads(response.data)
        assert len(body["errors"]) > 0
        assert "to" in body["errors"][0]["message"].lower()

    def test_list_history_multiple_filters(self, authed_client, mock_db):
        """Should combine multiple filters in the where clause."""
        mock_db.auditlog.count.return_value = 0
        mock_db.auditlog.find_many.return_value = []

        response = authed_client.get(
            "/v2/system/history?entityType=Product&action=create&userId=user-abc"
        )
        assert response.status_code == 200

        call_kwargs = mock_db.auditlog.find_many.call_args
        where = call_kwargs.kwargs["where"]
        assert where["entityType"] == "Product"
        assert where["action"] == {"contains": "create"}
        assert where["userId"] == "user-abc"

    def test_list_history_entry_without_user(self, authed_client, mock_db):
        """Should serialize user as null when entry has no associated user."""
        entry = _audit_entry(user=None)
        mock_db.auditlog.count.return_value = 1
        mock_db.auditlog.find_many.return_value = [entry]

        response = authed_client.get("/v2/system/history")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["data"][0]["user"] is None

    def test_list_history_ordering(self, authed_client, mock_db):
        """Results should be ordered by createdAt descending."""
        mock_db.auditlog.count.return_value = 0
        mock_db.auditlog.find_many.return_value = []

        authed_client.get("/v2/system/history")

        call_kwargs = mock_db.auditlog.find_many.call_args
        assert call_kwargs.kwargs["order"] == {"createdAt": "desc"}

    def test_list_history_includes_user_relation(self, authed_client, mock_db):
        """The query should eagerly include the user relation."""
        mock_db.auditlog.count.return_value = 0
        mock_db.auditlog.find_many.return_value = []

        authed_client.get("/v2/system/history")

        call_kwargs = mock_db.auditlog.find_many.call_args
        assert call_kwargs.kwargs["include"] == {"user": True}

    def test_list_history_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/system/history")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /v2/system/history/<entry_id> — get_history_entry
# ---------------------------------------------------------------------------

class TestGetHistoryEntry:
    """Tests for the get_history_entry endpoint."""

    def test_get_entry_success(self, authed_client, mock_db):
        """Should return a single audit log entry with user info."""
        entry = _audit_entry(
            id="audit-specific",
            action="codebase.update",
            entityType="Codebase",
            entityId="cb-456",
        )
        mock_db.auditlog.find_unique.return_value = entry

        response = authed_client.get("/v2/system/history/audit-specific")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["errors"] == []
        assert body["data"]["id"] == "audit-specific"
        assert body["data"]["action"] == "codebase.update"
        assert body["data"]["entityType"] == "Codebase"
        assert body["data"]["entityId"] == "cb-456"
        assert body["data"]["user"]["name"] == "Alice"
        assert body["data"]["user"]["email"] == "alice@example.com"
        assert "createdAt" in body["data"]

    def test_get_entry_not_found(self, authed_client, mock_db):
        """Should return 404 for a non-existent entry."""
        mock_db.auditlog.find_unique.return_value = None

        response = authed_client.get("/v2/system/history/nonexistent")
        assert response.status_code == 404

        body = json.loads(response.data)
        assert len(body["errors"]) > 0

    def test_get_entry_without_user(self, authed_client, mock_db):
        """Should serialize user as null when the entry has no linked user."""
        entry = _audit_entry(id="audit-no-user", userId=None, user=None)
        mock_db.auditlog.find_unique.return_value = entry

        response = authed_client.get("/v2/system/history/audit-no-user")
        assert response.status_code == 200

        body = json.loads(response.data)
        assert body["data"]["user"] is None

    def test_get_entry_includes_all_fields(self, authed_client, mock_db):
        """All expected fields should be present in the response."""
        entry = _audit_entry()
        mock_db.auditlog.find_unique.return_value = entry

        response = authed_client.get("/v2/system/history/audit-001")
        assert response.status_code == 200

        body = json.loads(response.data)
        data = body["data"]
        expected_keys = {"id", "userId", "action", "entityType", "entityId",
                         "details", "ipAddress", "createdAt", "user"}
        assert expected_keys == set(data.keys())

    def test_get_entry_queries_with_include(self, authed_client, mock_db):
        """The find_unique call should include the user relation."""
        mock_db.auditlog.find_unique.return_value = _audit_entry()

        authed_client.get("/v2/system/history/audit-001")

        call_kwargs = mock_db.auditlog.find_unique.call_args
        assert call_kwargs.kwargs["include"] == {"user": True}
        assert call_kwargs.kwargs["where"] == {"id": "audit-001"}

    def test_get_entry_requires_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/v2/system/history/audit-001")
        assert response.status_code == 401
