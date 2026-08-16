"""Tests for runs/trigger.py -- trigger K8s validation jobs for a TestRun."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make_product(id="prod-1", name="Alpha", slug="alpha"):
    return make_obj(id=id, name=name, slug=slug)


def _make_node(**overrides):
    defaults = dict(
        id="node-1",
        hostname="verdin-33",
        ipAddress="192.168.1.100",
        status="ONLINE",
        type="VALIDATION",
        metadata={},
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_slot(**overrides):
    defaults = dict(
        id="slot-1",
        fixtureId="fix-1",
        slotIndex=0,
        active=True,
        dutDeviceId="70B3D584C01E1FCC",
        dutSnr="0964",
        dutImei=None,
        dutIccids=[],
        nodeId="node-1",
        node=_make_node(),
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_design(**overrides):
    defaults = dict(
        id="design-1",
        name="alpha-fixture",
        product="alpha",
        revision="b0",
        profileTemplate={},
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_fixture(**overrides):
    defaults = dict(
        id="fix-1",
        stationId="bench-33",
        name="Test Bench",
        productId="prod-1",
        active=True,
        profileOverrides={},
        design=_make_design(),
        slots=[_make_slot()],
        lastHealthCheck=None,
        metadata={},
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_run(**overrides):
    defaults = dict(
        id="run-1",
        type="VALIDATION",
        name="Alpha Smoke Run",
        productId="prod-1",
        fixtureId=None,
        status="ACTIVE",
        config={"nodeId": "node-1"},
        targetCount=1,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        startedAt=NOW,
        completedAt=None,
        notes=None,
        createdAt=NOW,
        updatedAt=NOW,
        product=_make_product(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trigger_run_not_found(authed_client, mock_db):
    """Triggering a non-existent run returns 404."""
    mock_db.testrun.find_unique.return_value = None

    resp = authed_client.post(
        "/v2/runs/bad-id/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert resp.status_code == 404


def test_trigger_run_wrong_status(authed_client, mock_db):
    """Triggering a non-ACTIVE run returns 400."""
    mock_db.testrun.find_unique.return_value = _make_run(status="COMPLETED")

    resp = authed_client.post(
        "/v2/runs/run-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert "COMPLETED" in data["errors"][0]["message"]


def test_trigger_run_missing_firmware_version(authed_client, mock_db):
    """Triggering without firmwareVersion returns 400."""
    resp = authed_client.post(
        "/v2/runs/run-1/trigger",
        data=json.dumps({"firmwarePath": "/some/path"}),
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["errors"][0]["message"] == "firmwareVersion is required"


@patch("api.v2.runs.trigger.create_kubernetes_job")
@patch("api.v2.runs.trigger.log_audit")
@patch("api.v2.runs.trigger._create_run_api_key", return_value="ck_run_test_key")
def test_trigger_run_success(mock_api_key, mock_audit, mock_k8s, authed_client, mock_db):
    """Successful trigger creates RunTargets and K8s jobs."""
    mock_db.testrun.find_unique.return_value = _make_run()
    mock_db.fixture.find_first.return_value = _make_fixture()
    mock_db.node.find_unique.return_value = _make_node()
    mock_db.runtarget.create.return_value = make_obj(id="target-1")
    mock_k8s.return_value = "alpha-val-run-1-s0-0-1-12"

    resp = authed_client.post(
        "/v2/runs/run-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["data"]["runId"] == "run-1"
    assert data["data"]["slotCount"] == 1
    assert len(data["data"]["jobNames"]) == 1

    mock_k8s.assert_called_once()
    # Audit: fixture lock + trigger
    assert mock_audit.call_count == 2


@patch("api.v2.runs.trigger.create_kubernetes_job")
@patch("api.v2.runs.trigger.log_audit")
@patch("api.v2.runs.trigger._create_run_api_key", return_value="ck_run_test_key")
def test_trigger_run_k8s_failure(mock_api_key, mock_audit, mock_k8s, authed_client, mock_db):
    """K8s job creation failure returns 500."""
    mock_db.testrun.find_unique.return_value = _make_run()
    mock_db.fixture.find_first.return_value = _make_fixture()
    mock_db.node.find_unique.return_value = _make_node()
    mock_db.runtarget.create.return_value = make_obj(id="target-1")
    mock_k8s.return_value = None  # Job creation failed

    resp = authed_client.post(
        "/v2/runs/run-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert resp.status_code == 500


def test_trigger_run_no_fixture_available(authed_client, mock_db):
    """No available fixture for the product returns 400."""
    mock_db.testrun.find_unique.return_value = _make_run()
    mock_db.fixture.find_first.return_value = None

    resp = authed_client.post(
        "/v2/runs/run-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert "No available fixture" in data["errors"][0]["message"]


def test_trigger_run_unauthorized(client):
    """Triggering without auth returns 401."""
    resp = client.post(
        "/v2/runs/run-1/trigger",
        data=json.dumps({"firmwareVersion": "0.1.12"}),
        content_type="application/json",
    )
    assert resp.status_code == 401
