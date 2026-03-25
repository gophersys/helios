"""Unit tests for the Validation Runs CRUD endpoints.

Tests the create, list, get, and cancel operations on
/v2/sessions/ using the mock DB + authed client pattern.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ── Helpers ──────────────────────────────────────────────


def _make_product(id="prod-1", name="Alpha"):
    return make_obj(id=id, name=name)


def _make_node(id="node-1", name="mtib-33"):
    return make_obj(id=id, name=name)


def _make_user(id="user-1", name="Test User", email="test@example.com"):
    return make_obj(id=id, name=name, email=email)


def _make_session(**overrides):
    defaults = dict(
        id="sess-1",
        name="Alpha REV1.2 Debug",
        productId="prod-1",
        fixtureId=None,
        status="ACTIVE",
        config={"nodeId": "node-1", "serialNumber": "70B3D584C01E1FCC"},
        targetCount=3,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        startedAt=NOW,
        finishedAt=None,
        notes=None,
        createdAt=NOW,
        updatedAt=NOW,
        product=_make_product(),
        createdBy=_make_user(),
        devices=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_device(**overrides):
    defaults = dict(
        id="dev-1",
        serialNumber="70B3D584C01E1FCC",
        sessionId="sess-1",
        status="PENDING",
        metadata=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_test(**overrides):
    defaults = dict(
        id="test-1",
        name="test_boot.test_power_cycle",
        productId="prod-1",
        category="boot",
        enabled=True,
        sortOrder=0,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_execution(**overrides):
    defaults = dict(
        id="exec-1",
        testId="test-1",
        nodeId="node-1",
        deviceId="dev-1",
        status="QUEUED",
        config=None,
        startedAt=None,
        finishedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ── CreateRun ────────────────────────────────────────────


class TestCreateRun:

    def test_create_run_minimal(self, authed_client, mock_db):
        """Create a run with only required fields."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.node.find_unique.return_value = _make_node()
        mock_db.session.create.return_value = _make_session(notes=None)
        mock_db.device.create.return_value = _make_device()
        mock_db.test.find_many.return_value = []
        mock_db.session.update.return_value = _make_session(targetCount=0)

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post(
                "/v2/sessions",
                data=json.dumps({
                    "name": "Minimal Run",
                    "productId": "prod-1",
                    "nodeId": "node-1",
                    "serialNumber": "ABC123",
                }),
            )

        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert body["errors"] == []
        assert body["data"]["id"] == "sess-1"
        assert body["data"]["executionCount"] == 0

    def test_create_run_with_all_fields(self, authed_client, mock_db):
        """Create a run providing every optional field."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.node.find_unique.return_value = _make_node()

        session = _make_session(
            notes="Full run with firmware debug variant",
            config={
                "nodeId": "node-1",
                "serialNumber": "70B3D584C01E1FCC",
                "firmwareVariant": "debug",
                "custom": "value",
            },
        )
        mock_db.session.create.return_value = session
        mock_db.device.create.return_value = _make_device()

        tests = [
            _make_test(id="t1", name="test_boot.test_power_cycle", sortOrder=0),
            _make_test(id="t2", name="test_boot.test_uart_output", sortOrder=1),
        ]
        mock_db.test.find_many.return_value = tests

        exec1 = _make_execution(id="e1", testId="t1")
        exec2 = _make_execution(id="e2", testId="t2")
        mock_db.testexecution.create.side_effect = [exec1, exec2]
        mock_db.session.update.return_value = session

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post(
                "/v2/sessions",
                data=json.dumps({
                    "name": "Full Run",
                    "productId": "prod-1",
                    "nodeId": "node-1",
                    "serialNumber": "70B3D584C01E1FCC",
                    "firmwareVariant": "debug",
                    "config": {"custom": "value"},
                    "notes": "Full run with firmware debug variant",
                    "testFilter": ["test_boot.test_power_cycle", "test_boot.test_uart_output"],
                }),
            )

        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert body["data"]["executionCount"] == 2
        assert body["data"]["devices"][0]["serialNumber"] == "70B3D584C01E1FCC"

    def test_create_run_missing_product_id(self, authed_client, mock_db):
        """Missing productId returns 400."""
        resp = authed_client.post(
            "/v2/sessions",
            data=json.dumps({
                "name": "Test",
                "nodeId": "node-1",
                "serialNumber": "ABC",
            }),
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert body["errors"][0]["message"] == "productId is required"

    def test_create_run_product_not_found(self, authed_client, mock_db):
        """Non-existent product returns 404."""
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/sessions",
            data=json.dumps({
                "name": "Test",
                "productId": "bad-id",
                "nodeId": "node-1",
                "serialNumber": "ABC",
            }),
        )

        assert resp.status_code == 404
        body = json.loads(resp.data)
        assert "Product not found" in body["errors"][0]["message"]

    def test_create_run_node_not_found(self, authed_client, mock_db):
        """Non-existent node returns 404."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.node.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/sessions",
            data=json.dumps({
                "name": "Test",
                "productId": "prod-1",
                "nodeId": "bad-node",
                "serialNumber": "ABC",
            }),
        )

        assert resp.status_code == 404
        body = json.loads(resp.data)
        assert "Node not found" in body["errors"][0]["message"]

    def test_create_run_unauthorized(self, client):
        """No auth header returns 401."""
        resp = client.post(
            "/v2/sessions",
            data=json.dumps({"name": "Test"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


# ── ListRuns ─────────────────────────────────────────────


class TestListRuns:

    def test_list_runs_empty(self, authed_client, mock_db):
        """Empty list returns valid pagination with zero items."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        resp = authed_client.get("/v2/sessions")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        payload = body["data"]
        assert payload["data"] == []
        assert payload["pagination"]["total"] == 0
        assert payload["pagination"]["page"] == 1

    def test_list_runs_with_results(self, authed_client, mock_db):
        """List returns serialized sessions with product and devices."""
        device = _make_device()
        session = _make_session(devices=[device])
        mock_db.session.count.return_value = 1
        mock_db.session.find_many.return_value = [session]

        resp = authed_client.get("/v2/sessions")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        items = body["data"]["data"]
        assert len(items) == 1
        assert items[0]["id"] == "sess-1"
        assert items[0]["product"]["name"] == "Alpha"
        assert items[0]["createdBy"]["email"] == "test@example.com"
        assert len(items[0]["devices"]) == 1

    def test_list_runs_pagination(self, authed_client, mock_db):
        """Pagination params are forwarded correctly."""
        mock_db.session.count.return_value = 150
        mock_db.session.find_many.return_value = []

        resp = authed_client.get("/v2/sessions?page=3&limit=25")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        pagination = body["data"]["pagination"]
        assert pagination["page"] == 3
        assert pagination["limit"] == 25
        assert pagination["total"] == 150
        assert pagination["pages"] == 6  # ceil(150/25)

        # Verify skip/take args passed to DB
        call_kwargs = mock_db.session.find_many.call_args[1]
        assert call_kwargs["skip"] == 50  # (3-1)*25
        assert call_kwargs["take"] == 25

    def test_list_runs_filter_by_status(self, authed_client, mock_db):
        """Status query param filters sessions."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        resp = authed_client.get("/v2/sessions?status=passed")
        assert resp.status_code == 200

        # Verify the where clause includes status
        count_where = mock_db.session.count.call_args[1]["where"]
        assert count_where["status"] == "PASSED"

    def test_list_runs_filter_by_product(self, authed_client, mock_db):
        """productId query param filters sessions."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        resp = authed_client.get("/v2/sessions?productId=prod-1")
        assert resp.status_code == 200

        count_where = mock_db.session.count.call_args[1]["where"]
        assert count_where["productId"] == "prod-1"

    def test_list_runs_limit_clamped(self, authed_client, mock_db):
        """Limit is clamped to 100 max."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        resp = authed_client.get("/v2/sessions?limit=999")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["pagination"]["limit"] == 100


# ── GetRunDetail ─────────────────────────────────────────


class TestGetRunDetail:

    def test_get_run_detail(self, authed_client, mock_db):
        """Get returns full session with product and user."""
        session = _make_session()
        mock_db.session.find_unique.return_value = session

        resp = authed_client.get("/v2/sessions/sess-1")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["id"] == "sess-1"
        assert body["data"]["name"] == "Alpha REV1.2 Debug"
        assert body["data"]["product"]["name"] == "Alpha"
        assert body["data"]["createdBy"]["name"] == "Test User"

    def test_get_run_not_found(self, authed_client, mock_db):
        """Non-existent run returns 404."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.get("/v2/sessions/nonexistent")
        assert resp.status_code == 404

        body = json.loads(resp.data)
        assert "not found" in body["errors"][0]["message"].lower()

    def test_get_run_includes_executions(self, authed_client, mock_db):
        """Get detail includes nested executions with test info and results."""
        result = make_obj(
            id="r1",
            executionId="exec-1",
            stepIndex=0,
            groupIndex=0,
            passed=True,
            result={},
            createdAt=NOW,
        )
        execution = _make_execution(
            test=_make_test(),
            results=[result],
        )
        device = _make_device(executions=[execution])
        session = _make_session(devices=[device])
        mock_db.session.find_unique.return_value = session

        resp = authed_client.get("/v2/sessions/sess-1")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert "executions" in body["data"]
        assert len(body["data"]["executions"]) == 1

        ex = body["data"]["executions"][0]
        assert ex["testId"] == "test-1"
        assert ex["test"]["name"] == "test_boot.test_power_cycle"
        assert ex["stepCount"] == 1
        assert ex["stepsPassed"] == 1


# ── CancelRun ────────────────────────────────────────────


class TestCancelRun:

    def test_cancel_active_run(self, authed_client, mock_db):
        """Cancel an ACTIVE run sets status to CANCELLED."""
        mock_db.session.find_unique.return_value = _make_session(status="ACTIVE")
        mock_db.session.update.return_value = _make_session(status="CANCELLED")
        mock_db.testexecution.update_many = MagicMock(return_value=None)

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post("/v2/sessions/sess-1/cancel")

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["status"] == "CANCELLED"

        # Verify executions were bulk-cancelled
        mock_db.testexecution.update_many.assert_called_once()

    def test_cancel_paused_run(self, authed_client, mock_db):
        """Cancel a PENDING run also succeeds."""
        mock_db.session.find_unique.return_value = _make_session(status="PENDING")
        mock_db.session.update.return_value = _make_session(status="CANCELLED")
        mock_db.testexecution.update_many = MagicMock(return_value=None)

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post("/v2/sessions/sess-1/cancel")

        assert resp.status_code == 200

    def test_cancel_completed_run_fails(self, authed_client, mock_db):
        """Cancelling a PASSED run returns 409."""
        mock_db.session.find_unique.return_value = _make_session(status="PASSED")

        resp = authed_client.post("/v2/sessions/sess-1/cancel")
        assert resp.status_code == 409

        body = json.loads(resp.data)
        assert "PASSED" in body["errors"][0]["message"]

    def test_cancel_cancelled_run_fails(self, authed_client, mock_db):
        """Cancelling an already CANCELLED run returns 409."""
        mock_db.session.find_unique.return_value = _make_session(status="CANCELLED")

        resp = authed_client.post("/v2/sessions/sess-1/cancel")
        assert resp.status_code == 409

    def test_cancel_run_not_found(self, authed_client, mock_db):
        """Cancelling a non-existent run returns 404."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.post("/v2/sessions/nonexistent/cancel")
        assert resp.status_code == 404
