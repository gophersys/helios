"""Unit tests for the Validation Reporter callback endpoints.

Tests the /v2/sessions/<id>/report/* endpoints used by the
ConcordReporter pytest plugin to stream results back to the API.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from tests.conftest import make_obj


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ── Helpers ──────────────────────────────────────────────


def _make_session(**overrides):
    defaults = dict(
        id="sess-1",
        name="Alpha REV1.2 Debug",
        productId="prod-1",
        fixtureId=None,
        status="ACTIVE",
        config={"nodeId": "node-1", "serialNumber": "70B3D584C01E1FCC"},
        targetCount=3,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        startedAt=NOW,
        finishedAt=None,
        notes=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_device(**overrides):
    defaults = dict(
        id="dev-1",
        serialNumber="70B3D584C01E1FCC",
        sessionId="sess-1",
        status="PENDING",
        metadata=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_test(**overrides):
    defaults = dict(
        id="test-1",
        name="test_boot.test_power_cycle",
        productId="prod-1",
        category="boot",
        enabled=True,
        sortOrder=0,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_execution(**overrides):
    defaults = dict(
        id="exec-1",
        testId="test-1",
        nodeId="node-1",
        deviceId="dev-1",
        status="RUNNING",
        config=None,
        startedAt=NOW,
        finishedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ── ReportStart ──────────────────────────────────────────


class TestReportStart:

    def test_report_start(self, authed_client, mock_db):
        """Report start on an ACTIVE session succeeds."""
        mock_db.session.find_unique.return_value = _make_session(status="ACTIVE")

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps({"started": True}),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["runId"] == "sess-1"
        assert body["data"]["status"] == "ACTIVE"

        # Verify session was updated with startedAt
        mock_db.session.update.assert_called_once()
        update_data = mock_db.session.update.call_args[1]["data"]
        assert update_data["status"] == "ACTIVE"
        assert "startedAt" in update_data

    def test_report_start_nonexistent_run(self, authed_client, mock_db):
        """Report start on non-existent run returns 404."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/sessions/bad-id/report/start",
            data=json.dumps({"started": True}),
        )

        assert resp.status_code == 404
        body = json.loads(resp.data)
        assert "not found" in body["errors"][0]["message"].lower()

    def test_report_start_wrong_status(self, authed_client, mock_db):
        """Report start on a PASSED session returns 409."""
        mock_db.session.find_unique.return_value = _make_session(status="PASSED")

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps({"started": True}),
        )

        assert resp.status_code == 409
        body = json.loads(resp.data)
        assert "PASSED" in body["errors"][0]["message"]

    def test_report_start_empty_body(self, authed_client, mock_db):
        """Report start with no JSON body returns 400."""
        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps(None),
            content_type="application/json",
        )

        assert resp.status_code == 400


# ── ReportTestStart ──────────────────────────────────────


