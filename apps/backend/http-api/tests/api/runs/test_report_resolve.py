"""Tests for reporter._resolve_target and the DB unique-constraint path.

Stream S4 of the test framework refactor simplified target resolution to a
single path: slotIndex (for multi-slot runs) OR the sole target (for
single-slot runs). Everything else is a 400 or 404 -- no silent fallback.

A companion DB constraint `@@unique([targetId, name])` on TestExecution
makes duplicate execution rows impossible; the reporter translates the
resulting UniqueViolationError into a 409 after a find-retry (races with
a sibling request).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from prisma.errors import UniqueViolationError


def _make_unique_violation(msg: str = "duplicate key") -> UniqueViolationError:
    """Build a UniqueViolationError with the dict shape the class expects."""
    return UniqueViolationError(
        {
            "user_facing_error": {
                "error_code": "P2002",
                "message": msg,
                "meta": {"target": ["targetId", "name"]},
            },
        }
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)


def _make_run(**overrides):
    defaults = dict(
        id="run-1",
        type="VALIDATION",
        status="ACTIVE",
        productId="prod-1",
        fixtureId=None,
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
        serialNumber="095F",
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


# ---------------------------------------------------------------------------
# Target resolution: multi-target runs
# ---------------------------------------------------------------------------

class TestResolveTargetMultiSlot:
    """Runs with more than one RunTarget require explicit slotIndex."""

    def test_slot_index_zero_resolves_via_compound_key(self, authed_client, mock_db):
        """slotIndex=0 (falsy-looking but valid) must resolve the slot-0 target."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=2)
        # The handler resolves via find_unique(runId_slotIndex=...)
        mock_db.runtarget.find_unique.return_value = _make_target(
            id="target-slot0", slotIndex=0,
        )
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution(
            targetId="target-slot0",
        )

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({
                    "testName": "test_boot",
                    "slotIndex": 0,
                }),
            )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["targetId"] == "target-slot0"
        # Confirm we hit the compound-key lookup, not the fallback
        call = mock_db.runtarget.find_unique.call_args.kwargs
        assert call["where"] == {"runId_slotIndex": {"runId": "run-1", "slotIndex": 0}}

    def test_slot_index_not_found_returns_404(self, authed_client, mock_db):
        """slotIndex=5 missing from run → 404 naming both run and slot."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=2)
        mock_db.runtarget.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({
                "testName": "test_boot",
                "slotIndex": 5,
            }),
        )

        assert resp.status_code == 404
        msg = resp.get_json()["errors"][0]["message"]
        assert "5" in msg
        assert "run-1" in msg

    def test_no_slot_index_with_multi_target_returns_400(self, authed_client, mock_db):
        """Multi-target run without slotIndex in payload → 400, no silent fallback."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=2)
        # Handler only consults find_unique() when slotIndex is present,
        # so it falls through to count() for multi-target detection.
        mock_db.runtarget.count.return_value = 2

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({"testName": "test_boot"}),
        )

        assert resp.status_code == 400
        msg = resp.get_json()["errors"][0]["message"]
        assert "slotIndex required" in msg

    def test_device_serial_without_slot_index_returns_400(self, authed_client, mock_db):
        """deviceSerial fallback is REMOVED -- slotIndex is mandatory for multi-target.

        Even though the old code accepted deviceSerial, the new contract is
        slotIndex-only. A payload with deviceSerial but no slotIndex on a
        multi-target run must 400.
        """
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=2)
        mock_db.runtarget.count.return_value = 2
        # Even if a target with this serial exists, we must NOT resolve it
        mock_db.runtarget.find_first.return_value = _make_target(serialNumber="095F")

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({
                "testName": "test_boot",
                "deviceSerial": "095F",
            }),
        )

        assert resp.status_code == 400
        msg = resp.get_json()["errors"][0]["message"]
        assert "slotIndex required" in msg

    def test_target_id_in_payload_is_ignored(self, authed_client, mock_db):
        """`targetId` payload key is not honored -- only slotIndex matters.

        Decision: the old `targetId` escape hatch is removed in S4. The
        reporter never sent it in practice, and allowing it weakens the
        single-path contract. Multi-target run + no slotIndex → 400
        regardless of any targetId the caller supplies.
        """
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=2)
        mock_db.runtarget.count.return_value = 2
        # Should NOT be consulted by ID lookup in the new code path
        mock_db.runtarget.find_unique.return_value = _make_target(id="target-7")

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({
                "testName": "test_boot",
                "targetId": "target-7",
            }),
        )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Target resolution: single-target runs
