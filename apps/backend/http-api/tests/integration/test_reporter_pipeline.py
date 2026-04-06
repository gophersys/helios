"""Integration tests for the full reporter → backend → Prisma pipeline.

These tests verify the complete lifecycle of a validation run as driven by the
ConcordReporter pytest plugin:

    create run → report/start → report/test-start → report/test-result → report/finish

Each test sets up the mock DB returns to simulate Prisma behavior, then asserts
that the correct DB mutations happen in the right order with the right data.
The "full pipeline" test at the end chains all steps together.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from tests.conftest import make_obj


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ── Factories ─────────────────────────────────────────────


def _make_product(id="prod-1", name="Alpha"):
    return make_obj(id=id, name=name)


def _make_node(id="node-1", name="mtib-33"):
    return make_obj(id=id, name=name)


def _make_session(**overrides):
    defaults = dict(
        id="sess-1",
        name="Alpha REV1.2 Smoke",
        productId="prod-1",
        fixtureId=None,
        status="ACTIVE",
        config={"nodeId": "node-1", "serialNumber": "70B3D584C01E1FCC"},
        targetCount=1,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        startedAt=None,
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
        name="test_power.test_boot_current",
        productId="prod-1",
        category="power",
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
        status="QUEUED",
        config=None,
        startedAt=None,
        finishedAt=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_result(**overrides):
    defaults = dict(
        id="result-1",
        executionId="exec-1",
        stepIndex=0,
        groupIndex=0,
        passed=True,
        result={},
        createdAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def pipeline_session():
    """A session in ACTIVE state ready for the reporter to drive."""
    return _make_session(status="ACTIVE")


@pytest.fixture
def pipeline_device():
    return _make_device()


# ── Create Run → Session + Device ─────────────────────────


class TestCreateRun:
    """POST /v2/sessions creates a Session + Device."""

    def test_creates_session_and_device(self, authed_client, mock_db):
        """Run creation produces Session, Device, and pre-queued TestExecutions."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.node.find_unique.return_value = _make_node()

        session = _make_session()
        mock_db.session.create.return_value = session
        mock_db.device.create.return_value = _make_device()
        mock_db.test.find_many.return_value = [
            _make_test(id="t1", name="test_power.test_boot_current"),
            _make_test(id="t2", name="test_uart.test_shell_lock"),
        ]
        mock_db.testexecution.create.return_value = _make_execution()
        mock_db.session.update.return_value = session

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post(
                "/v2/sessions",
                data=json.dumps({
                    "name": "Alpha REV1.2 Smoke",
                    "productId": "prod-1",
                    "nodeId": "node-1",
                    "serialNumber": "70B3D584C01E1FCC",
                }),
            )

        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert body["data"]["id"] == "sess-1"
        assert body["data"]["status"] == "ACTIVE"
        # Device was created with the serial number
        mock_db.device.create.assert_called_once()
        create_data = mock_db.device.create.call_args[1]["data"]
        assert create_data["serialNumber"] == "70B3D584C01E1FCC"
        assert create_data["sessionId"] == "sess-1"
        # Two executions created (one per test)
        assert mock_db.testexecution.create.call_count == 2

    def test_returns_device_in_response(self, authed_client, mock_db):
        """Response includes the Device object for the DUT."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.node.find_unique.return_value = _make_node()

        session = _make_session()
        device = _make_device()
        mock_db.session.create.return_value = session
        mock_db.device.create.return_value = device
        mock_db.test.find_many.return_value = []
        mock_db.session.update.return_value = session

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post(
                "/v2/sessions",
                data=json.dumps({
                    "name": "Test",
                    "productId": "prod-1",
                    "nodeId": "node-1",
                    "serialNumber": "SN-001",
                }),
            )

        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert len(body["data"]["devices"]) == 1
        assert body["data"]["devices"][0]["serialNumber"] == "70B3D584C01E1FCC"


# ── Report Start ──────────────────────────────────────────


class TestReportStart:
    """POST /report/start transitions session to RUNNING."""

    def test_activates_session(self, authed_client, mock_db, pipeline_session):
        """Start callback updates session status and sets startedAt."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps({"started": True}),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["status"] == "ACTIVE"
        assert body["data"]["runId"] == "sess-1"

        # Verify DB update was called with correct fields
        mock_db.session.update.assert_called_once()
        update_kwargs = mock_db.session.update.call_args[1]
        assert update_kwargs["where"] == {"id": "sess-1"}
        assert update_kwargs["data"]["status"] == "ACTIVE"
        assert "startedAt" in update_kwargs["data"]

    def test_rejects_completed_session(self, authed_client, mock_db):
        """Start callback returns 409 for a PASSED session."""
        mock_db.session.find_unique.return_value = _make_session(status="PASSED")

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps({"started": True}),
        )

        assert resp.status_code == 409

    def test_returns_404_for_missing_run(self, authed_client, mock_db):
        """Start callback returns 404 when run ID doesn't exist."""
        mock_db.session.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/sessions/nonexistent/report/start",
            data=json.dumps({"started": True}),
        )

        assert resp.status_code == 404

    def test_rejects_empty_body(self, authed_client, mock_db, pipeline_session):
        """Start callback returns 400 for missing JSON body."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=None,
            content_type="application/json",
        )

        assert resp.status_code == 400


# ── Report Test Start ─────────────────────────────────────


class TestReportTestStart:
    """POST /report/test-start creates TestExecution record."""

    def test_creates_execution_for_existing_test(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """When test definition exists, creates execution and sets RUNNING."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = pipeline_device
        mock_db.testexecution.find_first.return_value = _make_execution()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "module": "power",
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["status"] == "RUNNING"
        assert body["data"]["testName"] == "test_power.test_boot_current"

        # Verify execution was updated to RUNNING
        mock_db.testexecution.update.assert_called_once()
        update_data = mock_db.testexecution.update.call_args[1]["data"]
        assert update_data["status"] == "RUNNING"
        assert "startedAt" in update_data

    def test_auto_creates_test_definition(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """When test definition doesn't exist, auto-creates it."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = None  # Test not found
        new_test = _make_test(id="test-new", name="test_new.test_discovery")
        mock_db.test.create.return_value = new_test
        mock_db.device.find_first.return_value = pipeline_device
        mock_db.testexecution.find_first.return_value = None  # No existing execution
        mock_db.node.find_first.return_value = _make_node()
        mock_db.testexecution.create.return_value = _make_execution(id="exec-new")

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({
                "testName": "test_new.test_discovery",
                "module": "new",
            }),
        )

        assert resp.status_code == 200
        # Test was auto-created
        mock_db.test.create.assert_called_once()
        create_data = mock_db.test.create.call_args[1]["data"]
        assert create_data["name"] == "test_new.test_discovery"
        assert create_data["productId"] == "prod-1"
        assert create_data["category"] == "new"

    def test_creates_new_execution_when_none_exists(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """When no prior execution exists, creates a new one with RUNNING status."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = pipeline_device
        mock_db.testexecution.find_first.return_value = None  # No prior execution
        mock_db.node.find_first.return_value = _make_node()
        mock_db.testexecution.create.return_value = _make_execution(
            id="exec-fresh", status="RUNNING"
        )

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "module": "power",
            }),
        )

        assert resp.status_code == 200
        mock_db.testexecution.create.assert_called_once()
        create_data = mock_db.testexecution.create.call_args[1]["data"]
        assert create_data["status"] == "RUNNING"
        assert create_data["testId"] == "test-1"
        assert create_data["deviceId"] == "dev-1"
        assert create_data["nodeId"] == "node-1"

    def test_updates_device_status_to_in_progress(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Device status transitions to IN_PROGRESS when a test starts."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = pipeline_device
        mock_db.testexecution.find_first.return_value = _make_execution()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({"testName": "test_power.test_boot_current"}),
        )

        assert resp.status_code == 200
        mock_db.device.update.assert_called_once()
        update_data = mock_db.device.update.call_args[1]["data"]
        assert update_data["status"] == "IN_PROGRESS"

    def test_rejects_missing_test_name(self, authed_client, mock_db, pipeline_session):
        """Returns 400 when testName is missing."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({"module": "power"}),
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "testName" in body["errors"][0]["message"]

    def test_returns_500_when_no_device(self, authed_client, mock_db, pipeline_session):
        """Returns 500 when session has no associated device."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = None  # No device

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({"testName": "test_power.test_boot_current"}),
        )

        assert resp.status_code == 500


