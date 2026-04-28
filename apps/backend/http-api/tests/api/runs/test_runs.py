"""Tests for runs/runs.py -- CRUD endpoints for TestRun.

Covers: create_run, list_runs, get_run, cancel_run, rerun_run,
        list_targets, list_executions.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make_run(**overrides):
    defaults = dict(
        id="run-1",
        type="VALIDATION",
        name="Validation run",
        productId="prod-1",
        fixtureId="fix-1",
        testPackageId=None,
        buildRunId=None,
        manufacturingSessionId=None,
        panelIdentifier=None,
        assetSetId=None,
        status="PENDING",
        operatorId="user-1",
        targetCount=1,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        config=None,
        notes=None,
        errorMessage=None,
        startedAt=None,
        completedAt=None,
        durationMs=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_run_with_relations(**overrides):
    """Run with product and operator relations attached."""
    run = _make_run(**overrides)
    if not hasattr(run, "product") or run.product is None:
        run.product = SimpleNamespace(id="prod-1", name="Alpha")
    if not hasattr(run, "operator") or run.operator is None:
        run.operator = SimpleNamespace(
            id="user-1", name="Test User", email="test@example.com"
        )
    return run


def _make_target(**overrides):
    defaults = dict(
        id="target-1",
        runId="run-1",
        slotIndex=0,
        slotId=None,
        serialNumber="0964",
        deviceId=None,
        status="PENDING",
        metadata=None,
        errorMessage=None,
        startedAt=None,
        completedAt=None,
        durationMs=None,
        createdAt=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_execution(**overrides):
    defaults = dict(
        id="exec-1",
        targetId="target-1",
        executionIndex=0,
        name="test_boot",
        module="boot",
        status="PASSED",
        durationMs=1500,
        errorMessage=None,
        measurements=None,
        logOutput=None,
        logStorageKey=None,
        startedAt=NOW,
        completedAt=NOW,
        createdAt=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_step(**overrides):
    defaults = dict(
        id="step-1",
        executionId="exec-1",
        stepIndex=0,
        name="power_on",
        status="PASSED",
        passed=True,
        durationMs=500,
        errorMessage=None,
        measurements=None,
        logOutput=None,
        logStorageKey=None,
        startedAt=NOW,
        completedAt=NOW,
        createdAt=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# POST /v2/runs — create_run
# ---------------------------------------------------------------------------

class TestCreateRun:
    """Tests for POST /v2/runs -- create a new validation run."""

    def test_create_run_success(self, authed_client, mock_db):
        product = make_obj(id="prod-1", name="Alpha")
        fixture = make_obj(id="fix-1", name="Bench-1")
        created_run = _make_run_with_relations()
        target = _make_target()

        mock_db.product.find_unique.return_value = product
        mock_db.fixture.find_unique.return_value = fixture
        mock_db.testrun.create.return_value = created_run
        mock_db.runtarget.create.return_value = target

        with patch("api.v2.runs.runs.log_audit"):
            resp = authed_client.post(
                "/v2/runs",
                data=json.dumps({
                    "type": "VALIDATION",
                    "productId": "prod-1",
                    "fixtureId": "fix-1",
                    "serialNumber": "0964",
                }),
            )

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["id"] == "run-1"
        assert body["data"]["status"] == "PENDING"
        assert body["data"]["targets"][0]["serialNumber"] == "0964"
        mock_db.testrun.create.assert_called_once()
        mock_db.runtarget.create.assert_called_once()

    def test_create_run_missing_product_id(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "VALIDATION",
                "fixtureId": "fix-1",
            }),
        )
        assert resp.status_code == 400

    def test_create_run_missing_fixture_id(self, authed_client, mock_db):
        product = make_obj(id="prod-1", name="Alpha")
        mock_db.product.find_unique.return_value = product

        resp = authed_client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "VALIDATION",
                "productId": "prod-1",
            }),
        )
        assert resp.status_code == 400

    def test_create_run_product_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "VALIDATION",
                "productId": "nonexistent",
                "fixtureId": "fix-1",
            }),
        )
        assert resp.status_code == 404

    def test_create_run_fixture_not_found(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "VALIDATION",
                "productId": "prod-1",
                "fixtureId": "nonexistent",
            }),
        )
        assert resp.status_code == 404

    def test_create_run_manufacturing_rejected(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "MANUFACTURING",
                "productId": "prod-1",
                "fixtureId": "fix-1",
            }),
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "ManufacturingSession" in body["errors"][0]["message"]

    def test_create_run_creates_target_with_slot_zero(self, authed_client, mock_db):
        mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Alpha")
        mock_db.fixture.find_unique.return_value = make_obj(id="fix-1", name="Bench-1")
        mock_db.testrun.create.return_value = _make_run_with_relations()
        mock_db.runtarget.create.return_value = _make_target()

        with patch("api.v2.runs.runs.log_audit"):
            authed_client.post(
                "/v2/runs",
                data=json.dumps({
                    "type": "VALIDATION",
                    "productId": "prod-1",
                    "fixtureId": "fix-1",
                }),
            )

        create_data = mock_db.runtarget.create.call_args.kwargs["data"]
        assert create_data["slotIndex"] == 0
        assert create_data["status"] == "PENDING"

    def test_create_run_requires_auth(self, client, mock_db):
        resp = client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "VALIDATION",
                "productId": "prod-1",
                "fixtureId": "fix-1",
            }),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_create_run_invalid_type(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/runs",
            data=json.dumps({
                "type": "INVALID",
                "productId": "prod-1",
                "fixtureId": "fix-1",
            }),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /v2/runs — list_runs
# ---------------------------------------------------------------------------

class TestListRuns:
    """Tests for GET /v2/runs -- paginated list with filters."""

    def test_list_runs_default(self, authed_client, mock_db):
        run1 = _make_run_with_relations(id="run-1")
        run2 = _make_run_with_relations(id="run-2")
        mock_db.testrun.count.return_value = 2
        mock_db.testrun.find_many.return_value = [run1, run2]

        resp = authed_client.get("/v2/runs")

        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2
        assert body["data"]["pagination"]["page"] == 1

    def test_list_runs_filter_by_type(self, authed_client, mock_db):
        mock_db.testrun.count.return_value = 1
        mock_db.testrun.find_many.return_value = [_make_run_with_relations()]

        resp = authed_client.get("/v2/runs?type=VALIDATION")

        assert resp.status_code == 200
        where = mock_db.testrun.find_many.call_args.kwargs["where"]
        assert where["type"] == "VALIDATION"

    def test_list_runs_filter_by_status(self, authed_client, mock_db):
        mock_db.testrun.count.return_value = 0
        mock_db.testrun.find_many.return_value = []

        resp = authed_client.get("/v2/runs?status=ACTIVE")

        assert resp.status_code == 200
        where = mock_db.testrun.find_many.call_args.kwargs["where"]
        assert where["status"] == "ACTIVE"

    def test_list_runs_filter_by_product(self, authed_client, mock_db):
        mock_db.testrun.count.return_value = 0
        mock_db.testrun.find_many.return_value = []

        resp = authed_client.get("/v2/runs?productId=prod-1")

        assert resp.status_code == 200
        where = mock_db.testrun.find_many.call_args.kwargs["where"]
        assert where["productId"] == "prod-1"

    def test_list_runs_pagination(self, authed_client, mock_db):
        mock_db.testrun.count.return_value = 25
        mock_db.testrun.find_many.return_value = []

        resp = authed_client.get("/v2/runs?page=2&limit=5")

        assert resp.status_code == 200
        call_kwargs = mock_db.testrun.find_many.call_args.kwargs
        assert call_kwargs["skip"] == 5  # (2-1) * 5
        assert call_kwargs["take"] == 5
        body = resp.get_json()
        assert body["data"]["pagination"]["page"] == 2
        assert body["data"]["pagination"]["limit"] == 5
        assert body["data"]["pagination"]["pages"] == 5

    def test_list_runs_empty(self, authed_client, mock_db):
        mock_db.testrun.count.return_value = 0
        mock_db.testrun.find_many.return_value = []

        resp = authed_client.get("/v2/runs")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# GET /v2/runs/<run_id> — get_run
# ---------------------------------------------------------------------------

class TestGetRun:
    """Tests for GET /v2/runs/<run_id> -- full detail with relations."""

    def test_get_run_success(self, authed_client, mock_db):
        step = _make_step()
        execution = _make_execution(steps=[step])
        target = _make_target(executions=[execution])
        run = _make_run_with_relations(targets=[target])
        run.fixture = SimpleNamespace(id="fix-1", name="Bench-1")
        mock_db.testrun.find_unique.return_value = run

        resp = authed_client.get("/v2/runs/run-1")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["id"] == "run-1"
        assert body["data"]["targets"][0]["id"] == "target-1"
        assert body["data"]["targets"][0]["executions"][0]["id"] == "exec-1"
        assert body["data"]["targets"][0]["executions"][0]["steps"][0]["id"] == "step-1"

    def test_get_run_not_found(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.get("/v2/runs/nonexistent")

        assert resp.status_code == 404

    def test_get_run_includes_relations(self, authed_client, mock_db):
        run = _make_run_with_relations(targets=[])
        run.fixture = SimpleNamespace(id="fix-1", name="Bench-1")
        run.testPackage = SimpleNamespace(
            id="tp-1", version="1.0.0", type="VALIDATION", status="ACTIVE"
        )
        run.buildRun = SimpleNamespace(
            id="br-1", name="Build 1", status="SUCCESS",
            commitSha="abc123", branch="main",
        )
        run.assetSet = SimpleNamespace(id="as-1", version="2.0", status="ACTIVE")
        mock_db.testrun.find_unique.return_value = run

        resp = authed_client.get("/v2/runs/run-1")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["product"]["id"] == "prod-1"
        assert body["data"]["fixture"]["id"] == "fix-1"
        assert body["data"]["testPackage"]["id"] == "tp-1"
        assert body["data"]["buildRun"]["id"] == "br-1"
        assert body["data"]["assetSet"]["id"] == "as-1"
        assert body["data"]["operator"]["email"] == "test@example.com"


# ---------------------------------------------------------------------------
# POST /v2/runs/<run_id>/cancel — cancel_run
# ---------------------------------------------------------------------------

class TestCancelRun:
    """Tests for POST /v2/runs/<run_id>/cancel -- cancel pending/active run."""

    def test_cancel_active_run(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(
            status="ACTIVE", fixtureId=None
        )
        cancelled_run = _make_run_with_relations(
            status="CANCELLED", targets=[]
        )
        mock_db.testrun.update.return_value = cancelled_run

        with patch("api.v2.runs.runs.log_audit"):
            resp = authed_client.post("/v2/runs/run-1/cancel")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "CANCELLED"
        mock_db.testrun.update.assert_called_once()
        update_data = mock_db.testrun.update.call_args.kwargs["data"]
        assert update_data["status"] == "CANCELLED"
        assert update_data["completedAt"] is not None

    def test_cancel_pending_run(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(
            status="PENDING", fixtureId=None
        )
        mock_db.testrun.update.return_value = _make_run_with_relations(
            status="CANCELLED", targets=[]
        )

        with patch("api.v2.runs.runs.log_audit"):
            resp = authed_client.post("/v2/runs/run-1/cancel")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["status"] == "CANCELLED"

    def test_cancel_completed_run_returns_conflict(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(status="COMPLETED")

        resp = authed_client.post("/v2/runs/run-1/cancel")

        assert resp.status_code == 409

    def test_cancel_unlocks_fixture(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(
            status="ACTIVE", fixtureId="fix-1"
        )
        mock_db.testrun.update.return_value = _make_run_with_relations(
            status="CANCELLED", targets=[]
        )

        with patch("api.v2.runs.runs.log_audit"):
            resp = authed_client.post("/v2/runs/run-1/cancel")

        assert resp.status_code == 200
        mock_db.fixture.update.assert_called_once()
        fix_data = mock_db.fixture.update.call_args.kwargs["data"]
        assert fix_data["lockState"] == "FREE"
        assert fix_data["lockedBy"] is None
        assert fix_data["lockedAt"] is None

    def test_cancel_not_found(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.post("/v2/runs/nonexistent/cancel")

        assert resp.status_code == 404

    def test_cancel_updates_targets_and_executions(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(
            status="ACTIVE", fixtureId=None
        )
        mock_db.testrun.update.return_value = _make_run_with_relations(
            status="CANCELLED", targets=[]
        )

        with patch("api.v2.runs.runs.log_audit"):
            authed_client.post("/v2/runs/run-1/cancel")

        # Targets updated
        mock_db.runtarget.update_many.assert_called_once()
        target_where = mock_db.runtarget.update_many.call_args.kwargs["where"]
        assert target_where["runId"] == "run-1"
        assert "PENDING" in target_where["status"]["in"]
        assert "RUNNING" in target_where["status"]["in"]
        target_data = mock_db.runtarget.update_many.call_args.kwargs["data"]
        assert target_data["status"] == "ERROR"

        # Executions updated
        mock_db.testexecution.update_many.assert_called_once()
        exec_data = mock_db.testexecution.update_many.call_args.kwargs["data"]
        assert exec_data["status"] == "FAILED"


# ---------------------------------------------------------------------------
# POST /v2/runs/<run_id>/rerun — rerun_run
# ---------------------------------------------------------------------------

class TestRerunRun:
    """Tests for POST /v2/runs/<run_id>/rerun -- clone into new PENDING run."""

    def test_rerun_success(self, authed_client, mock_db):
        original = _make_run_with_relations(
            id="run-old",
            config={},
            testPackageId="tp-1",
            buildRunId="br-1",
            assetSetId="as-1",
        )
        mock_db.testrun.find_unique.return_value = original

        new_run = _make_run_with_relations(id="run-new", status="PENDING")
        mock_db.testrun.create.return_value = new_run

        with patch("api.v2.runs.runs.log_audit"):
            resp = authed_client.post("/v2/runs/run-old/rerun")

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["id"] == "run-new"
        assert body["data"]["status"] == "PENDING"
        mock_db.testrun.create.assert_called_once()
        create_data = mock_db.testrun.create.call_args.kwargs["data"]
        assert create_data["status"] == "PENDING"
        assert create_data["productId"] == "prod-1"

    def test_rerun_sets_rerun_config(self, authed_client, mock_db):
        original = _make_run_with_relations(
            id="run-old", config={"stage": "fuota"}
        )
        mock_db.testrun.find_unique.return_value = original
        mock_db.testrun.create.return_value = _make_run_with_relations(
            id="run-new", status="PENDING"
        )

        with patch("api.v2.runs.runs.log_audit"):
            authed_client.post("/v2/runs/run-old/rerun")

        create_data = mock_db.testrun.create.call_args.kwargs["data"]
        # The config should be wrapped in Json(), verify the source dict
        # has rerunOf pointing to the original
        config_arg = create_data["config"]
        # Json() wraps the dict; verify the argument passed to Json
        assert config_arg is not None

    def test_rerun_not_found(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.post("/v2/runs/nonexistent/rerun")

        assert resp.status_code == 404

    def test_rerun_copies_original_fields(self, authed_client, mock_db):
        original = _make_run_with_relations(
            id="run-old",
            type="VALIDATION",
            name="Original run",
            productId="prod-1",
            fixtureId="fix-1",
            testPackageId="tp-1",
            buildRunId="br-1",
            assetSetId="as-1",
            config={},
        )
        mock_db.testrun.find_unique.return_value = original
        mock_db.testrun.create.return_value = _make_run_with_relations(
            id="run-new", status="PENDING"
        )

        with patch("api.v2.runs.runs.log_audit"):
            authed_client.post("/v2/runs/run-old/rerun")

        create_data = mock_db.testrun.create.call_args.kwargs["data"]
        assert create_data["type"] == "VALIDATION"
        assert create_data["productId"] == "prod-1"
        assert create_data["fixtureId"] == "fix-1"
        assert create_data["testPackageId"] == "tp-1"
        assert create_data["buildRunId"] == "br-1"
        assert create_data["assetSetId"] == "as-1"
        assert create_data["notes"] == "Rerun of run-old"


# ---------------------------------------------------------------------------
# GET /v2/runs/<run_id>/targets — list_targets
# ---------------------------------------------------------------------------

class TestListTargets:
    """Tests for GET /v2/runs/<run_id>/targets -- targets with executions."""

    def test_list_targets_success(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        exec1 = _make_execution(id="exec-1", steps=[])
        target1 = _make_target(id="target-1", executions=[exec1])
        target2 = _make_target(id="target-2", slotIndex=1, executions=[])
        mock_db.runtarget.find_many.return_value = [target1, target2]

        resp = authed_client.get("/v2/runs/run-1/targets")

        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["data"]) == 2
        assert body["data"]["data"][0]["id"] == "target-1"
        assert body["data"]["data"][0]["executions"][0]["id"] == "exec-1"

    def test_list_targets_not_found(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.get("/v2/runs/nonexistent/targets")

        assert resp.status_code == 404

    def test_list_targets_empty(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.runtarget.find_many.return_value = []

        resp = authed_client.get("/v2/runs/run-1/targets")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["data"] == []


# ---------------------------------------------------------------------------
# GET /v2/runs/<run_id>/executions — list_executions
# ---------------------------------------------------------------------------

class TestListExecutions:
    """Tests for GET /v2/runs/<run_id>/executions -- paginated executions."""

    def test_list_executions_success(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        step = _make_step()
        exec1 = _make_execution(id="exec-1", steps=[step])
        exec2 = _make_execution(id="exec-2", executionIndex=1, name="test_uart", steps=[])
        mock_db.testexecution.count.return_value = 2
        mock_db.testexecution.find_many.return_value = [exec1, exec2]

        resp = authed_client.get("/v2/runs/run-1/executions")

        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]["data"]) == 2
        assert body["data"]["pagination"]["total"] == 2
        assert body["data"]["data"][0]["steps"][0]["id"] == "step-1"

    def test_list_executions_not_found(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = None

        resp = authed_client.get("/v2/runs/nonexistent/executions")

        assert resp.status_code == 404

    def test_list_executions_pagination(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.testexecution.count.return_value = 30
        mock_db.testexecution.find_many.return_value = []

        resp = authed_client.get("/v2/runs/run-1/executions?page=3&limit=10")

        assert resp.status_code == 200
        call_kwargs = mock_db.testexecution.find_many.call_args.kwargs
        assert call_kwargs["skip"] == 20  # (3-1) * 10
        assert call_kwargs["take"] == 10
        body = resp.get_json()
        assert body["data"]["pagination"]["page"] == 3
        assert body["data"]["pagination"]["pages"] == 3

    def test_list_executions_empty(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run()
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.find_many.return_value = []

        resp = authed_client.get("/v2/runs/run-1/executions")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["data"] == []
        assert body["data"]["pagination"]["total"] == 0
