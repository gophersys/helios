"""Tests for runs/reporter.py -- the unified reporter callbacks.

Data model: TestRun -> RunTarget -> TestExecution -> TestStep
No more Test model -- execution names are stored directly on TestExecution.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make_run(**overrides):
    defaults = dict(
        id="run-1",
        type="VALIDATION",
        status="ACTIVE",
        productId="prod-1",
        fixtureId="fix-1",
        operatorId="user-1",
        config={},
        startedAt=_now(),
        targetCount=1,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        buildRunId=None,
        manufacturingSessionId=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_target(**overrides):
    defaults = dict(
        id="target-1",
        runId="run-1",
        slotIndex=0,
        status="RUNNING",
        serialNumber="0964",
        executions=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_execution(**overrides):
    defaults = dict(
        id="exec-1",
        targetId="target-1",
        executionIndex=0,
        name="test_boot_sequence",
        module="boot",
        status="RUNNING",
        startedAt=_now(),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_step(**overrides):
    defaults = dict(
        id="step-1",
        executionId="exec-1",
        stepIndex=0,
        name="step-0",
        status="RUNNING",
        startedAt=_now(),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/start
# ---------------------------------------------------------------------------

class TestReportStart:
    """Tests for report_start -- transitions PENDING/ACTIVE run to ACTIVE."""

    def test_activates_pending_run(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(status="PENDING")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/start",
                data=json.dumps({"_": 1}),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["runId"] == "run-1"
        assert body["data"]["status"] == "ACTIVE"
        mock_db.testrun.update.assert_called_once()

    def test_run_not_found_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/nonexistent/report/start",
                data=json.dumps({"_": 1}),
            )

        assert resp.status_code == 404

    def test_wrong_status_returns_400(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(status="COMPLETED")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/start",
                data=json.dumps({"_": 1}),
            )

        assert resp.status_code == 400

    def test_already_active_is_ok(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(status="ACTIVE")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/start",
                data=json.dumps({"_": 1}),
            )

        assert resp.status_code == 200

    def test_unauthorized_returns_401(self, client, mock_db):
        resp = client.post(
            "/v2/runs/run-1/report/start",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/test-list
# ---------------------------------------------------------------------------

class TestReportTestList:
    """Tests for report_test_list -- stores test list in run config."""

    def test_stores_test_list_in_config(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(config={})

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/test-list",
                data=json.dumps({"tests": ["test_a", "test_b", "test_c"]}),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["count"] == 3
        mock_db.testrun.update.assert_called_once()

    def test_empty_body_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/test-list",
            data=None,
            content_type="application/json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/execution-start
# ---------------------------------------------------------------------------

class TestReportExecutionStart:
    """Tests for report_execution_start -- creates or updates a TestExecution."""

    def test_creates_new_execution(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({"testName": "test_boot_sequence", "module": "boot"}),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["name"] == "test_boot_sequence"
        assert body["data"]["status"] == "RUNNING"
        mock_db.testexecution.create.assert_called_once()

    def test_accepts_name_field(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution(name="test_power")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({"name": "test_power"}),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["name"] == "test_power"

    def test_updates_existing_execution(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        existing = _make_execution(status="PASSED")
        mock_db.testexecution.find_first.return_value = existing

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({"testName": "test_boot_sequence"}),
            )

        assert resp.status_code == 200
        mock_db.testexecution.update.assert_called_once()

    def test_missing_name_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({"module": "boot"}),
        )
        assert resp.status_code == 400

    def test_no_target_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_first.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({"testName": "test_boot"}),
        )
        assert resp.status_code == 404

    def test_resolves_target_by_slot_index(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_unique.return_value = _make_target(id="target-2", slotIndex=1)
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution(targetId="target-2")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({
                    "testName": "test_boot",
                    "slotIndex": 1,
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["targetId"] == "target-2"


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/execution-result
# ---------------------------------------------------------------------------

class TestReportExecutionResult:
    """Tests for report_execution_result -- marks execution as PASSED/FAILED."""

    def test_passed_execution(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = _make_execution()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "passed": True,
                    "durationMs": 1500,
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["passed"] is True
        assert body["data"]["status"] == "PASSED"
        mock_db.testexecution.update.assert_called_once()

    def test_failed_with_error_message(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = _make_execution()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "passed": False,
                    "errorMessage": "AssertionError: timeout waiting for boot",
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["passed"] is False
        update_data = mock_db.testexecution.update.call_args.kwargs["data"]
        assert update_data["errorMessage"] == "AssertionError: timeout waiting for boot"

    def test_accepts_duration_seconds(self, authed_client, mock_db):
        """durationS is converted to durationMs."""
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = _make_execution()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "passed": True,
                    "durationS": 2.5,
                }),
            )

        assert resp.status_code == 200
        update_data = mock_db.testexecution.update.call_args.kwargs["data"]
        assert update_data["durationMs"] == 2500

    def test_auto_creates_execution_when_not_found(self, authed_client, mock_db):
        """execution-result auto-creates execution if it doesn't exist
        (handles setup-phase skips where execution-start never fired)."""
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution(
            id="auto-exec-1", name="unknown_test",
        )

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-result",
                data=json.dumps({"testName": "unknown_test", "passed": True}),
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["name"] == "unknown_test"
        assert body["data"]["passed"] is True
        mock_db.testexecution.create.assert_called_once()

    def test_missing_name_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-result",
            data=json.dumps({"passed": True}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/step-start
# ---------------------------------------------------------------------------

class TestReportStepStart:
    """Tests for report_step_start -- creates a TestStep under an execution."""

    def test_creates_step(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.create.return_value = _make_step()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/step-start",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "stepName": "power_on",
                    "stepIndex": 0,
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["stepIndex"] == 0
        assert body["data"]["status"] == "RUNNING"
        mock_db.teststep.create.assert_called_once()

    def test_missing_test_name_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/step-start",
            data=json.dumps({"stepName": "power_on", "stepIndex": 0}),
        )
        assert resp.status_code == 400

    def test_missing_step_index_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/step-start",
            data=json.dumps({"testName": "test_boot"}),
        )
        assert resp.status_code == 400

    def test_execution_not_found_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/step-start",
            data=json.dumps({
                "testName": "unknown_test",
                "stepIndex": 0,
            }),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/step-result
# ---------------------------------------------------------------------------

class TestReportStepResult:
    """Tests for report_step_result -- updates or creates a step with result."""

    def test_updates_existing_step(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.find_first.return_value = _make_step()
        mock_db.teststep.update.return_value = _make_step(status="PASSED")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/step-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "stepIndex": 0,
                    "passed": True,
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["passed"] is True
        mock_db.teststep.update.assert_called_once()

    def test_creates_step_when_no_prior_start(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.find_first.return_value = None
        mock_db.teststep.create.return_value = _make_step(status="FAILED")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/step-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "stepIndex": 0,
                    "passed": False,
                    "errorMessage": "Timed out",
                }),
            )

        assert resp.status_code == 200
        mock_db.teststep.create.assert_called_once()
        create_data = mock_db.teststep.create.call_args.kwargs["data"]
        assert create_data["status"] == "FAILED"
        assert create_data["errorMessage"] == "Timed out"

    def test_missing_test_name_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/step-result",
            data=json.dumps({"stepIndex": 0, "passed": True}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/target-result
# ---------------------------------------------------------------------------

class TestReportTargetResult:
    """Tests for report_target_result -- updates target status."""

    def test_updates_target_status(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_unique.return_value = _make_target()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/target-result",
                data=json.dumps({
                    "slotIndex": 0,
                    "status": "PASSED",
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "PASSED"
        mock_db.runtarget.update.assert_called_once()

    def test_missing_slot_index_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/target-result",
            data=json.dumps({"status": "COMPLETED"}),
        )
        assert resp.status_code == 400

    def test_missing_status_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/target-result",
            data=json.dumps({"slotIndex": 0}),
        )
        assert resp.status_code == 400

    def test_target_not_found_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/target-result",
            data=json.dumps({"slotIndex": 5, "status": "PASSED"}),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/finish
# ---------------------------------------------------------------------------

class TestReportFinish:
    """Tests for report_finish -- finalizes run, cleans up fixtures, propagates."""

    def test_all_passed_completes_run(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(fixtureId=None)
        mock_db.runtarget.find_many.return_value = [_make_target()]

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 5, "passed": 5, "failed": 0, "errors": 0,
                    }),
                )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "COMPLETED"
        assert body["data"]["passed"] == 5
        mock_db.testrun.update.assert_called()

    def test_failures_mark_run_as_failed(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(fixtureId=None)
        mock_db.runtarget.find_many.return_value = [_make_target()]

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 5, "passed": 3, "failed": 2, "errors": 0,
                    }),
                )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "FAILED"

    def test_errors_count_as_failures(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(fixtureId=None)
        mock_db.runtarget.find_many.return_value = [_make_target()]

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 5, "passed": 5, "failed": 0, "errors": 1,
                    }),
                )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "FAILED"

    def test_run_not_found_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/nonexistent/report/finish",
            data=json.dumps({"total": 0, "passed": 0, "failed": 0}),
        )
        assert resp.status_code == 404

    def test_empty_body_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/finish",
            data=None,
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unlocks_fixture(self, authed_client, mock_db):
        fixture = make_obj(id="fix-1", status="LOCKED")
        run = _make_run(fixtureId="fix-1")
        mock_db.testrun.find_unique.return_value = run
        mock_db.runtarget.find_many.return_value = [_make_target()]
        mock_db.fixture.find_unique.return_value = fixture

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 1, "passed": 1, "failed": 0, "errors": 0,
                    }),
                )

        assert resp.status_code == 200
        mock_db.fixture.update.assert_called_once()
        update_data = mock_db.fixture.update.call_args.kwargs["data"]
        assert update_data["status"] == "AVAILABLE"

    def test_propagates_to_build_run(self, authed_client, mock_db):
        run = _make_run(buildRunId="pipe-1", fixtureId=None, failedCount=0)
        mock_db.testrun.find_unique.return_value = run
        mock_db.runtarget.find_many.return_value = [_make_target()]

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 3, "passed": 3, "failed": 0, "errors": 0,
                    }),
                )

        assert resp.status_code == 200
        mock_db.buildrun.update.assert_called_once()
        pipe_data = mock_db.buildrun.update.call_args.kwargs["data"]
        assert pipe_data["status"] == "SUCCESS"

    def test_marks_leftover_targets_with_computed_status(self, authed_client, mock_db):
        """RUNNING targets get their status computed from execution results."""
        mock_db.testrun.find_unique.return_value = _make_run(fixtureId=None)
        mock_db.runtarget.find_many.return_value = [_make_target(status="RUNNING")]

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 5, "passed": 5, "failed": 0, "errors": 0,
                    }),
                )

        # Per-target update for the RUNNING target (computed status = ERROR
        # because no executions present)
        mock_db.runtarget.update.assert_called_once()
        update_data = mock_db.runtarget.update.call_args.kwargs["data"]
        assert update_data["status"] == "ERROR"

    def test_accepts_duration_seconds(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(fixtureId=None)
        mock_db.runtarget.find_many.return_value = [_make_target()]

        with patch("api.v2.runs.reporter._emit"):
            with patch("api.v2.runs.reporter._process_queue"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/finish",
                    data=json.dumps({
                        "total": 1, "passed": 1, "failed": 0, "errors": 0,
                        "durationS": 30.5,
                    }),
                )

        assert resp.status_code == 200
        update_data = mock_db.testrun.update.call_args.kwargs["data"]
        assert update_data["durationMs"] == 30500

    def test_unauthorized_returns_401(self, client, mock_db):
        resp = client.post(
            "/v2/runs/run-1/report/finish",
            data=json.dumps({"total": 0, "passed": 0, "failed": 0}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/log-chunk (routed to logs.report_log_chunk)
# ---------------------------------------------------------------------------

class TestReportLogChunk:
    """Tests for the /report/log-chunk endpoint (handled by logs module)."""

    def test_valid_chunk_returns_200(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()

        with patch("api.v2.runs.logs._schedule_flush"):
            with patch("api.v2.runs.ws.emit_to_run"):
                resp = authed_client.post(
                    "/v2/runs/run-1/report/log-chunk",
                    data=json.dumps({
                        "file": "stdout.log",
                        "data": "bG9nIGxpbmUK",
                        "offset": 0,
                    }),
                )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["received"] is True

    def test_missing_file_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/log-chunk",
            data=json.dumps({"data": "bG9n", "offset": 0}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/telemetry
# ---------------------------------------------------------------------------

class TestReportTelemetry:
    """Tests for report_telemetry -- emits WS event, no DB storage."""

    def test_broadcasts_samples(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()

        with patch("api.v2.runs.reporter._emit") as mock_emit:
            resp = authed_client.post(
                "/v2/runs/run-1/report/telemetry",
                data=json.dumps({
                    "samples": [
                        {"channel": "voltage", "value": 3.3, "timestamp": 1000},
                        {"channel": "current", "value": 0.015, "timestamp": 1001},
                    ],
                }),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["count"] == 2
        mock_emit.assert_called_once()

    def test_empty_samples_returns_zero_count(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/telemetry",
                data=json.dumps({"samples": []}),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["count"] == 0

    def test_empty_body_returns_400(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/telemetry",
            data=None,
            content_type="application/json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/runs/<id>/report/target-start
# ---------------------------------------------------------------------------

class TestReportTargetStart:
    """Tests for report_target_start -- transitions target to RUNNING."""

    def test_target_start_success(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_unique.return_value = _make_target(status="PENDING")

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/target-start",
                data=json.dumps({"slotIndex": 0}),
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "RUNNING"
        assert body["data"]["slotIndex"] == 0
        mock_db.runtarget.update.assert_called_once()
        update_data = mock_db.runtarget.update.call_args.kwargs["data"]
        assert update_data["status"] == "RUNNING"
        assert update_data["startedAt"] is not None

    def test_target_start_missing_slot_index(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs/run-1/report/target-start",
            data=json.dumps({"serialNumber": "0964"}),
        )
        assert resp.status_code == 400

    def test_target_start_target_not_found(self, authed_client, mock_db):
        mock_db.runtarget.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/target-start",
            data=json.dumps({"slotIndex": 5}),
        )
        assert resp.status_code == 404

    def test_target_start_updates_serial_and_device(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_unique.return_value = _make_target()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/target-start",
                data=json.dumps({
                    "slotIndex": 0,
                    "serialNumber": "1234",
                    "deviceId": "70B3D584C01E1FCC",
                }),
            )

        assert resp.status_code == 200
        update_data = mock_db.runtarget.update.call_args.kwargs["data"]
        assert update_data["serialNumber"] == "1234"
        assert update_data["deviceId"] == "70B3D584C01E1FCC"