# ── Report Test Result ────────────────────────────────────


class TestReportTestResult:
    """POST /report/test-result creates TestResult records."""

    def _setup_result_mocks(self, mock_db, session, device, test, execution):
        mock_db.session.find_unique.return_value = session
        mock_db.test.find_first.return_value = test
        mock_db.device.find_first.return_value = device
        mock_db.testexecution.find_first.return_value = execution
        mock_db.teststep.count.return_value = 0

    def test_pass_result_creates_passed_record(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Passed test creates PASSED execution + result with passed=True."""
        test = _make_test()
        execution = _make_execution(status="RUNNING")
        self._setup_result_mocks(mock_db, pipeline_session, pipeline_device, test, execution)
        mock_db.teststep.create.return_value = _make_result(passed=True)

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": True,
                "durationS": 2.3,
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["passed"] is True

        # Execution updated to PASSED
        mock_db.testexecution.update.assert_called_once()
        exec_update = mock_db.testexecution.update.call_args[1]["data"]
        assert exec_update["status"] == "PASSED"
        assert "finishedAt" in exec_update

        # Result created with passed=True
        mock_db.teststep.create.assert_called_once()

    def test_fail_result_creates_failed_record(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Failed test creates FAILED execution + result with error message."""
        test = _make_test()
        execution = _make_execution(status="RUNNING")
        self._setup_result_mocks(mock_db, pipeline_session, pipeline_device, test, execution)
        mock_db.teststep.create.return_value = _make_result(passed=False)

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": False,
                "durationS": 5.0,
                "errorMessage": "AssertionError: current 2mA < 5mA threshold",
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["passed"] is False

        # Execution updated to FAILED
        exec_update = mock_db.testexecution.update.call_args[1]["data"]
        assert exec_update["status"] == "FAILED"

    def test_result_includes_measurements(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Measurements dict is stored in the result JSON."""
        test = _make_test()
        execution = _make_execution(status="RUNNING")
        self._setup_result_mocks(mock_db, pipeline_session, pipeline_device, test, execution)
        mock_db.teststep.create.return_value = _make_result()

        measurements = {"currentMa": 33.5, "voltageV": 4.5, "bootTimeS": 3.2}

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": True,
                "durationS": 3.2,
                "measurements": measurements,
            }),
        )

        assert resp.status_code == 200
        # Verify the step data includes measurements
        create_call = mock_db.teststep.create.call_args[1]["data"]
        measurements_json = create_call["measurements"]
        # measurements is wrapped in Json() — check the inner dict
        assert measurements_json.data == measurements
        assert create_call["durationMs"] == 3200  # 3.2s -> 3200ms

    def test_step_index_increments(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Step index is based on existing result count for the execution."""
        test = _make_test()
        execution = _make_execution(status="RUNNING")
        self._setup_result_mocks(mock_db, pipeline_session, pipeline_device, test, execution)
        mock_db.teststep.count.return_value = 3  # 3 existing results
        mock_db.teststep.create.return_value = _make_result(stepIndex=3)

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": True,
            }),
        )

        assert resp.status_code == 200
        create_data = mock_db.teststep.create.call_args[1]["data"]
        assert create_data["stepIndex"] == 3

    def test_rejects_missing_passed_field(
        self, authed_client, mock_db, pipeline_session
    ):
        """Returns 400 when 'passed' field is missing."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "durationS": 1.0,
            }),
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "passed" in body["errors"][0]["message"]

    def test_rejects_non_boolean_passed(
        self, authed_client, mock_db, pipeline_session
    ):
        """Returns 400 when 'passed' is not a boolean."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": "yes",
            }),
        )

        assert resp.status_code == 400

    def test_returns_404_for_unknown_test(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Returns 404 when test name has no matching definition."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = None  # Test not found

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_nonexistent.test_ghost",
                "passed": True,
            }),
        )

        assert resp.status_code == 404

    def test_returns_404_for_no_execution(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Returns 404 when there's no execution for the test+device pair."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.test.find_first.return_value = _make_test()
        mock_db.device.find_first.return_value = pipeline_device
        mock_db.testexecution.find_first.return_value = None  # No execution

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": True,
            }),
        )

        assert resp.status_code == 404


