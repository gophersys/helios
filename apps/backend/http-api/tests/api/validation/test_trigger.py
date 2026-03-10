"""Integration tests for the Validation Run Trigger endpoint."""

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from tests.conftest import make_obj


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_product(id="prod-1", name="Alpha"):
    return make_obj(id=id, name=name)


def _make_bench(**overrides):
    defaults = dict(
        id="bench-1",
        stationId="bench-33",
        name="Test Bench",
        status="AVAILABLE",
        nodeId="node-1",
        mtibAddress="10.4.45.33:50053",
        mtibRevision="1.2",
        fixtureDesignId=None,
        profileOverrides={},
        capabilities=["button"],
        dutDeviceId="70B3D584C01E1FCC",
        dutSnr="0964",
        dutProduct="alpha",
        dutRevision="b0",
        dutImei=None,
        dutIccids=[],
        jlinkAppSerial=None,
        jlinkCommsSerial=None,
        uartAppPath=None,
        uartCommsPath=None,
        lockedBy=None,
        lockedAt=None,
        lastHealthCheck=None,
        metadata={},
        createdAt=NOW,
        updatedAt=NOW,
        node=None,
        fixtureDesign=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


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


# ── Trigger Run ──────────────────────────────────────────


def test_trigger_run_not_found(authed_client, mock_db):
    """Test triggering a non-existent run returns 404."""
    mock_db.session.find_unique.return_value = None

    response = authed_client.post(
        "/v2/validation/runs/bad-id/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert response.status_code == 404


def test_trigger_run_already_completed(authed_client, mock_db):
    """Test triggering a completed run returns 400."""
    mock_db.session.find_unique.return_value = _make_session(status="COMPLETED")

    response = authed_client.post(
        "/v2/validation/runs/sess-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "COMPLETED" in data["errors"][0]["message"]


def test_trigger_run_missing_firmware_version(authed_client, mock_db):
    """Test triggering without firmwareVersion returns 400."""
    response = authed_client.post(
        "/v2/validation/runs/sess-1/trigger",
        data=json.dumps({"firmwarePath": "/some/path"}),
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["errors"][0]["message"] == "firmwareVersion is required"


@patch("api.v2.validation.runs.trigger.create_kubernetes_job")
@patch("api.v2.validation.runs.trigger.log_audit")
def test_trigger_run_success(mock_audit, mock_k8s, authed_client, mock_db):
    """Test successful trigger creates K8s job."""
    mock_db.session.find_unique.return_value = _make_session()
    mock_db.testbench.find_first.return_value = _make_bench()
    mock_k8s.return_value = "alpha-val-sess-1-0-1-12"

    response = authed_client.post(
        "/v2/validation/runs/sess-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["jobName"] == "alpha-val-sess-1-0-1-12"
    assert data["data"]["runId"] == "sess-1"

    mock_k8s.assert_called_once()
    # Audit called twice: once for bench lock, once for trigger
    assert mock_audit.call_count == 2


@patch("api.v2.validation.runs.trigger.create_kubernetes_job")
@patch("api.v2.validation.runs.trigger.log_audit")
def test_trigger_run_k8s_failure(mock_audit, mock_k8s, authed_client, mock_db):
    """Test K8s job creation failure returns 500."""
    mock_db.session.find_unique.return_value = _make_session()
    mock_db.testbench.find_first.return_value = _make_bench()
    mock_k8s.return_value = None  # Simulate failure

    response = authed_client.post(
        "/v2/validation/runs/sess-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert response.status_code == 500


def test_trigger_run_no_bench_available(authed_client, mock_db):
    """Test triggering when no bench is available returns 400."""
    mock_db.session.find_unique.return_value = _make_session()
    mock_db.testbench.find_first.return_value = None  # No bench available

    response = authed_client.post(
        "/v2/validation/runs/sess-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "No available test bench" in data["errors"][0]["message"]


def test_trigger_run_unauthorized(client):
    """Test triggering without auth returns 401."""
    response = client.post(
        "/v2/validation/runs/sess-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
        content_type="application/json",
    )
    assert response.status_code == 401
