"""Tests for api/v2/sessions/executions.py — execution listing and results."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj

_now = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_step(**kw):
    defaults = dict(
        id="s-1", executionId="ex-1", stepIndex=0, name="power_on",
        status="PASSED", passed=True, errorMessage=None, measurements=None,
        logOutput=None, durationMs=500, startedAt=_now, finishedAt=_now,
        createdAt=_now,
    )
    defaults.update(kw)
    return make_obj(**defaults)


def _make_execution(**kw):
    defaults = dict(
        id="ex-1", testId="t-1", nodeId="n-1", deviceId="d-1",
        status="PASSED", config=None,
        startedAt=_now, finishedAt=_now, createdAt=_now, updatedAt=_now,
        test=make_obj(id="t-1", name="test_boot", category="power"),
        steps=[],
    )
    defaults.update(kw)
    return make_obj(**defaults)


class TestListExecutions:
    def test_session_not_found_returns_404(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/executions")
        assert resp.status_code == 404

    def test_returns_empty_list(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.find_many.return_value = []

        resp = authed_client.get("/v2/sessions/run-1/executions")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    def test_returns_executions_with_pagination(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        mock_db.testexecution.count.return_value = 2
        mock_db.testexecution.find_many.return_value = [_make_execution()]

        resp = authed_client.get("/v2/sessions/run-1/executions?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["data"]) == 1

    def test_status_filter(self, authed_client, mock_db):
        mock_db.session.find_unique.return_value = make_obj(id="run-1")
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.find_many.return_value = []

        resp = authed_client.get("/v2/sessions/run-1/executions?status=passed")
        assert resp.status_code == 200
        call_args = mock_db.testexecution.find_many.call_args
        assert call_args[1]["where"]["status"] == "PASSED"


class TestListExecutionResults:
    def test_execution_not_found_returns_404(self, authed_client, mock_db):
        mock_db.testexecution.find_unique.return_value = None
        resp = authed_client.get("/v2/sessions/run-1/executions/ex-1/results")
        assert resp.status_code == 404

    def test_execution_wrong_run_returns_404(self, authed_client, mock_db):
        ex = _make_execution(device=make_obj(sessionId="other-run"))
        mock_db.testexecution.find_unique.return_value = ex
        resp = authed_client.get("/v2/sessions/run-1/executions/ex-1/results")
        assert resp.status_code == 404

    def test_execution_no_device_returns_404(self, authed_client, mock_db):
        ex = _make_execution(device=None)
        mock_db.testexecution.find_unique.return_value = ex
        resp = authed_client.get("/v2/sessions/run-1/executions/ex-1/results")
        assert resp.status_code == 404

    def test_returns_execution_with_steps(self, authed_client, mock_db):
        ex = _make_execution(device=make_obj(sessionId="run-1"))
        mock_db.testexecution.find_unique.return_value = ex
        mock_db.teststep.find_many.return_value = [_make_step()]

        resp = authed_client.get("/v2/sessions/run-1/executions/ex-1/results")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "execution" in data
        assert len(data["steps"]) == 1
