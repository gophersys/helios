"""Tests for build queue priority management endpoints."""

import json

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _build_obj(**overrides):
    """Return a mock BuildJob with sensible defaults."""
    defaults = {
        "id": "build-001",
        "status": "QUEUED",
        "priority": 50,
        "product": "alpha_fw",
        "board": "alpha_b0",
        "target": "app",
        "variant": "debug",
        "branch": "main",
        "commitSha": "abc1234",
    }
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
#  PATCH /v2/builds/<build_id>/priority — Set priority
# ---------------------------------------------------------------------------

class TestSetBuildPriority:
    """Tests for PATCH /v2/builds/<build_id>/priority."""

    def test_set_priority_success(self, authed_client, mock_db):
        """Set priority on a QUEUED build returns 200."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjob.update.return_value = _build_obj(priority=100)

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["id"] == "build-001"
        assert body["data"]["priority"] == 100

        # Verify DB update was called
        mock_db.buildjob.update.assert_called_once()
        call_kwargs = mock_db.buildjob.update.call_args.kwargs
        assert call_kwargs["data"]["priority"] == 100

    def test_set_priority_blocked_build(self, authed_client, mock_db):
        """Set priority on a BLOCKED build also succeeds."""
        mock_db.buildjob.find_unique.return_value = _build_obj(status="BLOCKED")
        mock_db.buildjob.update.return_value = _build_obj(status="BLOCKED", priority=200)

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": 200}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_set_priority_missing_field(self, authed_client, mock_db):
        """Missing priority field returns 400."""
        mock_db.buildjob.find_unique.return_value = _build_obj()

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

        body = json.loads(resp.data)
        assert "priority is required" in body["errors"][0]["message"]

    def test_set_priority_negative(self, authed_client, mock_db):
        """Negative priority returns 400."""
        mock_db.buildjob.find_unique.return_value = _build_obj()

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": -1}),
            content_type="application/json",
        )
        assert resp.status_code == 400

        body = json.loads(resp.data)
        assert "between 0 and 1000" in body["errors"][0]["message"]

    def test_set_priority_over_max(self, authed_client, mock_db):
        """Priority above 1000 returns 400."""
        mock_db.buildjob.find_unique.return_value = _build_obj()

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": 1001}),
            content_type="application/json",
        )
        assert resp.status_code == 400

        body = json.loads(resp.data)
        assert "between 0 and 1000" in body["errors"][0]["message"]

    def test_set_priority_non_queued_build(self, authed_client, mock_db):
        """Setting priority on a BUILDING build returns 409."""
        mock_db.buildjob.find_unique.return_value = _build_obj(status="BUILDING")

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 409

        body = json.loads(resp.data)
        assert "BUILDING" in body["errors"][0]["message"]

    def test_set_priority_nonexistent_build(self, authed_client, mock_db):
        """Setting priority on a missing build returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        resp = authed_client.patch(
            "/v2/builds/no-such-id/priority",
            data=json.dumps({"priority": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_set_priority_non_integer(self, authed_client, mock_db):
        """Non-integer priority returns 400."""
        mock_db.buildjob.find_unique.return_value = _build_obj()

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": "high"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

        body = json.loads(resp.data)
        assert "must be an integer" in body["errors"][0]["message"]

    def test_set_priority_boundary_zero(self, authed_client, mock_db):
        """Priority of 0 is valid."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjob.update.return_value = _build_obj(priority=0)

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": 0}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_set_priority_boundary_thousand(self, authed_client, mock_db):
        """Priority of 1000 is valid."""
        mock_db.buildjob.find_unique.return_value = _build_obj()
        mock_db.buildjob.update.return_value = _build_obj(priority=1000)

        resp = authed_client.patch(
            "/v2/builds/build-001/priority",
            data=json.dumps({"priority": 1000}),
            content_type="application/json",
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
#  POST /v2/builds/<build_id>/promote — Promote to top of queue
# ---------------------------------------------------------------------------

class TestPromoteBuild:
    """Tests for POST /v2/builds/<build_id>/promote."""

    def test_promote_success(self, authed_client, mock_db):
        """Promote sets priority to max+1 among queued jobs."""
        mock_db.buildjob.find_unique.return_value = _build_obj(priority=50)
        mock_db.buildjob.find_many.return_value = [_build_obj(id="other", priority=80)]
        mock_db.buildjob.update.return_value = _build_obj(priority=81)

        resp = authed_client.post("/v2/builds/build-001/promote")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["priority"] == 81

        # Verify the update was called with max+1
        call_kwargs = mock_db.buildjob.update.call_args.kwargs
        assert call_kwargs["data"]["priority"] == 81

    def test_promote_no_other_queued_jobs(self, authed_client, mock_db):
        """Promote with no other queued jobs uses default 50+1."""
        mock_db.buildjob.find_unique.return_value = _build_obj(priority=50)
        mock_db.buildjob.find_many.return_value = []
        mock_db.buildjob.update.return_value = _build_obj(priority=51)

        resp = authed_client.post("/v2/builds/build-001/promote")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["priority"] == 51

    def test_promote_non_queued_build(self, authed_client, mock_db):
        """Promoting a SUCCESS build returns 409."""
        mock_db.buildjob.find_unique.return_value = _build_obj(status="SUCCESS")

        resp = authed_client.post("/v2/builds/build-001/promote")
        assert resp.status_code == 409

        body = json.loads(resp.data)
        assert "SUCCESS" in body["errors"][0]["message"]

    def test_promote_nonexistent_build(self, authed_client, mock_db):
        """Promoting a missing build returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        resp = authed_client.post("/v2/builds/no-such-id/promote")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  POST /v2/builds/<build_id>/demote — Demote to bottom of queue
# ---------------------------------------------------------------------------

class TestDemoteBuild:
    """Tests for POST /v2/builds/<build_id>/demote."""

    def test_demote_success(self, authed_client, mock_db):
        """Demote sets priority to min-1 among queued jobs."""
        mock_db.buildjob.find_unique.return_value = _build_obj(priority=50)
        mock_db.buildjob.find_many.return_value = [_build_obj(id="other", priority=20)]
        mock_db.buildjob.update.return_value = _build_obj(priority=19)

        resp = authed_client.post("/v2/builds/build-001/demote")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["priority"] == 19

        call_kwargs = mock_db.buildjob.update.call_args.kwargs
        assert call_kwargs["data"]["priority"] == 19

    def test_demote_floor_at_zero(self, authed_client, mock_db):
        """Demote floors priority at 0 when min is already 0."""
        mock_db.buildjob.find_unique.return_value = _build_obj(priority=5)
        mock_db.buildjob.find_many.return_value = [_build_obj(id="other", priority=0)]
        mock_db.buildjob.update.return_value = _build_obj(priority=0)

        resp = authed_client.post("/v2/builds/build-001/demote")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["priority"] == 0

        call_kwargs = mock_db.buildjob.update.call_args.kwargs
        assert call_kwargs["data"]["priority"] == 0

    def test_demote_no_other_queued_jobs(self, authed_client, mock_db):
        """Demote with no other queued jobs uses default 50-1=49."""
        mock_db.buildjob.find_unique.return_value = _build_obj(priority=50)
        mock_db.buildjob.find_many.return_value = []
        mock_db.buildjob.update.return_value = _build_obj(priority=49)

        resp = authed_client.post("/v2/builds/build-001/demote")
        assert resp.status_code == 200

        body = json.loads(resp.data)
        assert body["data"]["priority"] == 49

    def test_demote_non_queued_build(self, authed_client, mock_db):
        """Demoting a FAILED build returns 409."""
        mock_db.buildjob.find_unique.return_value = _build_obj(status="FAILED")

        resp = authed_client.post("/v2/builds/build-001/demote")
        assert resp.status_code == 409

        body = json.loads(resp.data)
        assert "FAILED" in body["errors"][0]["message"]

    def test_demote_nonexistent_build(self, authed_client, mock_db):
        """Demoting a missing build returns 404."""
        mock_db.buildjob.find_unique.return_value = None

        resp = authed_client.post("/v2/builds/no-such-id/demote")
        assert resp.status_code == 404
