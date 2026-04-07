"""Integration tests for Validation Runs — list_runs, get_run, cancel_run, rerun_session."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import make_obj

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_product(id="prod-1", name="Alpha", slug="alpha"):
    return make_obj(id=id, name=name, slug=slug)


def _make_session(**overrides):
    defaults = dict(
        id="sess-1",
        name="Alpha Stage-5",
        type="VALIDATION",
        productId="prod-1",
        fixtureId=None,
        buildRunId=None,
        status="ACTIVE",
        config={"nodeId": "node-1"},
        targetCount=2,
        completedCount=1,
        passedCount=1,
        failedCount=0,
        durationMs=None,
        errorMessage=None,
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


class TestListRuns:
    """Tests for GET /v2/sessions (list_runs)."""

    def test_list_runs_returns_paginated(self, authed_client, mock_db):
        """list_runs returns a paginated list of sessions."""
        mock_db.session.count.return_value = 1
        mock_db.session.find_many.return_value = [_make_session()]

        response = authed_client.get("/v2/sessions")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "data" in data["data"]
        assert "pagination" in data["data"]
        assert len(data["data"]["data"]) == 1
        assert data["data"]["pagination"]["total"] == 1

    def test_list_runs_filter_by_status(self, authed_client, mock_db):
        """list_runs passes status filter to the DB query."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        response = authed_client.get("/v2/sessions?status=active")

        assert response.status_code == 200
        call_kwargs = mock_db.session.find_many.call_args
        where = call_kwargs[1].get("where", {})
        assert where.get("status") == "ACTIVE"

    def test_list_runs_filter_by_product(self, authed_client, mock_db):
        """list_runs filters sessions by productId when provided."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        response = authed_client.get("/v2/sessions?productId=prod-99")

        assert response.status_code == 200
        call_kwargs = mock_db.session.find_many.call_args
        where = call_kwargs[1].get("where", {})
        assert where.get("productId") == "prod-99"

    def test_list_runs_filter_by_type(self, authed_client, mock_db):
        """list_runs filters sessions by type (VALIDATION, MANUFACTURING)."""
        mock_db.session.count.return_value = 0
        mock_db.session.find_many.return_value = []

        response = authed_client.get("/v2/sessions?type=manufacturing")

        assert response.status_code == 200
        call_kwargs = mock_db.session.find_many.call_args
        where = call_kwargs[1].get("where", {})
        assert where.get("type") == "MANUFACTURING"

    def test_list_runs_unauthorized(self, client):
        """list_runs returns 401 without auth token."""
        response = client.get("/v2/sessions")
        assert response.status_code == 401


class TestGetRun:
    """Tests for GET /v2/sessions/<id> (get_run)."""

    def test_get_run_returns_session(self, authed_client, mock_db):
        """get_run returns session detail with executions."""
        session = _make_session()
        mock_db.session.find_unique.return_value = session

        response = authed_client.get("/v2/sessions/sess-1")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["id"] == "sess-1"
        assert data["data"]["status"] == "ACTIVE"

    def test_get_run_not_found(self, authed_client, mock_db):
        """get_run returns 404 when session does not exist."""
        mock_db.session.find_unique.return_value = None

        response = authed_client.get("/v2/sessions/bad-id")

        assert response.status_code == 404


class TestCancelRun:
    """Tests for POST /v2/sessions/<id>/cancel (cancel_run)."""

    def test_cancel_active_run(self, authed_client, mock_db):
        """cancel_run cancels an ACTIVE session and its queued executions."""
        session = _make_session(status="ACTIVE", config={})
        cancelled = _make_session(status="CANCELLED", finishedAt=NOW)
        mock_db.session.find_unique.return_value = session
        mock_db.testexecution.update_many.return_value = None
        mock_db.validationqueueentry.find_first.return_value = None
        mock_db.session.update.return_value = cancelled

        with patch("api.v2.sessions.runs.log_audit"), \
             patch("api.v2.sessions.reporter._emit_validation_event"), \
             patch("api.v2.sessions.queue.process_queue"), \
             patch("api.v2.sessions.runs.get_storage_client", return_value=MagicMock()), \
             patch("api.v2.sessions.runs.get_bucket_name", return_value="bucket"):
            response = authed_client.post("/v2/sessions/sess-1/cancel")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["status"] == "CANCELLED"

    def test_cancel_already_completed_returns_409(self, authed_client, mock_db):
        """cancel_run returns 409 when session is already COMPLETED."""
        mock_db.session.find_unique.return_value = _make_session(status="COMPLETED")

        response = authed_client.post("/v2/sessions/sess-1/cancel")

        assert response.status_code == 409

    def test_cancel_not_found_returns_404(self, authed_client, mock_db):
        """cancel_run returns 404 for unknown session."""
        mock_db.session.find_unique.return_value = None

        response = authed_client.post("/v2/sessions/bad-id/cancel")

        assert response.status_code == 404

    def test_cancel_unlocks_fixture(self, authed_client, mock_db):
        """cancel_run unlocks the associated fixture when session has one."""
        session = _make_session(status="ACTIVE", fixtureId="fix-1", config={})
        cancelled = _make_session(status="CANCELLED", fixtureId="fix-1")
        mock_db.session.find_unique.return_value = session
        mock_db.testexecution.update_many.return_value = None
        mock_db.validationqueueentry.find_first.return_value = None
        mock_db.session.update.return_value = cancelled

        with patch("api.v2.sessions.runs.log_audit"), \
             patch("api.v2.sessions.reporter._emit_validation_event"), \
             patch("api.v2.sessions.queue.process_queue"), \
             patch("api.v2.sessions.runs.get_storage_client", return_value=MagicMock()), \
             patch("api.v2.sessions.runs.get_bucket_name", return_value="bucket"):
            authed_client.post("/v2/sessions/sess-1/cancel")

        mock_db.fixture.update.assert_called_once()
        fixture_update = mock_db.fixture.update.call_args[1]["data"]
        assert fixture_update["status"] == "AVAILABLE"


class TestRerunSession:
    """Tests for POST /v2/sessions/<id>/rerun (rerun_session)."""

    def test_rerun_creates_new_session(self, authed_client, mock_db):
        """rerun_session clones the original session into a new PENDING session."""
        original = _make_session(status="COMPLETED", buildRunId="run-1")
        new_session = _make_session(
            id="sess-new",
            name="Rerun of Alpha Stage-5",
            status="PENDING",
            buildRunId="run-1",
        )
        mock_db.session.find_unique.return_value = original
        mock_db.buildrun.find_unique.return_value = make_obj(id="run-1")
        mock_db.session.create.return_value = new_session

        with patch("api.v2.sessions.runs.log_audit"):
            response = authed_client.post(
                "/v2/sessions/sess-1/rerun",
                data=json.dumps({}),
            )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["data"]["id"] == "sess-new"
        assert data["data"]["status"] == "PENDING"

    def test_rerun_original_not_found_returns_404(self, authed_client, mock_db):
        """rerun_session returns 404 when original session does not exist."""
        mock_db.session.find_unique.return_value = None

        response = authed_client.post(
            "/v2/sessions/bad-id/rerun",
            data=json.dumps({}),
        )

        assert response.status_code == 404
