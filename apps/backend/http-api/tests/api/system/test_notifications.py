"""Integration tests for Notifications API — list, mark read, unread count."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def _notification(nid="notif-1", read_at=None):
    return make_obj(
        id=nid,
        type="RELEASE_PUBLISHED",
        title="Release v0.3.0 published",
        message="A new release has been published with bug fixes.",
        userId="test-user-id",
        releaseId="rel-1",
        errorReportId=None,
        readAt=read_at,
        createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


def _err_msg(data: dict) -> str:
    return data["errors"][0]["message"]


# ── list_my_notifications ───────────────────────────────────


def test_list_my_notifications(authed_client, mock_db):
    mock_db.notification.count.return_value = 2
    mock_db.notification.find_many.return_value = [
        _notification("notif-1"),
        _notification("notif-2"),
    ]

    response = authed_client.get("/v2/notifications")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


# ── mark_notification_read ──────────────────────────────────


def test_mark_notification_read(authed_client, mock_db):
    mock_db.notification.find_unique.return_value = _notification()
    read_notif = _notification(read_at=datetime(2026, 4, 2, tzinfo=timezone.utc))
    mock_db.notification.update.return_value = read_notif

    response = authed_client.patch("/v2/notifications/notif-1/read")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["readAt"] is not None


def test_mark_notification_read_not_found(authed_client, mock_db):
    mock_db.notification.find_unique.return_value = None

    response = authed_client.patch("/v2/notifications/nonexistent/read")

    assert response.status_code == 404


def test_mark_notification_read_wrong_user(authed_client, mock_db):
    notif = _notification()
    notif.userId = "other-user-id"
    mock_db.notification.find_unique.return_value = notif

    response = authed_client.patch("/v2/notifications/notif-1/read")

    assert response.status_code == 404


# ── mark_all_read ───────────────────────────────────────────


def test_mark_all_read(authed_client, mock_db):
    mock_db.notification.update_many.return_value = make_obj(count=5)

    response = authed_client.post("/v2/notifications/read-all")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["updated"] == 5


# ── unread_count ────────────────────────────────────────────


def test_notification_unread_count(authed_client, mock_db):
    mock_db.notification.count.return_value = 3

    response = authed_client.get("/v2/notifications/unread-count")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["count"] == 3


# ── broadcast ───────────────────────────────────────────────


def test_broadcast_notification(authed_client, mock_db):
    mock_db.user.find_many.return_value = [
        make_obj(id="user-1", active=True),
        make_obj(id="user-2", active=True),
    ]
    mock_db.notification.create_many.return_value = make_obj(count=2)

    with patch("src.api.v2.system.notifications.log_audit"):
        response = authed_client.post(
            "/v2/notifications/broadcast",
            data=json.dumps({
                "title": "System maintenance",
                "message": "Maintenance window tonight at 10 PM.",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["sent"] == 2


def test_broadcast_notification_missing_title(authed_client, mock_db):
    response = authed_client.post(
        "/v2/notifications/broadcast",
        data=json.dumps({"message": "Some message"}),
    )

    assert response.status_code == 400


def test_broadcast_notification_missing_message(authed_client, mock_db):
    response = authed_client.post(
        "/v2/notifications/broadcast",
        data=json.dumps({"title": "Some title"}),
    )

    assert response.status_code == 400
