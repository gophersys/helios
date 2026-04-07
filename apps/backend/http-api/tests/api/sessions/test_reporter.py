"""Tests for sessions/reporter.py — report_start, test_start, test_result, finish."""
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
    return datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _session(**overrides):
    defaults = dict(
        id="run-001",
        name="Alpha Smoke Run",
        status="PENDING",
        productId="prod-alpha",
        targetCount=1,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        startedAt=None,
        finishedAt=None,
        createdAt=_now(),
        config=None,
        fixtureId=None,
        buildRunId=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _device(**overrides):
    defaults = dict(
        id="dev-001",
        sessionId="run-001",
        serialNumber="SN0001",
        status="PENDING",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _test(**overrides):
    defaults = dict(
        id="test-001",
        name="test_boot_sequence",
        productId="prod-alpha",
        category="boot",
        enabled=True,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _execution(**overrides):
    defaults = dict(
        id="exec-001",
        testId="test-001",
        deviceId="dev-001",
        status="RUNNING",
        startedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ---------------------------------------------------------------------------
# POST /v2/sessions/<id>/report/start
# ---------------------------------------------------------------------------

class TestReportStart:
    """Tests for report_start endpoint."""

    def test_report_start_activates_session(self, authed_client, mock_db):
        """POST report/start transitions PENDING session to ACTIVE."""
        mock_db.session.find_unique.return_value = _session(status="PENDING")

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/start",
                data=json.dumps({"_": 1}),
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["runId"] == "run-001"
        assert body["data"]["status"] == "ACTIVE"
        mock_db.session.update.assert_called_once()

    def test_report_start_session_not_found_returns_404(self, authed_client, mock_db):
        """POST report/start returns 404 when session does not exist."""
        mock_db.session.find_unique.return_value = None

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/nonexistent/report/start",
                data=json.dumps({"_": 1}),
            )

        assert response.status_code == 404

    def test_report_start_wrong_status_returns_conflict(self, authed_client, mock_db):
        """POST report/start returns 409 when session is already PASSED."""
        mock_db.session.find_unique.return_value = _session(status="PASSED")

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/start",
                data=json.dumps({"_": 1}),
            )

        assert response.status_code == 409

    def test_report_start_empty_body_returns_400(self, authed_client, mock_db):
        """POST report/start with no body returns 400."""
        response = authed_client.post(
            "/v2/sessions/run-001/report/start",
            data=None,
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_report_start_unauthorized_returns_401(self, client, mock_db):
        """POST report/start without auth returns 401."""
        response = client.post(
            "/v2/sessions/run-001/report/start",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/sessions/<id>/report/test-start
# ---------------------------------------------------------------------------

class TestReportTestStart:
    """Tests for report_test_start endpoint."""

    def test_report_test_start_creates_execution(self, authed_client, mock_db):
        """POST test-start creates a RUNNING execution for a new test."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = None  # test doesn't exist yet
        mock_db.test.create.return_value = _test()
        mock_db.device.find_first.return_value = _device()
        mock_db.testexecution.find_first.return_value = None  # no prior execution
        mock_db.node.find_first.return_value = make_obj(id="node-1")
        mock_db.testexecution.create.return_value = _execution()

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/test-start",
                data=json.dumps({"testName": "test_boot_sequence", "module": "boot"}),
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["testName"] == "test_boot_sequence"
        assert body["data"]["status"] == "RUNNING"

    def test_report_test_start_missing_test_name_returns_400(self, authed_client, mock_db):
        """POST test-start without testName returns 400."""
        response = authed_client.post(
            "/v2/sessions/run-001/report/test-start",
            data=json.dumps({"module": "boot"}),
        )

        assert response.status_code == 400

    def test_report_test_start_session_not_found_returns_404(self, authed_client, mock_db):
        """POST test-start returns 404 when session does not exist."""
        mock_db.session.find_unique.return_value = None

        response = authed_client.post(
            "/v2/sessions/nonexistent/report/test-start",
            data=json.dumps({"testName": "test_boot"}),
        )

        assert response.status_code == 404

    def test_report_test_start_no_device_returns_500(self, authed_client, mock_db):
        """POST test-start returns 500 when no device is linked to session."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = _test()
        mock_db.device.find_first.return_value = None

        response = authed_client.post(
            "/v2/sessions/run-001/report/test-start",
            data=json.dumps({"testName": "test_boot"}),
        )

        assert response.status_code == 500

    def test_report_test_start_updates_existing_execution(self, authed_client, mock_db):
        """POST test-start updates status to RUNNING for existing execution."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = _test()
        mock_db.device.find_first.return_value = _device()
        existing_exec = _execution(status="PASSED")  # prior run
        mock_db.testexecution.find_first.return_value = existing_exec

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/test-start",
                data=json.dumps({"testName": "test_boot_sequence"}),
            )

        assert response.status_code == 200
        mock_db.testexecution.update.assert_called_once()


# ---------------------------------------------------------------------------
# POST /v2/sessions/<id>/report/test-result
# ---------------------------------------------------------------------------

class TestReportTestResult:
    """Tests for report_test_result endpoint."""

    def test_report_test_result_passed(self, authed_client, mock_db):
        """POST test-result with passed=True creates PASSED step."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = _test()
        mock_db.device.find_first.return_value = _device()
        mock_db.testexecution.find_first.return_value = _execution()
        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = make_obj(id="step-1")

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/test-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "passed": True,
                    "durationS": 1.5,
                }),
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["passed"] is True
        mock_db.testexecution.update.assert_called_once()

    def test_report_test_result_failed_with_error_message(self, authed_client, mock_db):
        """POST test-result with passed=False stores error message in step."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = _test()
        mock_db.device.find_first.return_value = _device()
        mock_db.testexecution.find_first.return_value = _execution()
        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = make_obj(id="step-2")

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/test-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "passed": False,
                    "errorMessage": "AssertionError: timeout waiting for boot",
                }),
            )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["passed"] is False

        # Verify error message stored in step
        create_call = mock_db.teststep.create.call_args
        assert "errorMessage" in create_call.kwargs["data"]

    def test_report_test_result_skipped(self, authed_client, mock_db):
        """POST test-result with skipped=True creates SKIPPED execution."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = _test()
        mock_db.device.find_first.return_value = _device()
        mock_db.testexecution.find_first.return_value = _execution()
        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = make_obj(id="step-3")

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            response = authed_client.post(
                "/v2/sessions/run-001/report/test-result",
                data=json.dumps({
                    "testName": "test_boot_sequence",
                    "passed": False,
                    "skipped": True,
                }),
            )

        assert response.status_code == 200
        update_call = mock_db.testexecution.update.call_args
        assert update_call.kwargs["data"]["status"] == "SKIPPED"

    def test_report_test_result_test_not_found_returns_404(self, authed_client, mock_db):
        """POST test-result returns 404 when test record is missing."""
        mock_db.session.find_unique.return_value = _session(status="ACTIVE")
        mock_db.test.find_first.return_value = None
        mock_db.device.find_first.return_value = _device()

        response = authed_client.post(
            "/v2/sessions/run-001/report/test-result",
            data=json.dumps({"testName": "unknown_test", "passed": True}),
        )

        assert response.status_code == 404

    def test_report_test_result_missing_test_name_returns_400(self, authed_client, mock_db):
        """POST test-result without testName returns 400."""
        response = authed_client.post(
            "/v2/sessions/run-001/report/test-result",
            data=json.dumps({"passed": True}),
        )

        assert response.status_code == 400

    def test_report_test_result_missing_passed_field_returns_400(self, authed_client, mock_db):
        """POST test-result without passed field returns 400."""
        response = authed_client.post(
            "/v2/sessions/run-001/report/test-result",
            data=json.dumps({"testName": "test_boot"}),
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/sessions/<id>/report/finish
# ---------------------------------------------------------------------------

class TestReportFinish:
    """Tests for report_finish endpoint."""

    def test_report_finish_single_slot_all_passed(self, authed_client, mock_db):
        """POST report/finish finalizes session as PASSED when all tests pass."""
        session = _session(
            status="ACTIVE",
            targetCount=1, completedCount=0, passedCount=0, failedCount=0,
            startedAt=_now(), config=None, fixtureId=None,
        )
        mock_db.session.find_unique.return_value = session
        mock_db.device.find_first.return_value = _device()

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            with patch("api.v2.sessions.logs.flush_log_buffers_for_run", create=True):
                with patch("api.v2.sessions.reporter.process_queue", create=True):
                    response = authed_client.post(
                        "/v2/sessions/run-001/report/finish",
                        data=json.dumps({
                            "total": 5, "passed": 5, "failed": 0, "errors": 0,
                        }),
                    )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["allSlotsComplete"] is True
        assert body["data"]["sessionStatus"] == "PASSED"

    def test_report_finish_single_slot_with_failures(self, authed_client, mock_db):
        """POST report/finish finalizes session as FAILED when any test fails."""
        session = _session(
            status="ACTIVE",
            targetCount=1, completedCount=0, passedCount=0, failedCount=0,
            startedAt=_now(), config=None, fixtureId=None,
        )
        mock_db.session.find_unique.return_value = session
        mock_db.device.find_first.return_value = _device()

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            with patch("api.v2.sessions.logs.flush_log_buffers_for_run", create=True):
                with patch("api.v2.sessions.reporter.process_queue", create=True):
                    response = authed_client.post(
                        "/v2/sessions/run-001/report/finish",
                        data=json.dumps({
                            "total": 5, "passed": 3, "failed": 2, "errors": 0,
                        }),
                    )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["sessionStatus"] == "FAILED"

    def test_report_finish_multi_slot_not_final(self, authed_client, mock_db):
        """POST report/finish with targetCount=2 does not finalize on first slot."""
        session = _session(
            status="ACTIVE",
            targetCount=2, completedCount=0, passedCount=0, failedCount=0,
            startedAt=_now(), config=None, fixtureId=None,
        )
        mock_db.session.find_unique.return_value = session
        mock_db.device.find_first.return_value = _device()

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            with patch("api.v2.sessions.logs.flush_log_buffers_for_run", create=True):
                response = authed_client.post(
                    "/v2/sessions/run-001/report/finish",
                    data=json.dumps({"total": 5, "passed": 5, "failed": 0, "errors": 0}),
                )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["data"]["allSlotsComplete"] is False
        assert body["data"]["sessionStatus"] == "ACTIVE"

    def test_report_finish_session_not_found_returns_404(self, authed_client, mock_db):
        """POST report/finish returns 404 for nonexistent session."""
        mock_db.session.find_unique.return_value = None

        response = authed_client.post(
            "/v2/sessions/nonexistent/report/finish",
            data=json.dumps({"total": 0, "passed": 0, "failed": 0}),
        )

        assert response.status_code == 404

    def test_report_finish_missing_total_returns_400(self, authed_client, mock_db):
        """POST report/finish without total field returns 400."""
        response = authed_client.post(
            "/v2/sessions/run-001/report/finish",
            data=json.dumps({"passed": 5, "failed": 0}),
        )

        assert response.status_code == 400

    def test_report_finish_unlocks_fixture_when_configured(self, authed_client, mock_db):
        """POST report/finish releases the fixture lock stored in session.config."""
        fixture = make_obj(id="fix-1", stationId="bench-1", status="LOCKED")
        session = _session(
            status="ACTIVE",
            targetCount=1, completedCount=0, passedCount=0, failedCount=0,
            startedAt=_now(),
            config={"fixtureId": "fix-1"},
            fixtureId=None,
        )
        mock_db.session.find_unique.return_value = session
        mock_db.device.find_first.return_value = _device()
        mock_db.fixture.find_unique.return_value = fixture

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            with patch("api.v2.sessions.logs.flush_log_buffers_for_run", create=True):
                with patch("api.v2.sessions.reporter.process_queue", create=True):
                    response = authed_client.post(
                        "/v2/sessions/run-001/report/finish",
                        data=json.dumps({"total": 1, "passed": 1, "failed": 0, "errors": 0}),
                    )

        assert response.status_code == 200
        mock_db.fixture.update.assert_called_once()
        update_call = mock_db.fixture.update.call_args
        assert update_call.kwargs["data"]["status"] == "AVAILABLE"

    def test_report_finish_propagates_to_pipeline(self, authed_client, mock_db):
        """POST report/finish updates parent pipeline status when buildRunId is set."""
        session = _session(
            status="ACTIVE",
            targetCount=1, completedCount=0, passedCount=0, failedCount=0,
            startedAt=_now(), config=None, fixtureId=None,
            buildRunId="pipe-001",
        )
        mock_db.session.find_unique.return_value = session
        mock_db.device.find_first.return_value = _device()

        with patch("api.v2.sessions.reporter._emit_validation_event"):
            with patch("api.v2.sessions.logs.flush_log_buffers_for_run", create=True):
                with patch("api.v2.sessions.reporter.process_queue", create=True):
                    response = authed_client.post(
                        "/v2/sessions/run-001/report/finish",
                        data=json.dumps({"total": 3, "passed": 3, "failed": 0, "errors": 0}),
                    )

        assert response.status_code == 200
        mock_db.buildrun.update.assert_called_once()
        call_data = mock_db.buildrun.update.call_args.kwargs["data"]
        assert call_data["status"] == "SUCCESS"

    def test_report_finish_unauthorized_returns_401(self, client, mock_db):
        """POST report/finish without auth returns 401."""
        response = client.post(
            "/v2/sessions/run-001/report/finish",
            data=json.dumps({"total": 0, "passed": 0, "failed": 0}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401

    # TODO: test_report_finish_multi_slot_second_slot_finalizes
    # TODO: test_report_finish_device_id_header_selects_device
    # TODO: test_report_finish_errors_counted_as_failures
