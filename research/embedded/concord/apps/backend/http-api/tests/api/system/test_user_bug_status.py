"""Integration tests for user-facing bug status API — my error reports."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def _error_report(
    rid="err-1",
    status="OPEN",
    resolved_in_release_id=None,
    resolved_in_release=None,
):
    return make_obj(
        id=rid,
        status=status,
        type="user_report",
        severity="error",
        message="Something broke",
        context=None,
        currentPath="/dashboard",
        userEmail="test@example.com",
        userId="test-user-id",
        appVersion="0.2.5",
        resolvedById=None,
        resolvedAt=None,
        adminNotes=None,
        resolvedInReleaseId=resolved_in_release_id,
        resolvedInRelease=resolved_in_release,
        createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


# ── list_my_bugs ────────────────────────────────────────────


def test_list_my_bugs(authed_client, mock_db):
    mock_db.errorreport.count.return_value = 2
    mock_db.errorreport.find_many.return_value = [
        _error_report("err-1"),
        _error_report("err-2"),
    ]

    response = authed_client.get("/v2/my/error-reports")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_list_my_bugs_empty(authed_client, mock_db):
    mock_db.errorreport.count.return_value = 0
    mock_db.errorreport.find_many.return_value = []

    response = authed_client.get("/v2/my/error-reports")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 0


# ── my_bugs_shows_release_link ──────────────────────────────


def test_my_bugs_shows_release_link(authed_client, mock_db):
    release_obj = make_obj(id="rel-1", version="0.3.0")
    mock_db.errorreport.count.return_value = 1
    mock_db.errorreport.find_many.return_value = [
        _error_report(
            "err-1",
            status="RESOLVED",
            resolved_in_release_id="rel-1",
            resolved_in_release=release_obj,
        ),
    ]

    response = authed_client.get("/v2/my/error-reports")

    assert response.status_code == 200
    data = json.loads(response.data)
    report = data["data"]["data"][0]
    assert report["resolvedInReleaseId"] == "rel-1"
    assert report["resolvedInVersion"] == "0.3.0"


def test_my_bugs_no_release_link(authed_client, mock_db):
    mock_db.errorreport.count.return_value = 1
    mock_db.errorreport.find_many.return_value = [
        _error_report("err-1", status="OPEN"),
    ]

    response = authed_client.get("/v2/my/error-reports")

    assert response.status_code == 200
    data = json.loads(response.data)
    report = data["data"]["data"][0]
    assert report["resolvedInReleaseId"] is None
    assert report["resolvedInVersion"] is None
