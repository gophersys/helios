"""Integration tests for the Validation Runs API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_product(id="prod-1", name="Alpha"):
    return make_obj(id=id, name=name)


def _make_node(id="node-1", name="mtib-33"):
    return make_obj(id=id, name=name)


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
        createdBy=make_obj(id="user-1", name="Test User", email="test@example.com"),
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


# ── Create Run ───────────────────────────────────────────


def test_create_run(authed_client, mock_db):
    """Test creating a new validation run."""
    mock_db.product.find_unique.return_value = _make_product()
    mock_db.node.find_unique.return_value = _make_node()

    session = _make_session()
    mock_db.session.create.return_value = session
    mock_db.device.create.return_value = _make_device()
    mock_db.test.find_many.return_value = [_make_test()]
    mock_db.testexecution.create.return_value = _make_execution()
    mock_db.session.update.return_value = session

    with patch("src.api.v2.sessions.runs.log_audit"):
        response = authed_client.post(
            "/v2/sessions",
            data=json.dumps({
                "name": "Alpha REV1.2 Debug",
                "productId": "prod-1",
                "nodeId": "node-1",
                "serialNumber": "70B3D584C01E1FCC",
                "firmwareVariant": "debug",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "sess-1"
    assert data["data"]["name"] == "Alpha REV1.2 Debug"
    assert data["data"]["executionCount"] == 1


def test_create_run_product_not_found(authed_client, mock_db):
    """Test creating a run with non-existent product returns 404."""
    mock_db.product.find_unique.return_value = None

    response = authed_client.post(
        "/v2/sessions",
        data=json.dumps({
            "name": "Test",
            "productId": "bad-id",
            "nodeId": "node-1",
            "serialNumber": "ABC",
        }),
    )

    assert response.status_code == 404


def test_create_run_missing_name(authed_client, mock_db):
    """Test creating a run without name returns 400."""
    response = authed_client.post(
        "/v2/sessions",
        data=json.dumps({
            "productId": "prod-1",
            "nodeId": "node-1",
            "serialNumber": "ABC",
        }),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["errors"][0]["message"] == "Name is required"


def test_create_run_unauthorized(client):
    """Test creating a run without auth returns 401."""
    response = client.post(
        "/v2/sessions",
        data=json.dumps({"name": "Test"}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ── List Runs ────────────────────────────────────────────


def test_list_runs(authed_client, mock_db):
    """Test listing runs with pagination."""
    mock_db.session.count.return_value = 1
    mock_db.session.find_many.return_value = [_make_session()]

    response = authed_client.get("/v2/sessions")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 1
    assert data["data"]["pagination"]["total"] == 1


def test_list_runs_with_status_filter(authed_client, mock_db):
    """Test listing runs filtered by status."""
    mock_db.session.count.return_value = 0
    mock_db.session.find_many.return_value = []

    response = authed_client.get("/v2/sessions?status=completed")
    assert response.status_code == 200


# ── Get Run ──────────────────────────────────────────────


def test_get_run(authed_client, mock_db):
    """Test getting a single run with details."""
    device = _make_device(executions=[
        _make_execution(
            test=_make_test(),
            results=[make_obj(id="r1", executionId="exec-1", stepIndex=0, groupIndex=0, passed=True, result={}, createdAt=NOW)],
        ),
    ])
    session = _make_session(devices=[device])
    mock_db.session.find_unique.return_value = session

    response = authed_client.get("/v2/sessions/sess-1")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "sess-1"
    assert "devices" in data["data"]
    assert "executions" in data["data"]


def test_get_run_not_found(authed_client, mock_db):
    """Test getting a non-existent run returns 404."""
    mock_db.session.find_unique.return_value = None

    response = authed_client.get("/v2/sessions/bad-id")
    assert response.status_code == 404


# ── Cancel Run ───────────────────────────────────────────


def test_cancel_run(authed_client, mock_db):
    """Test cancelling an active run."""
    from unittest.mock import MagicMock

    mock_db.session.find_unique.return_value = _make_session(status="ACTIVE")
    mock_db.session.update.return_value = _make_session(status="CANCELLED")
    mock_db.testexecution.update_many = MagicMock(return_value=None)

    with patch("src.api.v2.sessions.runs.log_audit"):
        response = authed_client.post("/v2/sessions/sess-1/cancel")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "CANCELLED"


def test_cancel_completed_run(authed_client, mock_db):
    """Test cancelling a completed run returns 409."""
    mock_db.session.find_unique.return_value = _make_session(status="PASSED")

    response = authed_client.post("/v2/sessions/sess-1/cancel")
    assert response.status_code == 409


# ── Reporter: Start ──────────────────────────────────────


def test_report_start(authed_client, mock_db):
    """Test reporter start callback."""
    mock_db.session.find_unique.return_value = _make_session(status="ACTIVE")

    response = authed_client.post(
        "/v2/sessions/sess-1/report/start",
        data=json.dumps({"started": True}),
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "ACTIVE"


def test_report_start_not_found(authed_client, mock_db):
    """Test reporter start on non-existent run returns 404."""
    mock_db.session.find_unique.return_value = None

    response = authed_client.post(
        "/v2/sessions/bad/report/start",
        data=json.dumps({"started": True}),
    )
    assert response.status_code == 404


# ── Reporter: Test Start ────────────────────────────────


def test_report_test_start(authed_client, mock_db):
    """Test reporter test-start callback creates/updates execution."""
    session = _make_session(config={"nodeId": "node-1", "serialNumber": "70B3D584C01E1FCC"})
    mock_db.session.find_unique.return_value = session
    mock_db.test.find_first.return_value = _make_test()
    mock_db.device.find_first.return_value = _make_device()
    mock_db.testexecution.find_first.return_value = _make_execution()

    response = authed_client.post(
        "/v2/sessions/sess-1/report/test-start",
        data=json.dumps({
            "testName": "test_boot.test_power_cycle",
            "module": "boot",
        }),
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["testName"] == "test_boot.test_power_cycle"
    assert data["data"]["status"] == "RUNNING"


def test_report_test_start_auto_creates_test(authed_client, mock_db):
    """Test reporter test-start auto-creates test if not found."""
    session = _make_session(config={"nodeId": "node-1", "serialNumber": "70B3D584C01E1FCC"})
    mock_db.session.find_unique.return_value = session
    mock_db.test.find_first.return_value = None  # Test doesn't exist yet
    new_test = _make_test(id="test-new", name="test_new.test_something")
    mock_db.test.create.return_value = new_test
    mock_db.device.find_first.return_value = _make_device()
    mock_db.testexecution.find_first.return_value = None  # No execution yet
    mock_db.testexecution.create.return_value = _make_execution(id="exec-new")

    response = authed_client.post(
        "/v2/sessions/sess-1/report/test-start",
        data=json.dumps({
            "testName": "test_new.test_something",
            "module": "new",
        }),
    )

    assert response.status_code == 200
    mock_db.test.create.assert_called_once()
    mock_db.testexecution.create.assert_called_once()


# ── Reporter: Test Result ────────────────────────────────


def test_report_test_result(authed_client, mock_db):
    """Test reporting a test result."""
    mock_db.session.find_unique.return_value = _make_session()
    mock_db.test.find_first.return_value = _make_test()
    mock_db.device.find_first.return_value = _make_device()
    mock_db.testexecution.find_first.return_value = _make_execution()
    mock_db.teststep.count.return_value = 0
    mock_db.teststep.create.return_value = make_obj(
        id="result-1", executionId="exec-1", stepIndex=0, groupIndex=0, passed=True, result={}, createdAt=NOW,
    )

    response = authed_client.post(
        "/v2/sessions/sess-1/report/test-result",
        data=json.dumps({
            "testName": "test_boot.test_power_cycle",
            "passed": True,
            "durationS": 1.5,
            "measurements": {"currentMa": 33.5},
        }),
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["passed"] is True


# ── Reporter: Finish ─────────────────────────────────────


def test_report_finish(authed_client, mock_db):
    """Test reporter finish callback."""
    mock_db.session.find_unique.return_value = _make_session()
    mock_db.device.find_first.return_value = _make_device()

    response = authed_client.post(
        "/v2/sessions/sess-1/report/finish",
        data=json.dumps({
            "total": 37,
            "passed": 35,
            "failed": 2,
            "errors": 0,
            "durationS": 120.0,
        }),
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "FAILED"
    assert data["data"]["total"] == 37
    assert data["data"]["passed"] == 35
