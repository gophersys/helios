"""Integration tests for Releases API — CRUD, status transitions, bug linkage."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def _release(
    rid="rel-1",
    version="0.3.0",
    status="DRAFT",
    commit_sha="abc1234",
    branch="main",
):
    return make_obj(
        id=rid,
        version=version,
        status=status,
        commitSha=commit_sha,
        branch=branch,
        previousVersion=None,
        corekinectVersion="0.2.6",
        corectlMinVersion=None,
        protoVersion=None,
        migrationHash=None,
        changelog="## Changes\n- Feature A",
        summary="First release",
        breakingChanges=None,
        testsPassed=42,
        testsFailed=0,
        testCoverage=95.5,
        gateStatus="passed",
        gateOverrideBy=None,
        gateOverrideReason=None,
        stagedAt=None,
        releasedAt=None,
        rolledBackAt=None,
        createdById="user-1",
        createdBy=None,
        resolvedErrorReports=[],
        notifications=[],
        createdAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


def _err_msg(data: dict) -> str:
    return data["errors"][0]["message"]


# ── create_release ──────────────────────────────────────────


def test_create_release(authed_client, mock_db):
    mock_db.release.find_unique.return_value = None
    created = _release()
    mock_db.release.create.return_value = created

    with patch("src.api.v2.system.releases.log_audit"):
        response = authed_client.post(
            "/v2/releases",
            data=json.dumps({
                "version": "0.3.0",
                "commitSha": "abc1234",
                "changelog": "## Changes\n- Feature A",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["version"] == "0.3.0"
    assert data["data"]["status"] == "DRAFT"


def test_create_release_duplicate_version(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release()

    response = authed_client.post(
        "/v2/releases",
        data=json.dumps({
            "version": "0.3.0",
            "commitSha": "abc1234",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert "already exists" in _err_msg(data).lower()


def test_create_release_missing_version(authed_client, mock_db):
    response = authed_client.post(
        "/v2/releases",
        data=json.dumps({"commitSha": "abc1234"}),
    )

    assert response.status_code == 400


def test_create_release_missing_commit_sha(authed_client, mock_db):
    response = authed_client.post(
        "/v2/releases",
        data=json.dumps({"version": "0.3.0"}),
    )

    assert response.status_code == 400


# ── list_releases ───────────────────────────────────────────


def test_list_releases(authed_client, mock_db):
    mock_db.release.count.return_value = 2
    mock_db.release.find_many.return_value = [
        _release("rel-1", "0.3.0"),
        _release("rel-2", "0.2.0", status="RELEASED"),
    ]

    response = authed_client.get("/v2/releases")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_list_releases_status_filter(authed_client, mock_db):
    mock_db.release.count.return_value = 1
    mock_db.release.find_many.return_value = [
        _release("rel-2", "0.2.0", status="RELEASED"),
    ]

    response = authed_client.get("/v2/releases?status=RELEASED")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 1


# ── get_release ─────────────────────────────────────────────


def test_get_release(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release()

    response = authed_client.get("/v2/releases/rel-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["id"] == "rel-1"
    assert data["data"]["version"] == "0.3.0"


def test_get_release_not_found(authed_client, mock_db):
    mock_db.release.find_unique.return_value = None

    response = authed_client.get("/v2/releases/nonexistent")

    assert response.status_code == 404


# ── update_release_status ───────────────────────────────────


def test_update_release_status_draft_to_staged(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release(status="DRAFT")
    mock_db.release.update.return_value = _release(status="STAGED")

    with patch("src.api.v2.system.releases.log_audit"):
        response = authed_client.patch(
            "/v2/releases/rel-1",
            data=json.dumps({"status": "STAGED"}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["status"] == "STAGED"


def test_update_release_status_staged_to_released(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release(status="STAGED")
    mock_db.release.update.return_value = _release(status="RELEASED")

    with patch("src.api.v2.system.releases.log_audit"):
        response = authed_client.patch(
            "/v2/releases/rel-1",
            data=json.dumps({"status": "RELEASED"}),
        )

    assert response.status_code == 200


def test_update_release_invalid_status(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release(status="DRAFT")

    response = authed_client.patch(
        "/v2/releases/rel-1",
        data=json.dumps({"status": "INVALID"}),
    )

    assert response.status_code == 400


def test_update_release_changelog(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release()
    mock_db.release.update.return_value = _release()

    with patch("src.api.v2.system.releases.log_audit"):
        response = authed_client.patch(
            "/v2/releases/rel-1",
            data=json.dumps({"changelog": "## Updated\n- New stuff"}),
        )

    assert response.status_code == 200


def test_update_release_not_found(authed_client, mock_db):
    mock_db.release.find_unique.return_value = None

    response = authed_client.patch(
        "/v2/releases/nonexistent",
        data=json.dumps({"status": "STAGED"}),
    )

    assert response.status_code == 404


# ── delete_release ──────────────────────────────────────────


def test_delete_release_draft(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release(status="DRAFT")

    with patch("src.api.v2.system.releases.log_audit"):
        response = authed_client.delete("/v2/releases/rel-1")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_release_non_draft_blocked(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release(status="RELEASED")

    response = authed_client.delete("/v2/releases/rel-1")

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "draft" in _err_msg(data).lower()


def test_delete_release_not_found(authed_client, mock_db):
    mock_db.release.find_unique.return_value = None

    response = authed_client.delete("/v2/releases/nonexistent")

    assert response.status_code == 404


# ── link_bugs_to_release ────────────────────────────────────


def test_link_bugs_to_release(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release()
    mock_db.errorreport.update_many.return_value = None

    with patch("src.api.v2.system.releases.log_audit"):
        response = authed_client.post(
            "/v2/releases/rel-1/link-bugs",
            data=json.dumps({"errorReportIds": ["err-1", "err-2"]}),
        )

    assert response.status_code == 200
    mock_db.errorreport.update_many.assert_called_once()


def test_link_bugs_to_release_not_found(authed_client, mock_db):
    mock_db.release.find_unique.return_value = None

    response = authed_client.post(
        "/v2/releases/nonexistent/link-bugs",
        data=json.dumps({"errorReportIds": ["err-1"]}),
    )

    assert response.status_code == 404


def test_link_bugs_missing_ids(authed_client, mock_db):
    mock_db.release.find_unique.return_value = _release()

    response = authed_client.post(
        "/v2/releases/rel-1/link-bugs",
        data=json.dumps({}),
    )

    assert response.status_code == 400
