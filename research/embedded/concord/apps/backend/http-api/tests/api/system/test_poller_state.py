"""Integration tests for the Poller State API.

Covers GET /v2/system/poller-state, PUT /v2/system/poller-state,
and DELETE /v2/system/poller-state.
"""

import json
from datetime import datetime, timezone

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    id="pc-1",
    repo_slug="alpha_fw",
    entry_type="branch",
    ref_id="concord-main",
    commit_sha="abc123",
    metadata=None,
):
    return make_obj(
        id=id,
        repoSlug=repo_slug,
        type=entry_type,
        refId=ref_id,
        commitSha=commit_sha,
        metadata=metadata,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# GET /v2/system/poller-state
# ---------------------------------------------------------------------------


class TestListPollerState:
    def test_list_all_entries(self, authed_client, mock_db):
        mock_db.pollcache.find_many.return_value = [
            _make_entry(id="pc-1", entry_type="branch", ref_id="concord-main"),
            _make_entry(id="pc-2", entry_type="pr", ref_id="42"),
        ]

        response = authed_client.get("/v2/system/poller-state")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "pc-1"
        assert data["data"][1]["id"] == "pc-2"

        call_kwargs = mock_db.pollcache.find_many.call_args[1]
        assert call_kwargs["where"] == {}

    def test_list_filtered_by_repo_slug(self, authed_client, mock_db):
        mock_db.pollcache.find_many.return_value = [
            _make_entry(id="pc-1", repo_slug="alpha_fw"),
        ]

        response = authed_client.get("/v2/system/poller-state?repoSlug=alpha_fw")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 1

        call_kwargs = mock_db.pollcache.find_many.call_args[1]
        assert call_kwargs["where"] == {"repoSlug": "alpha_fw"}

    def test_list_empty(self, authed_client, mock_db):
        mock_db.pollcache.find_many.return_value = []

        response = authed_client.get("/v2/system/poller-state")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"] == []

    def test_list_requires_auth(self, client):
        response = client.get("/v2/system/poller-state")
        assert response.status_code == 401

    def test_entry_fields_serialized(self, authed_client, mock_db):
        mock_db.pollcache.find_many.return_value = [
            _make_entry(
                id="pc-3",
                entry_type="pr",
                ref_id="99",
                commit_sha="deadbeef",
                metadata={"source_branch": "feature/x", "title": "My PR"},
            )
        ]

        response = authed_client.get("/v2/system/poller-state")
        data = json.loads(response.data)
        entry = data["data"][0]

        assert entry["id"] == "pc-3"
        assert entry["type"] == "pr"
        assert entry["refId"] == "99"
        assert entry["commitSha"] == "deadbeef"
        assert entry["metadata"]["source_branch"] == "feature/x"


# ---------------------------------------------------------------------------
# PUT /v2/system/poller-state
# ---------------------------------------------------------------------------


class TestUpsertPollerState:
    def test_upsert_branch_entry(self, authed_client, mock_db):
        upserted = _make_entry(
            id="pc-new",
            entry_type="branch",
            ref_id="concord-main",
            commit_sha="newsha123",
        )
        mock_db.pollcache.upsert.return_value = upserted

        response = authed_client.put(
            "/v2/system/poller-state",
            data=json.dumps({
                "repoSlug": "alpha_fw",
                "type": "branch",
                "refId": "concord-main",
                "commitSha": "newsha123",
            }),
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["commitSha"] == "newsha123"
        assert data["data"]["type"] == "branch"

    def test_upsert_pr_entry_with_metadata(self, authed_client, mock_db):
        upserted = _make_entry(
            id="pc-pr",
            entry_type="pr",
            ref_id="42",
            commit_sha="prsha456",
            metadata={"source_branch": "feature/sensor", "title": "Add sensor"},
        )
        mock_db.pollcache.upsert.return_value = upserted

        response = authed_client.put(
            "/v2/system/poller-state",
            data=json.dumps({
                "repoSlug": "alpha_fw",
                "type": "pr",
                "refId": "42",
                "commitSha": "prsha456",
                "metadata": {"source_branch": "feature/sensor", "title": "Add sensor"},
            }),
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["metadata"]["source_branch"] == "feature/sensor"

    def test_upsert_requires_auth(self, client):
        response = client.put(
            "/v2/system/poller-state",
            data=json.dumps({"repoSlug": "x", "type": "branch", "refId": "main", "commitSha": "a"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_upsert_missing_repo_slug(self, authed_client, mock_db):
        response = authed_client.put(
            "/v2/system/poller-state",
            data=json.dumps({"type": "branch", "refId": "main", "commitSha": "abc"}),
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "repoSlug" in data["errors"][0]["message"]

    def test_upsert_invalid_type(self, authed_client, mock_db):
        response = authed_client.put(
            "/v2/system/poller-state",
            data=json.dumps({
                "repoSlug": "alpha_fw",
                "type": "invalid",
                "refId": "main",
                "commitSha": "abc",
            }),
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "type" in data["errors"][0]["message"]

    def test_upsert_missing_ref_id(self, authed_client, mock_db):
        response = authed_client.put(
            "/v2/system/poller-state",
            data=json.dumps({"repoSlug": "alpha_fw", "type": "branch", "commitSha": "abc"}),
        )
        assert response.status_code == 400

    def test_upsert_missing_commit_sha(self, authed_client, mock_db):
        response = authed_client.put(
            "/v2/system/poller-state",
            data=json.dumps({"repoSlug": "alpha_fw", "type": "branch", "refId": "main"}),
        )
        assert response.status_code == 400

    def test_upsert_no_body(self, authed_client, mock_db):
        response = authed_client.put("/v2/system/poller-state")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /v2/system/poller-state
# ---------------------------------------------------------------------------


class TestDeletePollerState:
    def test_delete_existing_entry(self, authed_client, mock_db):
        mock_db.pollcache.find_unique.return_value = _make_entry()
        mock_db.pollcache.delete.return_value = None

        response = authed_client.delete(
            "/v2/system/poller-state?repoSlug=alpha_fw&type=branch&refId=concord-main"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["deleted"] is True

    def test_delete_not_found(self, authed_client, mock_db):
        mock_db.pollcache.find_unique.return_value = None

        response = authed_client.delete(
            "/v2/system/poller-state?repoSlug=alpha_fw&type=branch&refId=missing"
        )

        assert response.status_code == 404

    def test_delete_requires_auth(self, client):
        response = client.delete(
            "/v2/system/poller-state?repoSlug=alpha_fw&type=branch&refId=concord-main"
        )
        assert response.status_code == 401

    def test_delete_missing_repo_slug(self, authed_client, mock_db):
        response = authed_client.delete(
            "/v2/system/poller-state?type=branch&refId=main"
        )
        assert response.status_code == 400

    def test_delete_invalid_type(self, authed_client, mock_db):
        response = authed_client.delete(
            "/v2/system/poller-state?repoSlug=alpha_fw&type=bad&refId=main"
        )
        assert response.status_code == 400

    def test_delete_missing_ref_id(self, authed_client, mock_db):
        response = authed_client.delete(
            "/v2/system/poller-state?repoSlug=alpha_fw&type=branch"
        )
        assert response.status_code == 400

    def test_delete_calls_db_delete(self, authed_client, mock_db):
        mock_db.pollcache.find_unique.return_value = _make_entry(
            ref_id="concord-main", entry_type="branch"
        )

        authed_client.delete(
            "/v2/system/poller-state?repoSlug=alpha_fw&type=branch&refId=concord-main"
        )

        mock_db.pollcache.delete.assert_called_once()
