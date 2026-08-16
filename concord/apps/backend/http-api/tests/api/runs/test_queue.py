"""Tests for /v2/runs/queue endpoints (excluding demote, tested separately)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _queue_entry(**overrides):
    defaults = dict(
        id="qe-001",
        assetSetId="as-001",
        stageConfigId=None,
        stage=4,
        priority=0,
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
#  list_queue
# ---------------------------------------------------------------------------


def test_list_queue_success(authed_client, mock_db):
    e1 = _queue_entry(id="qe-001")
    e2 = _queue_entry(id="qe-002")
    mock_db.validationqueueentry.count.return_value = 2
    mock_db.validationqueueentry.find_many.return_value = [e1, e2]

    resp = authed_client.get("/v2/runs/queue")
    assert resp.status_code == 200

    body = json.loads(resp.data)
    assert len(body["data"]["data"]) == 2
    assert body["data"]["pagination"]["total"] == 2
    assert body["data"]["pagination"]["page"] == 1


def test_list_queue_with_status_filter(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 1
    mock_db.validationqueueentry.find_many.return_value = [_queue_entry()]

    resp = authed_client.get("/v2/runs/queue?status=QUEUED")
    assert resp.status_code == 200

    count_call = mock_db.validationqueueentry.count.call_args
    assert count_call.kwargs["where"]["status"] == "QUEUED"


def test_list_queue_empty(authed_client, mock_db):
    mock_db.validationqueueentry.count.return_value = 0
    mock_db.validationqueueentry.find_many.return_value = []

    resp = authed_client.get("/v2/runs/queue")
    assert resp.status_code == 200

    body = json.loads(resp.data)
    assert body["data"]["data"] == []
    assert body["data"]["pagination"]["total"] == 0


def test_list_queue_unauthorized(client):
    resp = client.get("/v2/runs/queue", content_type="application/json")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
#  get_queue_entry
# ---------------------------------------------------------------------------


def test_get_queue_entry_success(authed_client, mock_db):
    entry = _queue_entry()
    mock_db.validationqueueentry.find_unique.return_value = entry

    resp = authed_client.get("/v2/runs/queue/qe-001")
    assert resp.status_code == 200

    body = json.loads(resp.data)
    assert body["data"]["id"] == "qe-001"
    assert body["data"]["status"] == "QUEUED"


def test_get_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    resp = authed_client.get("/v2/runs/queue/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  create_queue_entry
# ---------------------------------------------------------------------------


def test_create_queue_entry_success(authed_client, mock_db):
    mock_db.assetset.find_unique.return_value = make_obj(id="as-001")
    mock_db.validationqueueentry.find_first.return_value = None
    created = _queue_entry(priority=3, reason="manual test")
    mock_db.validationqueueentry.create.return_value = created

    with patch("api.v2.runs.queue.log_audit"):
        resp = authed_client.post(
            "/v2/runs/queue",
            data=json.dumps({"assetSetId": "as-001", "priority": 3, "reason": "manual test"}),
        )

    assert resp.status_code == 201
    body = json.loads(resp.data)
    assert body["data"]["assetSetId"] == "as-001"


def test_create_queue_entry_no_body(authed_client, mock_db):
    resp = authed_client.post("/v2/runs/queue", data=None, content_type=None)
    assert resp.status_code == 400


def test_create_queue_entry_missing_asset_set_id(authed_client, mock_db):
    resp = authed_client.post(
        "/v2/runs/queue",
        data=json.dumps({"priority": 1}),
    )
    assert resp.status_code == 400

    body = json.loads(resp.data)
    assert "assetSetId" in body["errors"][0]["message"]


def test_create_queue_entry_asset_set_not_found(authed_client, mock_db):
    mock_db.assetset.find_unique.return_value = None

    resp = authed_client.post(
        "/v2/runs/queue",
        data=json.dumps({"assetSetId": "as-missing"}),
    )
    assert resp.status_code == 404


def test_create_queue_entry_already_queued(authed_client, mock_db):
    mock_db.assetset.find_unique.return_value = make_obj(id="as-001")
    mock_db.validationqueueentry.find_first.return_value = _queue_entry()

    resp = authed_client.post(
        "/v2/runs/queue",
        data=json.dumps({"assetSetId": "as-001"}),
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
#  update_queue_entry
# ---------------------------------------------------------------------------


def test_update_queue_entry_success(authed_client, mock_db):
    entry = _queue_entry()
    updated = _queue_entry(priority=10)
    mock_db.validationqueueentry.find_unique.return_value = entry
    mock_db.validationqueueentry.update.return_value = updated

    with patch("api.v2.runs.queue.log_audit"):
        resp = authed_client.patch(
            "/v2/runs/queue/qe-001",
            data=json.dumps({"priority": 10}),
        )

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["priority"] == 10


def test_update_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    resp = authed_client.patch(
        "/v2/runs/queue/qe-001",
        data=json.dumps({"priority": 5}),
    )
    assert resp.status_code == 404


def test_update_queue_entry_not_queued(authed_client, mock_db):
    entry = _queue_entry(status="RUNNING")
    mock_db.validationqueueentry.find_unique.return_value = entry

    resp = authed_client.patch(
        "/v2/runs/queue/qe-001",
        data=json.dumps({"priority": 5}),
    )
    assert resp.status_code == 409

    body = json.loads(resp.data)
    assert "RUNNING" in body["errors"][0]["message"]


def test_update_queue_entry_no_fields(authed_client, mock_db):
    entry = _queue_entry()
    mock_db.validationqueueentry.find_unique.return_value = entry

    resp = authed_client.patch(
        "/v2/runs/queue/qe-001",
        data=json.dumps({}),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  cancel_queue_entry
# ---------------------------------------------------------------------------


def test_cancel_queue_entry_success(authed_client, mock_db):
    entry = _queue_entry()
    cancelled = _queue_entry(status="CANCELLED", completedAt=NOW)
    mock_db.validationqueueentry.find_unique.return_value = entry
    mock_db.validationqueueentry.update.return_value = cancelled

    with patch("api.v2.runs.queue.log_audit"):
        resp = authed_client.post("/v2/runs/queue/qe-001/cancel")

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["status"] == "CANCELLED"


def test_cancel_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    resp = authed_client.post("/v2/runs/queue/nonexistent/cancel")
    assert resp.status_code == 404


def test_cancel_queue_entry_not_queued(authed_client, mock_db):
    entry = _queue_entry(status="RUNNING")
    mock_db.validationqueueentry.find_unique.return_value = entry

    resp = authed_client.post("/v2/runs/queue/qe-001/cancel")
    assert resp.status_code == 409

    body = json.loads(resp.data)
    assert "RUNNING" in body["errors"][0]["message"]


# ---------------------------------------------------------------------------
#  promote_queue_entry
# ---------------------------------------------------------------------------


def test_promote_queue_entry_success(authed_client, mock_db):
    entry = _queue_entry(priority=3)
    top = _queue_entry(id="qe-top", priority=5)
    promoted = _queue_entry(priority=6)

    mock_db.validationqueueentry.find_unique.return_value = entry
    mock_db.validationqueueentry.find_first.return_value = top
    mock_db.validationqueueentry.update.return_value = promoted

    with patch("api.v2.runs.queue.log_audit"):
        resp = authed_client.post("/v2/runs/queue/qe-001/promote")

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["priority"] == 6

    call_kwargs = mock_db.validationqueueentry.update.call_args
    assert call_kwargs.kwargs["data"]["priority"] == 6


def test_promote_queue_entry_not_found(authed_client, mock_db):
    mock_db.validationqueueentry.find_unique.return_value = None

    resp = authed_client.post("/v2/runs/queue/nonexistent/promote")
    assert resp.status_code == 404


def test_promote_queue_entry_not_queued(authed_client, mock_db):
    entry = _queue_entry(status="COMPLETED")
    mock_db.validationqueueentry.find_unique.return_value = entry

    resp = authed_client.post("/v2/runs/queue/qe-001/promote")
    assert resp.status_code == 409

    body = json.loads(resp.data)
    assert "COMPLETED" in body["errors"][0]["message"]


# ---------------------------------------------------------------------------
#  get_queue_stats
# ---------------------------------------------------------------------------


def test_get_queue_stats_success(authed_client, mock_db):
    mock_db.validationqueueentry.count.side_effect = [3, 1, 10, 2, 4]

    resp = authed_client.get("/v2/runs/queue/stats")
    assert resp.status_code == 200

    body = json.loads(resp.data)
    stats = body["data"]
    assert stats["queued"] == 3
    assert stats["running"] == 1
    assert stats["completed"] == 10
    assert stats["failed"] == 2
    assert stats["cancelled"] == 4
    assert stats["total"] == 20


# ---------------------------------------------------------------------------
#  trigger_scheduler
# ---------------------------------------------------------------------------


def test_trigger_scheduler_no_pending(authed_client, mock_db):
    with patch("api.v2.runs.queue.process_queue", return_value={"processed": False, "reason": "No pending entries"}):
        with patch("api.v2.runs.queue.log_audit"):
            resp = authed_client.post("/v2/runs/queue/schedule")

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["processed"] is False
    assert body["data"]["reason"] == "No pending entries"


def test_trigger_scheduler_error(authed_client, mock_db):
    with patch("api.v2.runs.queue.process_queue", side_effect=RuntimeError("boom")):
        resp = authed_client.post("/v2/runs/queue/schedule")

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["processed"] is False
    assert "boom" in body["data"]["reason"]


# ---------------------------------------------------------------------------
#  batch_queue_action
# ---------------------------------------------------------------------------


def test_batch_cancel_success(authed_client, mock_db):
    e1 = _queue_entry(id="qe-001")
    e2 = _queue_entry(id="qe-002")
    mock_db.validationqueueentry.find_unique.side_effect = [e1, e2]

    with patch("api.v2.runs.queue.log_audit"):
        resp = authed_client.post(
            "/v2/runs/queue/batch",
            data=json.dumps({"action": "cancel", "ids": ["qe-001", "qe-002"]}),
        )

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["succeeded"] == ["qe-001", "qe-002"]
    assert body["data"]["failed"] == []


def test_batch_cancel_invalid_action(authed_client, mock_db):
    resp = authed_client.post(
        "/v2/runs/queue/batch",
        data=json.dumps({"action": "delete", "ids": ["qe-001"]}),
    )
    assert resp.status_code == 400


def test_batch_cancel_empty_ids(authed_client, mock_db):
    resp = authed_client.post(
        "/v2/runs/queue/batch",
        data=json.dumps({"action": "cancel", "ids": []}),
    )
    assert resp.status_code == 400


def test_batch_cancel_mixed(authed_client, mock_db):
    queued = _queue_entry(id="qe-001", status="QUEUED")
    running = _queue_entry(id="qe-002", status="RUNNING")
    mock_db.validationqueueentry.find_unique.side_effect = [queued, running]

    with patch("api.v2.runs.queue.log_audit"):
        resp = authed_client.post(
            "/v2/runs/queue/batch",
            data=json.dumps({"action": "cancel", "ids": ["qe-001", "qe-002"]}),
        )

    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["data"]["succeeded"] == ["qe-001"]
    assert len(body["data"]["failed"]) == 1
    assert body["data"]["failed"][0]["id"] == "qe-002"
    assert "RUNNING" in body["data"]["failed"][0]["reason"]
