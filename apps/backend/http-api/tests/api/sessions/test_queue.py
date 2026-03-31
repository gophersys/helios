"""Tests for the Validation Queue API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline(**overrides):
    defaults = dict(
        id="pipe-1",
        name="Alpha CI #42",
        product="alpha",
        branch="main",
        status="READY",
        builds=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_queue_entry(**overrides):
    defaults = dict(
        id="entry-1",
        buildRunId="pipe-1",
        stageConfigId=None,
        stage=4,
        priority=0,
        status="QUEUED",
        fixtureId=None,
        sessionId=None,
        reason="All fixtures locked",
        errorMessage=None,
        jobName=None,
        requestedAt=NOW,
        assignedAt=None,
        startedAt=None,
        completedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
        buildRun=None,
        fixture=None,
        session=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# list_queue — GET /v2/sessions/queue
# ---------------------------------------------------------------------------

def test_list_queue_success(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 1
    mock_db.validationqueueentry.find_many.return_value = [_make_queue_entry()]

    response = authed_client.get("/v2/sessions/queue")

    assert response.status_code == 200
    data = json.loads(response.data)
    entries = data["data"]["data"]
    assert len(entries) == 1
    assert entries[0]["id"] == "entry-1"
    assert entries[0]["status"] == "QUEUED"
    assert entries[0]["priority"] == 0
    assert data["data"]["pagination"]["total"] == 1


def test_list_queue_empty(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 0
    mock_db.validationqueueentry.find_many.return_value = []

    response = authed_client.get("/v2/sessions/queue")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["data"] == []


def test_list_queue_status_filter(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 0
    mock_db.validationqueueentry.find_many.return_value = []

    response = authed_client.get("/v2/sessions/queue?status=running")

    assert response.status_code == 200
    count_kwargs = mock_db.validationqueueentry.count.call_args[1]
    assert count_kwargs["where"]["status"] == "RUNNING"


def test_list_queue_pagination(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 55
    mock_db.validationqueueentry.find_many.return_value = []

    response = authed_client.get("/v2/sessions/queue?page=2&limit=10")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["pagination"]["page"] == 2
    assert data["data"]["pagination"]["limit"] == 10
    assert data["data"]["pagination"]["pages"] == 6


def test_list_queue_requires_auth(client):
    response = client.get("/v2/sessions/queue")
    assert response.status_code == 401


def test_list_queue_entry_with_build_run(authed_client, mock_db):
    """Queue entry with nested buildRun should serialize it."""
    entry = _make_queue_entry(buildRun=_make_pipeline())
    mock_db.validationqueueentry.count.return_value = 1
    mock_db.validationqueueentry.find_many.return_value = [entry]

    response = authed_client.get("/v2/sessions/queue")

    assert response.status_code == 200
    data = json.loads(response.data)
    entry_data = data["data"]["data"][0]
    assert entry_data["buildRun"]["id"] == "pipe-1"
    assert entry_data["buildRun"]["branch"] == "main"


# ---------------------------------------------------------------------------
# get_queue_entry — GET /v2/sessions/queue/<id>
# ---------------------------------------------------------------------------

def test_get_queue_entry_success(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = _make_queue_entry()

    response = authed_client.get("/v2/sessions/queue/entry-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["id"] == "entry-1"
    assert data["data"]["buildRunId"] == "pipe-1"


def test_get_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    response = authed_client.get("/v2/sessions/queue/bad-id")

    assert response.status_code == 404


def test_get_queue_entry_requires_auth(client):
    response = client.get("/v2/sessions/queue/entry-1")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# create_queue_entry — POST /v2/sessions/queue
# ---------------------------------------------------------------------------

def test_create_queue_entry_success(authed_client, mock_db):
    mock_db.buildrun.find_unique.return_value = _make_pipeline()
    mock_db.validationqueueentry.find_first.return_value = None  # no existing entry
    created = _make_queue_entry(
        stage=4,
        priority=5,
        reason="Manual enqueue",
        buildRun=_make_pipeline(),
    )
    mock_db.validationqueueentry.create.return_value = created

    with patch("api.v2.sessions.queue.log_audit") as mock_audit:
        response = authed_client.post(
            "/v2/sessions/queue",
            data=json.dumps({
                "buildRunId": "pipe-1",
                "stage": 4,
                "priority": 5,
                "reason": "Manual enqueue",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "entry-1"
    assert data["data"]["status"] == "QUEUED"
    mock_audit.assert_called_once()


def test_create_queue_entry_missing_pipeline_id(authed_client, mock_db):
    response = authed_client.post(
        "/v2/sessions/queue",
        data=json.dumps({"stage": 4}),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "buildRunId" in data["errors"][0]["message"]


def test_create_queue_entry_pipeline_not_found(authed_client, mock_db):
    mock_db.buildrun.find_unique.return_value = None

    response = authed_client.post(
        "/v2/sessions/queue",
        data=json.dumps({"buildRunId": "bad-pipe"}),
    )

    assert response.status_code == 404


def test_create_queue_entry_duplicate(authed_client, mock_db):
    """Cannot enqueue pipeline that already has a QUEUED entry."""
    mock_db.buildrun.find_unique.return_value = _make_pipeline()
    mock_db.validationqueueentry.find_first.return_value = _make_queue_entry()

    response = authed_client.post(
        "/v2/sessions/queue",
        data=json.dumps({"buildRunId": "pipe-1"}),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "pending queue entry" in data["errors"][0]["message"]


def test_create_queue_entry_no_body(authed_client, mock_db):
    response = authed_client.post("/v2/sessions/queue", data="")

    assert response.status_code == 400


def test_create_queue_entry_requires_auth(client):
    response = client.post(
        "/v2/sessions/queue",
        data=json.dumps({"buildRunId": "pipe-1"}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# update_queue_entry — PATCH /v2/sessions/queue/<id>
# ---------------------------------------------------------------------------

def test_update_queue_entry_priority(authed_client, mock_db):
    original = _make_queue_entry()
    updated = _make_queue_entry(priority=10)
    mock_db.validationqueueentry.find_unique.return_value = original
    mock_db.validationqueueentry.update.return_value = updated

    with patch("api.v2.sessions.queue.log_audit"):
        response = authed_client._client.patch(
            "/v2/sessions/queue/entry-1",
            data=json.dumps({"priority": 10}),
            headers=dict(authed_client._headers),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["priority"] == 10


def test_update_queue_entry_reason(authed_client, mock_db):
    original = _make_queue_entry()
    updated = _make_queue_entry(reason="Updated reason")
    mock_db.validationqueueentry.find_unique.return_value = original
    mock_db.validationqueueentry.update.return_value = updated

    with patch("api.v2.sessions.queue.log_audit"):
        response = authed_client._client.patch(
            "/v2/sessions/queue/entry-1",
            data=json.dumps({"reason": "Updated reason"}),
            headers=dict(authed_client._headers),
        )

    assert response.status_code == 200


def test_update_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    response = authed_client._client.patch(
        "/v2/sessions/queue/bad-id",
        data=json.dumps({"priority": 5}),
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 404


def test_update_queue_entry_not_queued(authed_client, mock_db):
    """Cannot update a RUNNING or COMPLETED entry."""
    mock_db.validationqueueentry.find_unique.return_value = _make_queue_entry(status="RUNNING")

    response = authed_client._client.patch(
        "/v2/sessions/queue/entry-1",
        data=json.dumps({"priority": 5}),
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "RUNNING" in data["errors"][0]["message"]


def test_update_queue_entry_no_fields(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = _make_queue_entry()

    response = authed_client._client.patch(
        "/v2/sessions/queue/entry-1",
        data=json.dumps({}),
        headers=dict(authed_client._headers),
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "No fields" in data["errors"][0]["message"]


def test_update_queue_entry_requires_auth(client):
    response = client.patch(
        "/v2/sessions/queue/entry-1",
        data=json.dumps({"priority": 5}),
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# cancel_queue_entry — POST /v2/sessions/queue/<id>/cancel
# ---------------------------------------------------------------------------

def test_cancel_queue_entry_success(authed_client, mock_db):
    original = _make_queue_entry()
    cancelled = _make_queue_entry(status="CANCELLED", completedAt=NOW)
    mock_db.validationqueueentry.find_unique.return_value = original
    mock_db.validationqueueentry.update.return_value = cancelled

    with patch("api.v2.sessions.queue.log_audit") as mock_audit:
        response = authed_client.post("/v2/sessions/queue/entry-1/cancel")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "CANCELLED"
    mock_audit.assert_called_once()


def test_cancel_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    response = authed_client.post("/v2/sessions/queue/bad-id/cancel")

    assert response.status_code == 404


def test_cancel_queue_entry_not_cancellable(authed_client, mock_db):
    """Cannot cancel a COMPLETED or RUNNING entry."""
    mock_db.validationqueueentry.find_unique.return_value = _make_queue_entry(status="COMPLETED")

    response = authed_client.post("/v2/sessions/queue/entry-1/cancel")

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "COMPLETED" in data["errors"][0]["message"]


def test_cancel_queue_entry_requires_auth(client):
    response = client.post("/v2/sessions/queue/entry-1/cancel")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# promote_queue_entry — POST /v2/sessions/queue/<id>/promote
# ---------------------------------------------------------------------------

def test_promote_queue_entry_success(authed_client, mock_db):
    original = _make_queue_entry(priority=0)
    top_entry = _make_queue_entry(priority=5)
    promoted = _make_queue_entry(priority=6)

    mock_db.validationqueueentry.find_unique.return_value = original
    mock_db.validationqueueentry.find_first.return_value = top_entry
    mock_db.validationqueueentry.update.return_value = promoted

    with patch("api.v2.sessions.queue.log_audit") as mock_audit:
        response = authed_client.post("/v2/sessions/queue/entry-1/promote")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["priority"] == 6

    # Verify update called with priority = 6 (top + 1)
    update_call = mock_db.validationqueueentry.update.call_args[1]
    assert update_call["data"]["priority"] == 6
    mock_audit.assert_called_once()


def test_promote_queue_entry_when_queue_empty(authed_client, mock_db):
    """Promote when no other entries: priority should become 1."""
    original = _make_queue_entry(priority=0)
    promoted = _make_queue_entry(priority=1)

    mock_db.validationqueueentry.find_unique.return_value = original
    mock_db.validationqueueentry.find_first.return_value = None  # empty queue
    mock_db.validationqueueentry.update.return_value = promoted

    with patch("api.v2.sessions.queue.log_audit"):
        response = authed_client.post("/v2/sessions/queue/entry-1/promote")

    assert response.status_code == 200
    update_call = mock_db.validationqueueentry.update.call_args[1]
    assert update_call["data"]["priority"] == 1


def test_promote_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    response = authed_client.post("/v2/sessions/queue/bad-id/promote")

    assert response.status_code == 404


def test_promote_queue_entry_not_queued(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = _make_queue_entry(status="RUNNING")

    response = authed_client.post("/v2/sessions/queue/entry-1/promote")

    assert response.status_code == 409


def test_promote_queue_entry_requires_auth(client):
    response = client.post("/v2/sessions/queue/entry-1/promote")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# get_queue_stats — GET /v2/sessions/queue/stats
# ---------------------------------------------------------------------------

def test_get_queue_stats_success(authed_client, mock_db):
    mock_db.validationqueueentry.count.side_effect = [3, 1, 10, 2, 5]

    response = authed_client.get("/v2/sessions/queue/stats")

    assert response.status_code == 200
    data = json.loads(response.data)
    stats = data["data"]
    assert stats["queued"] == 3
    assert stats["running"] == 1
    assert stats["completed"] == 10
    assert stats["failed"] == 2
    assert stats["cancelled"] == 5
    assert stats["total"] == 21


def test_get_queue_stats_all_zero(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 0

    response = authed_client.get("/v2/sessions/queue/stats")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["total"] == 0


def test_get_queue_stats_requires_auth(client):
    response = client.get("/v2/sessions/queue/stats")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# trigger_scheduler — POST /v2/sessions/queue/schedule
# ---------------------------------------------------------------------------

def test_trigger_scheduler_success(authed_client, mock_db):
    with patch("api.v2.sessions.queue.process_queue") as mock_process, \
         patch("api.v2.sessions.queue.log_audit"):
        mock_process.return_value = {
            "processed": True,
            "entryId": "entry-1",
            "sessionId": "sess-1",
            "buildRunId": "pipe-1",
        }

        response = authed_client.post("/v2/sessions/queue/schedule")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["processed"] is True
    assert data["data"]["sessionId"] == "sess-1"


def test_trigger_scheduler_no_entries(authed_client, mock_db):
    with patch("api.v2.sessions.queue.process_queue") as mock_process, \
         patch("api.v2.sessions.queue.log_audit"):
        mock_process.return_value = {"processed": False, "reason": "No pending entries"}

        response = authed_client.post("/v2/sessions/queue/schedule")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["processed"] is False
    assert "No pending entries" in data["data"]["reason"]


def test_trigger_scheduler_error_graceful(authed_client, mock_db):
    """Scheduler errors return 200 with processed=False (not 500)."""
    with patch("api.v2.sessions.queue.process_queue") as mock_process:
        mock_process.side_effect = RuntimeError("DB connection lost")

        response = authed_client.post("/v2/sessions/queue/schedule")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["processed"] is False
    assert "Scheduler error" in data["data"]["reason"]


def test_trigger_scheduler_requires_auth(client):
    response = client.post("/v2/sessions/queue/schedule")
    assert response.status_code == 401