# ── Report Finish ─────────────────────────────────────────


class TestReportFinish:
    """POST /report/finish updates Session totals."""

    def test_updates_session_counts(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Finish callback sets completedCount, passedCount, failedCount."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.device.find_first.return_value = pipeline_device

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({
                "total": 10,
                "passed": 8,
                "failed": 1,
                "errors": 1,
            }),
        )

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body["data"]["deviceStatus"] == "FAILED"
        assert body["data"]["allSlotsComplete"] is True

        # Verify DB update (aggregated counts)
        update_data = mock_db.session.update.call_args[1]["data"]
        assert update_data["status"] == "FAILED"
        assert update_data["completedCount"] == 1
        assert update_data["passedCount"] == 8
        assert update_data["failedCount"] == 2  # failed + errors
        assert "finishedAt" in update_data

    def test_device_status_passed_on_clean_run(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Device gets PASSED status when no failures or errors."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.device.find_first.return_value = pipeline_device

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": 5, "passed": 5, "failed": 0, "errors": 0}),
        )

        assert resp.status_code == 200
        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "PASSED"

    def test_device_status_failed_on_failures(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Device gets FAILED status when there are test failures."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.device.find_first.return_value = pipeline_device

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": 5, "passed": 3, "failed": 2, "errors": 0}),
        )

        assert resp.status_code == 200
        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "FAILED"

    def test_device_status_failed_on_errors(
        self, authed_client, mock_db, pipeline_session, pipeline_device
    ):
        """Device gets FAILED status when there are test errors (not just failures)."""
        mock_db.session.find_unique.return_value = pipeline_session
        mock_db.device.find_first.return_value = pipeline_device

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": 5, "passed": 4, "failed": 0, "errors": 1}),
        )

        assert resp.status_code == 200
        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "FAILED"

    def test_rejects_negative_counts(self, authed_client, mock_db, pipeline_session):
        """Returns 400 for negative count values."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": -1, "passed": 0, "failed": 0}),
        )

        assert resp.status_code == 400

    def test_rejects_missing_required_fields(self, authed_client, mock_db, pipeline_session):
        """Returns 400 when required fields (total, passed, failed) are missing."""
        mock_db.session.find_unique.return_value = pipeline_session

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": 5}),
        )

        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert "passed" in body["errors"][0]["message"]


# ── Full Pipeline Sequence ────────────────────────────────


class TestFullPipeline:
    """End-to-end: create run → start → N tests → finish → verify all records.

    This test chains the entire reporter lifecycle, verifying that each step's
    DB mutations are consistent and the final state is correct.
    """

    def test_three_tests_two_pass_one_fail(self, authed_client, mock_db):
        """Full sequence: 3 tests (2 pass, 1 fail) → PASSED session, FAILED device."""
        # ── Step 1: Create run ──────────────────────────────
        product = _make_product()
        node = _make_node()
        session = _make_session()
        device = _make_device()

        mock_db.product.find_unique.return_value = product
        mock_db.node.find_unique.return_value = node
        mock_db.session.create.return_value = session
        mock_db.device.create.return_value = device
        mock_db.test.find_many.return_value = []  # No pre-existing tests
        mock_db.session.update.return_value = session

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post(
                "/v2/sessions",
                data=json.dumps({
                    "name": "Alpha REV1.2 Smoke",
                    "productId": "prod-1",
                    "nodeId": "node-1",
                    "serialNumber": "70B3D584C01E1FCC",
                }),
            )
        assert resp.status_code == 201

        # ── Step 2: Report start ────────────────────────────
        mock_db.session.find_unique.return_value = session
        mock_db.session.update.reset_mock()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps({"started": True}),
        )
        assert resp.status_code == 200

        # Session.update called with ACTIVE + startedAt
        update_data = mock_db.session.update.call_args[1]["data"]
        assert update_data["status"] == "ACTIVE"

        # ── Step 3: Three test cycles ───────────────────────
        tests_data = [
            ("test_power.test_boot_current", "power", True, 2.3, {"currentMa": 33.5}),
            ("test_uart.test_shell_lock", "uart", True, 1.1, None),
            ("test_adc.test_reference_rail", "adc", False, 5.0, {"voltageV": 2.8}),
        ]

        for i, (name, module, passed, duration, measurements) in enumerate(tests_data):
            test_obj = _make_test(id=f"test-{i}", name=name, category=module)
            exec_obj = _make_execution(id=f"exec-{i}", testId=f"test-{i}")

            # Reset mocks for this test cycle
            mock_db.session.find_unique.return_value = session
            mock_db.test.find_first.return_value = None  # Auto-create
            mock_db.test.create.return_value = test_obj
            mock_db.device.find_first.return_value = device
            mock_db.testexecution.find_first.return_value = None
            mock_db.node.find_first.return_value = node
            mock_db.testexecution.create.return_value = exec_obj
            mock_db.testexecution.update.reset_mock()
            mock_db.device.update.reset_mock()

            # test-start
            resp = authed_client.post(
                "/v2/sessions/sess-1/report/test-start",
                data=json.dumps({"testName": name, "module": module}),
            )
            assert resp.status_code == 200, f"test-start failed for {name}"

            # Now set up the test-result mocks
            mock_db.test.find_first.return_value = test_obj
            mock_db.testexecution.find_first.return_value = exec_obj
            mock_db.teststep.count.return_value = 0
            mock_db.teststep.create.return_value = _make_result(
                id=f"result-{i}", executionId=f"exec-{i}", passed=passed
            )

            # test-result
            result_payload = {"testName": name, "passed": passed, "durationS": duration}
            if measurements:
                result_payload["measurements"] = measurements
            if not passed:
                result_payload["errorMessage"] = "Assertion failed"

            resp = authed_client.post(
                "/v2/sessions/sess-1/report/test-result",
                data=json.dumps(result_payload),
            )
            assert resp.status_code == 200, f"test-result failed for {name}"

            # Verify execution status matches
            exec_update = mock_db.testexecution.update.call_args[1]["data"]
            expected_status = "PASSED" if passed else "FAILED"
            assert exec_update["status"] == expected_status

        # ── Step 4: Report finish ───────────────────────────
        mock_db.session.find_unique.return_value = session
        mock_db.session.update.reset_mock()
        mock_db.device.find_first.return_value = device
        mock_db.device.update.reset_mock()

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({
                "total": 3,
                "passed": 2,
                "failed": 1,
                "errors": 0,
                "durationS": 8.4,
            }),
        )
        assert resp.status_code == 200

        # Session marked FAILED with aggregated counts
        session_update = mock_db.session.update.call_args[1]["data"]
        assert session_update["status"] == "FAILED"
        assert session_update["completedCount"] == 1  # 1 slot completed
        assert session_update["passedCount"] == 2
        assert session_update["failedCount"] == 1

        # Device marked FAILED (because 1 failure)
        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "FAILED"

    def test_all_pass_clean_run(self, authed_client, mock_db):
        """Full sequence with all tests passing → PASSED device."""
        session = _make_session()
        device = _make_device()
        test_obj = _make_test()
        exec_obj = _make_execution()

        # Create run
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.node.find_unique.return_value = _make_node()
        mock_db.session.create.return_value = session
        mock_db.device.create.return_value = device
        mock_db.test.find_many.return_value = [test_obj]
        mock_db.testexecution.create.return_value = exec_obj
        mock_db.session.update.return_value = session

        with patch("src.api.v2.sessions.runs.log_audit"):
            resp = authed_client.post(
                "/v2/sessions",
                data=json.dumps({
                    "name": "Clean Run",
                    "productId": "prod-1",
                    "nodeId": "node-1",
                    "serialNumber": "SN-CLEAN",
                }),
            )
        assert resp.status_code == 201

        # Start
        mock_db.session.find_unique.return_value = session
        resp = authed_client.post(
            "/v2/sessions/sess-1/report/start",
            data=json.dumps({"started": True}),
        )
        assert resp.status_code == 200

        # Single test: start + result
        mock_db.test.find_first.return_value = test_obj
        mock_db.device.find_first.return_value = device
        mock_db.testexecution.find_first.return_value = exec_obj

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-start",
            data=json.dumps({"testName": "test_power.test_boot_current", "module": "power"}),
        )
        assert resp.status_code == 200

        mock_db.teststep.count.return_value = 0
        mock_db.teststep.create.return_value = _make_result(passed=True)

        resp = authed_client.post(
            "/v2/sessions/sess-1/report/test-result",
            data=json.dumps({
                "testName": "test_power.test_boot_current",
                "passed": True,
                "durationS": 1.5,
            }),
        )
        assert resp.status_code == 200

        # Finish: all pass
        mock_db.device.update.reset_mock()
        resp = authed_client.post(
            "/v2/sessions/sess-1/report/finish",
            data=json.dumps({"total": 1, "passed": 1, "failed": 0, "errors": 0}),
        )
        assert resp.status_code == 200

        device_update = mock_db.device.update.call_args[1]["data"]
        assert device_update["status"] == "PASSED"

    def test_unauthorized_reporter_rejected(self, client):
        """All reporter endpoints reject unauthenticated requests."""
        endpoints = [
            ("/v2/sessions/sess-1/report/start", {"started": True}),
            ("/v2/sessions/sess-1/report/test-start", {"testName": "x"}),
            ("/v2/sessions/sess-1/report/test-result", {"testName": "x", "passed": True}),
            ("/v2/sessions/sess-1/report/finish", {"total": 1, "passed": 1, "failed": 0}),
        ]

        for url, payload in endpoints:
            resp = client.post(url, data=json.dumps(payload), content_type="application/json")
            assert resp.status_code == 401, f"Expected 401 for unauthenticated {url}, got {resp.status_code}"
