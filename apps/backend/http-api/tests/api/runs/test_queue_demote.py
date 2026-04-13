"""Tests for POST /v2/runs/queue/<id>/demote -- drop priority to min - 1."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from tests.conftest import make_obj


NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make_queue_entry(**overrides):
    defaults = dict(
        id="qe-1",
        assetSetId="as-1",
        stageConfigId=None,
        stage=4,
        priority=5,
        status="QUEUED",
        fixtureId=None,
        testRunId=None,
        reason=None,
        errorMessage=None,
        jobName=None,
        requestedAt=NOW,
        assignedAt=None,
        startedAt=None,
        completedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_demote_success(authed_client, mock_db):
    """Demoting a QUEUED entry sets priority to min(QUEUED) - 1."""
    entry = _make_queue_entry(priority=5)
    bottom = _make_queue_entry(id="qe-bottom", priority=3)
    demoted = _make_queue_entry(priority=2)

    mock_db.validationqueueentry.find_unique.return_value = entry
    mock_db.validationqueueentry.find_first.return_value = bottom
    mock_db.validationqueueentry.update.return_value = demoted

    resp = authed_client.post("/v2/runs/queue/qe-1/demote")
    assert resp.status_code == 200

    data = json.loads(resp.data)
    assert data["data"]["priority"] == 2

    mock_db.validationqueueentry.update.assert_called_once()
    call_kwargs = mock_db.validationqueueentry.update.call_args
    assert call_kwargs.kwargs["data"]["priority"] == 2


def test_demote_floors_at_zero(authed_client, mock_db):
    """When min priority is already 0, demoted priority stays at 0."""
    entry = _make_queue_entry(priority=0)
    bottom = _make_queue_entry(id="qe-bottom", priority=0)
    demoted = _make_queue_entry(priority=0)

    mock_db.validationqueueentry.find_unique.return_value = entry
    mock_db.validationqueueentry.find_first.return_value = bottom
    mock_db.validationqueueentry.update.return_value = demoted

    resp = authed_client.post("/v2/runs/queue/qe-1/demote")
    assert resp.status_code == 200

    data = json.loads(resp.data)
    assert data["data"]["priority"] == 0

    call_kwargs = mock_db.validationqueueentry.update.call_args
    assert call_kwargs.kwargs["data"]["priority"] == 0


def test_demote_rejects_non_queued(authed_client, mock_db):
    """Demoting a RUNNING entry returns 409."""
    entry = _make_queue_entry(status="RUNNING")
    mock_db.validationqueueentry.find_unique.return_value = entry

    resp = authed_client.post("/v2/runs/queue/qe-1/demote")
    assert resp.status_code == 409

    data = json.loads(resp.data)
    assert "RUNNING" in data["errors"][0]["message"]


def test_demote_rejects_not_found(authed_client, mock_db):
    """Demoting a nonexistent entry returns 404."""
    mock_db.validationqueueentry.find_unique.return_value = None

    resp = authed_client.post("/v2/runs/queue/nonexistent/demote")
    assert resp.status_code == 404


def test_demote_unauthorized(client):
    """Demoting without auth returns 401."""
    resp = client.post(
        "/v2/runs/queue/qe-1/demote",
        content_type="application/json",
    )
    assert resp.status_code == 401