# ---------------------------------------------------------------------------

class TestResolveTargetSingleSlot:
    """Single-target runs resolve cleanly with or without slotIndex."""

    def test_no_slot_index_resolves_sole_target(self, authed_client, mock_db):
        """targetCount=1, no attribution keys → sole target returned."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=1)
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({"testName": "test_boot"}),
            )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["targetId"] == "target-1"

    def test_slot_index_zero_resolves_when_matching(self, authed_client, mock_db):
        """Single-slot run + slotIndex=0 that matches → resolves."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=1)
        mock_db.runtarget.find_unique.return_value = _make_target(slotIndex=0)
        mock_db.testexecution.find_first.return_value = None
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.return_value = _make_execution()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({
                    "testName": "test_boot",
                    "slotIndex": 0,
                }),
            )

        assert resp.status_code == 200

    def test_slot_index_mismatch_returns_404(self, authed_client, mock_db):
        """Single-slot run + slotIndex=5 → 404. Explicit slot still must exist."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=1)
        mock_db.runtarget.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({
                "testName": "test_boot",
                "slotIndex": 5,
            }),
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Target resolution: zero-target edge case
# ---------------------------------------------------------------------------

class TestResolveTargetZeroTargets:
    """Runs with zero RunTargets should never happen, but if they do → 404."""

    def test_zero_targets_returns_404(self, authed_client, mock_db):
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=0)
        mock_db.runtarget.count.return_value = 0
        mock_db.runtarget.find_first.return_value = None

        resp = authed_client.post(
            "/v2/runs/run-1/report/execution-start",
            data=json.dumps({"testName": "test_boot"}),
        )

        assert resp.status_code == 404
        msg = resp.get_json()["errors"][0]["message"]
        assert "run-1" in msg


# ---------------------------------------------------------------------------
# DB unique constraint: duplicate TestExecution row
# ---------------------------------------------------------------------------

class TestExecutionUniqueConstraint:
    """The DB enforces `@@unique([targetId, name])` on TestExecution.

    A race between two concurrent report/execution-start handlers can
    cause the `create` to fail with UniqueViolationError. The handler
    retries via find_first and either returns the winner's row or 409s.
    """

    def test_unique_violation_race_retry_succeeds(self, authed_client, mock_db):
        """create() races and loses → retry find_first → return winner's row."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=1)
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()

        # First find_first (pre-create): no existing execution.
        # Second find_first (post-UniqueViolation retry): sibling's row.
        winner = _make_execution(id="exec-winner")
        mock_db.testexecution.find_first.side_effect = [None, winner]
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.side_effect = _make_unique_violation(
            "duplicate key value violates unique constraint "
            "\"test_executions_targetId_name_key\""
        )

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({"testName": "test_boot_sequence"}),
            )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["executionId"] == "exec-winner"

    def test_unique_violation_retry_empty_returns_409(self, authed_client, mock_db):
        """create() fails and retry still returns nothing → 409 (true conflict)."""
        mock_db.testrun.find_unique.return_value = _make_run(targetCount=1)
        mock_db.runtarget.count.return_value = 1
        mock_db.runtarget.find_first.return_value = _make_target()

        # Both lookups return None; only the create raises.
        mock_db.testexecution.find_first.side_effect = [None, None]
        mock_db.testexecution.count.return_value = 0
        mock_db.testexecution.create.side_effect = _make_unique_violation()

        with patch("api.v2.runs.reporter._emit"):
            resp = authed_client.post(
                "/v2/runs/run-1/report/execution-start",
                data=json.dumps({"testName": "test_boot_sequence"}),
            )

        assert resp.status_code == 409