class TestReportTestStart:

    def test_report_test_start_creates_execution(self, authed_client, mock_db):
        """Test start with existing test and execution updates to RUNNING."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = _make_execution(status="QUEUED")

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
                "module": "boot",
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["testName"] == "test_boot.test_power_cycle"
        assert body["data"]["status"] == "RUNNING"

        # Verify execution was updated
        mock_db.testexecution.update.assert_called_once()
        update_data = mock_db.testexecution.update.call_args[1]["data"]
        assert update_data["status"] == "RUNNING"

    def test_report_test_start_auto_creates_test_def(self, authed_client, mock_db):
        """When test name not found, auto-creates Test and TestExecution."""
        session = _make_session()
        mock_db.session.find_unique.return_value = session
        mock_db.test.find_first.return_value = None  # not found
        new_test = _make_test(id="test-new", name="test_new.test_discovery")
        mock_db.test.create.return_value = new_test
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = None  # no execution yet
        mock_db.testexecution.create.return_value = _make_execution(id="exec-new")

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({
                "testName": "test_new.test_discovery",
                "module": "discovery",
            }),
        )

        assert resp.status_code == 200

        # Verify test was auto-created
        mock_db.test.create.assert_called_once()
        create_data = mock_db.test.create.call_args[1]["data"]
        assert create_data["name"] == "test_new.test_discovery"
        assert create_data["category"] == "discovery"
        assert create_data["productId"] == "prod-1"
        assert create_data["enabled"] is True

        # Verify execution was created (not just updated)
        mock_db.testexecution.create.assert_called_once()

    def test_report_test_start_missing_test_name(self, authed_client, mock_db):
        """Missing testName in body returns 400."""
        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({"module": "boot"}),
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "testName" in body["errors"][0]["message"]

    def test_report_test_start_no_device(self, authed_client, mock_db):
        """If session has no device, returns 500."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = None  # no device

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
            }),
        )

        assert resp.status_code == 500

    def test_report_test_start_updates_device_status(self, authed_client, mock_db):
        """Device status is updated to IN_PROGRESS."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        device = _make_device()
        mock_db.device.find_first.return_value = device
        mock_db.testexecution.find_first.return_value = _make_execution()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({"testName": "test_boot.test_power_cycle"}),
        )

        assert resp.status_code == 200
        mock_db.device.update.assert_called_once()
        update_data = mock_db.device.update.call_args[1]["data"]
        assert update_data["status"] == "IN_PROGRESS"


# ── ReportTestResult ─────────────────────────────────────


class TestReportTestResult:

    def test_report_result_passed(self, authed_client, mock_db):
        """Report a passing test result."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = make_obj(
            id="result-1", executionId="exec-1", stepIndex=0, groupIndex=0,
            passed=True, result={}, createdAt=NOW,
        )

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
                "passed": True,
                "durationS": 2.3,
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["passed"] is True
        assert body["data"]["executionId"] == "exec-1"

        # Verify execution updated to PASSED
        mock_db.testexecution.update.assert_called_once()
        update_data = mock_db.testexecution.update.call_args[1]["data"]
        assert update_data["status"] == "PASSED"

    def test_report_result_failed_with_error(self, authed_client, mock_db):
        """Report a failing test result with error message."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = make_obj(
            id="result-2", executionId="exec-1", stepIndex=0, groupIndex=0,
            passed=False, result={"errorMessage": "Current too low"}, createdAt=NOW,
        )

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
                "passed": False,
                "errorMessage": "Current too low",
                "durationS": 5.0,
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["passed"] is False

        # Verify execution updated to FAILED
        update_data = mock_db.testexecution.update.call_args[1]["data"]
        assert update_data["status"] == "FAILED"

    def test_report_result_with_measurements(self, authed_client, mock_db):
        """Report a result that includes measurement data."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = make_obj(
            id="result-3", executionId="exec-1", stepIndex=0, groupIndex=0,
            passed=True, result={"measurements": {"currentMa": 33.5}}, createdAt=NOW,
        )

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
                "passed": True,
                "measurements": {"currentMa": 33.5, "voltageV": 4.5},
            }),
        )

        assert resp.status_code == 200

        # Verify result was created with measurement data in result JSON
        create_data = mock_db.teststep.create.call_args[1]["data"]
        assert create_data["passed"] is True
        assert create_data["stepIndex"] == 0

    def test_report_result_test_not_found(self, authed_client, mock_db):
        """Reporting result for unknown test returns 404."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = None  # test not found

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_nonexistent.test_foo",
                "passed": True,
            }),
        )

        assert resp.status_code == 404

    def test_report_result_no_execution(self, authed_client, mock_db):
        """Reporting result when no execution exists returns 404."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = None  # no execution

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
                "passed": True,
            }),
        )

        assert resp.status_code == 404

    def test_report_result_step_index_increments(self, authed_client, mock_db):
        """stepIndex is based on existing result count for the execution."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = _make_device()
        mock_db.testexecution.find_first.return_value = _make_execution()
        mock_db.teststep.count.return_value = 3  # 3 existing results
        mock_db.teststep.create.return_value = make_obj(
            id="result-4", executionId="exec-1", stepIndex=3, groupIndex=0,
            passed=True, result={}, createdAt=NOW,
        )

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_boot.test_power_cycle",
                "passed": True,
            }),
        )

        assert resp.status_code == 200
        create_data = mock_db.teststep.create.call_args[1]["data"]
        assert create_data["stepIndex"] == 3


# ── ReportFinish ─────────────────────────────────────────


class TestReportFinish:

    def test_report_finish_updates_counts(self, authed_client, mock_db):
        """Finish updates session counts and sets PASSED or FAILED."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.device.find_first.return_value = _make_device()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({
                "total": 37,
                "passed": 35,
                "failed": 2,
                "errors": 0,
                "durationS": 120.0,
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["status"] == "FAILED"
        assert body["data"]["total"] == 37
        assert body["data"]["passed"] == 35
        assert body["data"]["failed"] == 2

        # Verify session update
        update_data = mock_db.session.update.call_args[1]["data"]
        assert update_data["status"] == "FAILED"
        assert update_data["completedCount"] == 37
        assert update_data["passedCount"] == 35
        assert update_data["failedCount"] == 2  # failed + errors
        assert "finishedAt" in update_data

    def test_report_finish_with_errors(self, authed_client, mock_db):
        """Errors are added to failedCount."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.device.find_first.return_value = _make_device()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({
                "total": 10,
                "passed": 7,
                "failed": 1,
                "errors": 2,
            }),
        )

        assert resp.status_code == 200

        update_data = mock_db.session.update.call_args[1]["data"]
        assert update_data["failedCount"] == 3  # 1 failed + 2 errors

    def test_report_finish_device_passed(self, authed_client, mock_db):
        """Device status is PASSED when no failures or errors."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.device.find_first.return_value = _make_device()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({
                "total": 10,
                "passed": 10,
                "failed": 0,
                "errors": 0,
            }),
        )

        assert resp.status_code == 200

        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "PASSED"

    def test_report_finish_device_failed(self, authed_client, mock_db):
        """Device status is FAILED when there are failures."""
        mock_db.session.find_unique.return_value = _make_session()
        mock_db.device.find_first.return_value = _make_device()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({
                "total": 10,
                "passed": 8,
                "failed": 2,
                "errors": 0,
            }),
        )

        assert resp.status_code == 200

        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "FAILED"

    def test_report_finish_nonexistent_run(self, authed_client, mock_db):
        """Finish on non-existent run returns 404."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/sessions/bad-id/report/finish",
            data=json.dumps({
                "total": 10,
                "passed": 10,
                "failed": 0,
            }),
        )

        assert resp.status_code == 404

    def test_report_finish_missing_required_fields(self, authed_client, mock_db):
        """Missing required fields in finish body returns 400."""
        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": 10}),
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "passed" in body["errors"][0]["message"].lower()
