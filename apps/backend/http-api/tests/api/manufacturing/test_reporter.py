"""Tests for unified reporter callbacks — /v2/runs/<id>/report/.

The manufacturing reporter endpoints are now part of the unified TestRun
reporter. These tests validate the key reporting paths using the new
data model: TestRun -> RunTarget -> TestExecution -> TestStep.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _run(**overrides):
    defaults = dict(
        id="s10-run-1",
        type="MANUFACTURING",
        productId="s10-prod-1",
        fixtureId="s10-fix-1",
        status="ACTIVE",
        targetCount=4,
        passedCount=0,
        failedCount=0,
        startedAt=_now(),
        completedAt=None,
        createdAt=_now(),
        updatedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _target(**overrides):
    defaults = dict(
        id="s10-target-1",
        runId="s10-run-1",
        slotIndex=0,
        slotId="slot-0",
        serialNumber=None,
        status="PENDING",
        startedAt=None,
        completedAt=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _execution(**overrides):
    defaults = dict(
        id="s10-exec-1",
        targetId="s10-target-1",
        executionIndex=0,
        name="test_electrical",
        module=None,
        status="RUNNING",
        startedAt=_now(),
        completedAt=None,
        durationMs=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_socketio():
    with patch("api.v2.runs.reporter._socketio", new=MagicMock()) as mock_sio:
        yield mock_sio


# ---------------------------------------------------------------------------
# POST /report/target-start
# ---------------------------------------------------------------------------

class TestTargetStart:
    def test_starts_target(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()
        mock_db.runtarget.find_unique.return_value = _target()
        mock_db.runtarget.update.return_value = _target(status="RUNNING")

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/target-start",
            data=json.dumps({"slotIndex": 0}),
        )
        assert resp.status_code == 200

    def test_returns_404_if_run_missing(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/s10-missing/report/target-start",
            data=json.dumps({"slotIndex": 0}),
        )
        assert resp.status_code == 404

    def test_returns_400_missing_fields(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/target-start",
            data=json.dumps({}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /report/execution-start
# ---------------------------------------------------------------------------

class TestExecutionStart:
    def test_creates_execution(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _target()
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _execution()

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/execution-start",
            data=json.dumps({"name": "test_electrical"}),
        )
        assert resp.status_code == 200

    def test_returns_400_missing_name(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/execution-start",
            data=json.dumps({}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /report/execution-result
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_updates_execution_status(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _target()
        mock_db.testexecution.find_first.return_value = _execution()
        mock_db.testexecution.update.return_value = _execution(status="PASSED")

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/execution-result",
            data=json.dumps({
                "name": "test_electrical",
                "passed": True,
                "durationMs": 500,
            }),
        )
        assert resp.status_code == 200

    def test_returns_404_if_execution_missing(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _target()
        mock_db.testexecution.find_first.return_value = None

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/execution-result",
            data=json.dumps({
                "name": "test_missing",
                "passed": True,
            }),
        )
        assert resp.status_code == 404

    def test_returns_400_missing_name(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/execution-result",
            data=json.dumps({"passed": True}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /report/target-result
# ---------------------------------------------------------------------------

class TestTargetResult:
    def test_completes_target(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()
        mock_db.runtarget.find_unique.return_value = _target()
        mock_db.runtarget.update.return_value = _target(status="PASSED")
        mock_db.testrun.update.return_value = _run(passedCount=1)
        mock_db.testexecution.count.return_value = 0

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/target-result",
            data=json.dumps({
                "slotIndex": 0,
                "status": "PASSED",
                "durationMs": 12000,
            }),
        )
        assert resp.status_code == 200

    def test_returns_404_if_target_missing(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _run()
        mock_db.runtarget.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/s10-run-1/report/target-result",
            data=json.dumps({
                "slotIndex": 99,
                "status": "PASSED",
            }),
        )
        assert resp.status_code == 404
