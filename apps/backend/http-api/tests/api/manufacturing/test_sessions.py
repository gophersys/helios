"""Tests for manufacturing sessions — /v2/manufacturing/sessions."""

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


def _product(**overrides):
    defaults = dict(id="s10-prod-1", name="s10-Alpha B0", slug="s10-alpha-b0")
    defaults.update(overrides)
    return make_obj(**defaults)


def _asset_set(**overrides):
    """AssetSet mock for manufacturing tests.

    Sessions now require a resolvable firmware AssetSet; the helper
    lets individual tests customize ``status`` / ``boardRevisionId`` /
    ``productId`` when they need to exercise the validation branches.
    """
    defaults = dict(
        id="s10-as-1",
        productId="s10-prod-1",
        boardRevisionId="s10-rev-1",
        status="COMPLETE",
        version="0.1.0",
        variant="debug",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _fixture(**overrides):
    defaults = dict(
        id="s10-fix-1",
        name="s10-MFG Fixture 1",
        productId="s10-prod-1",
        boardRevisionId="s10-rev-1",
        type="MANUFACTURING",
        status="AVAILABLE",
        lockedBy=None,
        lockedAt=None,
        active=True,
        panelRows=2,
        panelCols=2,
        metadata=None,
        product=_product(),
        # ``slots`` is re-fetched during session create (with node relations
        # for MTIB resolution). Default to empty so tests don't have to mock
        # slot/node trees unless they're exercising the snapshot path.
        slots=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _session(**overrides):
    defaults = dict(
        id="s10-sess-1",
        productId="s10-prod-1",
        fixtureId="s10-fix-1",
        status="ACTIVE",
        operatorId="test-user-id",
        assetSetId=None,
        assetSet=None,
        config=None,
        notes=None,
        startedAt=_now(),
        endedAt=None,
        createdAt=_now(),
        updatedAt=_now(),
        product=_product(),
        fixture=_fixture(),
        operator=make_obj(id="test-user-id", name="Test User", email="test@example.com"),
        runs=[],
        runCount=0,
        passedCount=0,
        failedCount=0,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _slot(**overrides):
    defaults = dict(
        id="s10-slot-0",
        fixtureId="s10-fix-1",
        slotIndex=0,
        name="Slot 1",
        active=True,
        dutSnr=None,
        dutDeviceId=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _run(**overrides):
    defaults = dict(
        id="s10-run-1",
        type="MANUFACTURING",
        name="MFG Run 1",
        productId="s10-prod-1",
        fixtureId="s10-fix-1",
        testPackageId=None,
        manufacturingSessionId="s10-sess-1",
        panelIdentifier="s10-QR-001",
        assetSetId=None,
        boardRevisionId=None,
        status="PENDING",
        operatorId="test-user-id",
        targetCount=4,
        completedCount=0,
        passedCount=0,
        failedCount=0,
        durationMs=None,
        config=None,
        notes=None,
        errorMessage=None,
        startedAt=_now(),
        completedAt=None,
        createdAt=_now(),
        updatedAt=_now(),
        targets=[],
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_audit():
    with patch("api.v2.manufacturing.sessions.log_audit"):
        yield


@pytest.fixture(autouse=True)
def _mock_socketio():
    with patch("api.v2.manufacturing.sessions._socketio", new=MagicMock()):
        yield


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/fixtures — list manufacturing fixtures
# ---------------------------------------------------------------------------

class TestListFixtures:
    def test_returns_manufacturing_fixtures(self, authed_client, mock_db):
        mock_db.fixture.find_many.return_value = [_fixture()]
        mock_db.fixture.count.return_value = 1

        resp = authed_client.get("/v2/manufacturing/fixtures")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["type"] == "MANUFACTURING"

    def test_returns_empty_list(self, authed_client, mock_db):
        mock_db.fixture.find_many.return_value = []
        mock_db.fixture.count.return_value = 0

        resp = authed_client.get("/v2/manufacturing/fixtures")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions — create session (locks fixture)
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_creates_session_and_locks_fixture(self, authed_client, mock_db):
        mock_db.fixture.find_unique.return_value = _fixture()
        mock_db.product.find_unique.return_value = _product()
        # Manufacturing sessions require a firmware asset set. The auto-
        # resolve now falls back to the latest COMPLETE AssetSet for the
        # (product, board) pair — mock that so the happy-path test
        # doesn't hit the hard 400 gate we added to prevent sessions
        # from spawning with assetSetId=None.
        mock_db.assetset.find_first.return_value = _asset_set(id="s10-as-1", status="COMPLETE")
        created = _session()
        mock_db.manufacturingsession.create.return_value = created
        mock_db.fixture.update.return_value = _fixture(status="LOCKED", lockedBy="s10-sess-1")

        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({
                "productId": "s10-prod-1",
                "fixtureId": "s10-fix-1",
            }),
        )
        assert resp.status_code == 201

    def test_returns_409_if_fixture_locked(self, authed_client, mock_db):
        mock_db.fixture.find_unique.return_value = _fixture(status="LOCKED", lockedBy="other-sess")

        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({
                "productId": "s10-prod-1",
                "fixtureId": "s10-fix-1",
            }),
        )
        assert resp.status_code == 409

    def test_returns_404_if_fixture_missing(self, authed_client, mock_db):
        mock_db.fixture.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({
                "productId": "s10-prod-1",
                "fixtureId": "s10-missing",
            }),
        )
        assert resp.status_code == 404

    def test_returns_400_missing_fields(self, authed_client, mock_db):
        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions — list sessions (paginated)
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_returns_paginated_sessions(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_many.return_value = [_session()]
        mock_db.manufacturingsession.count.return_value = 1

        resp = authed_client.get("/v2/manufacturing/sessions")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 1
        assert body["pagination"]["total"] == 1

    def test_pagination_params(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_many.return_value = []
        mock_db.manufacturingsession.count.return_value = 0

        resp = authed_client.get("/v2/manufacturing/sessions?page=2&limit=10")
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["page"] == 2


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions/<id> — get session detail
# ---------------------------------------------------------------------------

class TestGetSession:
    def test_returns_session_with_runs(self, authed_client, mock_db):
        sess = _session(runs=[_run()])
        mock_db.manufacturingsession.find_unique.return_value = sess

        resp = authed_client.get("/v2/manufacturing/sessions/s10-sess-1")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["id"] == "s10-sess-1"

    def test_returns_404(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = None

        resp = authed_client.get("/v2/manufacturing/sessions/s10-missing")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/runs — add run (QR scan)
# ---------------------------------------------------------------------------

class TestAddRun:
    def test_adds_run_to_session(self, authed_client, mock_db):
        fixture_with_slots = _fixture(slots=[])
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture_with_slots)
        created = _run()
        mock_db.testrun.create.return_value = created
        mock_db.testrun.find_unique.return_value = created

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({"qrCode": "s10-QR-001"}),
        )
        assert resp.status_code == 201

    def test_returns_404_if_session_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-missing/runs",
            data=json.dumps({"qrCode": "s10-QR-001"}),
        )
        assert resp.status_code == 404

    def test_returns_400_if_session_not_active(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session(status="COMPLETED")

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({"qrCode": "s10-QR-001"}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/end — end session (release fixture)
# ---------------------------------------------------------------------------

class TestEndSession:
    def test_ends_session_and_releases_fixture(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingsession.update.return_value = _session(status="COMPLETED")
        mock_db.fixture.update.return_value = _fixture(status="AVAILABLE", lockedBy=None)

        resp = authed_client.post("/v2/manufacturing/sessions/s10-sess-1/end")
        assert resp.status_code == 200

    def test_returns_404_if_session_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = None

        resp = authed_client.post("/v2/manufacturing/sessions/s10-missing/end")
        assert resp.status_code == 404

    def test_returns_400_if_already_ended(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session(status="COMPLETED")

        resp = authed_client.post("/v2/manufacturing/sessions/s10-sess-1/end")
        assert resp.status_code == 400

    def test_reconciles_orphan_active_runs_to_cancelled(self, authed_client, mock_db):
        """End-session is the authoritative "no more /report/* for this session".

        Any TestRun still ACTIVE at this point won't get a /report/finish
        — the runner pod is about to be torn down. Mark those runs
        CANCELLED and their targets ERROR so dashboards and
        wait_for_run callers don't spin forever.
        """
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingsession.update.return_value = _session(status="COMPLETED")
        mock_db.fixture.update.return_value = _fixture(status="AVAILABLE", lockedBy=None)

        # Two update_many calls are expected: PENDING→FAILED, ACTIVE→CANCELLED.
        # The second return value exercises the "reconciled > 0" branch that
        # also flips lingering RunTargets.
        mock_db.testrun.update_many.return_value = 2  # two ACTIVE runs reconciled

        resp = authed_client.post("/v2/manufacturing/sessions/s10-sess-1/end")
        assert resp.status_code == 200

        # PENDING cleanup + ACTIVE reconcile + RunTarget cleanup = 3 update_many calls
        assert mock_db.testrun.update_many.call_count >= 2
        # Find the ACTIVE-reconcile call by its where clause
        active_calls = [
            c for c in mock_db.testrun.update_many.call_args_list
            if c.kwargs.get("where", {}).get("status") == "ACTIVE"
        ]
        assert len(active_calls) == 1
        data = active_calls[0].kwargs["data"]
        assert data["status"] == "CANCELLED"
        assert "Reconciled by end_session" in data["errorMessage"]
        # RunTarget cleanup must also have fired since reconciled > 0
        assert mock_db.runtarget.update_many.call_count >= 1
        rt_data = mock_db.runtarget.update_many.call_args_list[-1].kwargs["data"]
        assert rt_data["status"] == "ERROR"

    def test_skips_runtarget_cleanup_when_no_orphans(self, authed_client, mock_db):
        """If every run already hit /report/finish, don't touch run targets."""
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingsession.update.return_value = _session(status="COMPLETED")
        mock_db.fixture.update.return_value = _fixture(status="AVAILABLE", lockedBy=None)
        mock_db.testrun.update_many.return_value = 0  # no orphans

        resp = authed_client.post("/v2/manufacturing/sessions/s10-sess-1/end")
        assert resp.status_code == 200

        # PENDING cleanup (return=0) + ACTIVE cleanup (return=0) — still 2
        # testrun.update_many calls, but NO runtarget.update_many because
        # the reconcile is guarded behind reconciled > 0.
        assert mock_db.runtarget.update_many.call_count == 0


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions/<id>/results — get session results
# ---------------------------------------------------------------------------

class TestGetResults:
    def test_returns_results(self, authed_client, mock_db):
        run = _run(
            targetCount=1,
            passedCount=1,
            failedCount=0,
            targets=[
                make_obj(
                    id="s10-target-1", runId="s10-run-1", slotIndex=0,
                    slotId="slot-0", serialNumber="SN001", deviceId=None,
                    status="PASSED", metadata=None, errorMessage=None,
                    durationMs=1000, executions=[],
                    startedAt=_now(), completedAt=_now(),
                )
            ]
        )
        sess = _session(runs=[run])
        mock_db.manufacturingsession.find_unique.return_value = sess

        resp = authed_client.get("/v2/manufacturing/sessions/s10-sess-1/results")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["runs"]) == 1


# ---------------------------------------------------------------------------
# _derive_panel_snrs — unit tests for SNR derivation logic
# ---------------------------------------------------------------------------

class TestDerivePanelSnrs:
    def test_numeric_snr(self):
        from api.v2.manufacturing.sessions import _derive_panel_snrs
        result = _derive_panel_snrs("0964", 4)
        assert len(result) == 4
        assert result[0] == {"slotIndex": 0, "snr": "0964"}
        assert result[1] == {"slotIndex": 1, "snr": "0965"}
        assert result[2] == {"slotIndex": 2, "snr": "0966"}
        assert result[3] == {"slotIndex": 3, "snr": "0967"}

    def test_prefixed_snr(self):
        from api.v2.manufacturing.sessions import _derive_panel_snrs
        result = _derive_panel_snrs("DUT-0964", 3)
        assert result[0] == {"slotIndex": 0, "snr": "DUT-0964"}
        assert result[1] == {"slotIndex": 1, "snr": "DUT-0965"}
        assert result[2] == {"slotIndex": 2, "snr": "DUT-0966"}

    def test_zero_padding_preserved(self):
        from api.v2.manufacturing.sessions import _derive_panel_snrs
        result = _derive_panel_snrs("0001", 3)
        assert result[0]["snr"] == "0001"
        assert result[1]["snr"] == "0002"
        assert result[2]["snr"] == "0003"

    def test_single_slot(self):
        from api.v2.manufacturing.sessions import _derive_panel_snrs
        result = _derive_panel_snrs("100", 1)
        assert len(result) == 1
        assert result[0] == {"slotIndex": 0, "snr": "100"}

    def test_non_numeric_snr(self):
        from api.v2.manufacturing.sessions import _derive_panel_snrs
        result = _derive_panel_snrs("ABCDEF", 3)
        assert result[0]["snr"] == "ABCDEF"
        assert result[1]["snr"] is None
        assert result[2]["snr"] is None


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/resolve-panel
# ---------------------------------------------------------------------------

class TestResolvePanel:
    def _four_slots(self):
        return [
            _slot(id=f"s10-slot-{i}", slotIndex=i, name=f"Slot {i + 1}")
            for i in range(4)
        ]

    def test_resolves_panel_snrs(self, authed_client, mock_db):
        slots = self._four_slots()
        fixture = _fixture(slots=slots)
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/resolve-panel",
            data=json.dumps({"snr": "0964"}),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["primarySnr"] == "0964"
        assert len(data["slots"]) == 4
        assert data["slots"][0]["snr"] == "0964"
        assert data["slots"][1]["snr"] == "0965"
        assert data["slots"][2]["snr"] == "0966"
        assert data["slots"][3]["snr"] == "0967"

    def test_returns_slot_labels(self, authed_client, mock_db):
        slots = self._four_slots()
        fixture = _fixture(slots=slots)
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/resolve-panel",
            data=json.dumps({"snr": "0964"}),
        )
        data = resp.get_json()["data"]
        assert data["slots"][0]["label"] == "Slot 1"
        assert data["slots"][3]["label"] == "Slot 4"

    def test_returns_404_missing_session(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-missing/resolve-panel",
            data=json.dumps({"snr": "0964"}),
        )
        assert resp.status_code == 404

    def test_returns_400_inactive_session(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session(status="COMPLETED")

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/resolve-panel",
            data=json.dumps({"snr": "0964"}),
        )
        assert resp.status_code == 400

    def test_returns_400_missing_snr(self, authed_client, mock_db):
        fixture = _fixture(slots=self._four_slots())
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/resolve-panel",
            data=json.dumps({}),
        )
        assert resp.status_code == 400

    def test_returns_400_no_active_slots(self, authed_client, mock_db):
        fixture = _fixture(slots=[])
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/resolve-panel",
            data=json.dumps({"snr": "0964"}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/runs — add run with slotSnrs / runType
# ---------------------------------------------------------------------------

class TestAddRunWithSlotSnrs:
    def _four_slots(self):
        return [
            _slot(id=f"s10-slot-{i}", slotIndex=i, name=f"Slot {i + 1}")
            for i in range(4)
        ]

    def test_uses_slot_snrs_when_provided(self, authed_client, mock_db):
        slots = self._four_slots()
        fixture = _fixture(slots=slots)
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)
        created = _run()
        mock_db.testrun.create.return_value = created
        mock_db.testrun.find_unique.return_value = created

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({
                "qrCode": "0964",
                "slotSnrs": [
                    {"slotIndex": 0, "snr": "0964"},
                    {"slotIndex": 1, "snr": "0965"},
                    {"slotIndex": 2, "snr": "0966"},
                    {"slotIndex": 3, "snr": "0967"},
                ],
            }),
        )
        assert resp.status_code == 201
        # Verify runtarget.create was called 4 times with correct SNRs
        calls = mock_db.runtarget.create.call_args_list
        assert len(calls) == 4
        assert calls[0].kwargs["data"]["serialNumber"] == "0964"
        assert calls[1].kwargs["data"]["serialNumber"] == "0965"
        assert calls[2].kwargs["data"]["serialNumber"] == "0966"
        assert calls[3].kwargs["data"]["serialNumber"] == "0967"

    def test_standalone_creates_one_target(self, authed_client, mock_db):
        slots = self._four_slots()
        fixture = _fixture(slots=slots)
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)
        created = _run(targetCount=1)
        mock_db.testrun.create.return_value = created
        mock_db.testrun.find_unique.return_value = created

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({
                "qrCode": "0964",
                "runType": "standalone",
            }),
        )
        assert resp.status_code == 201
        assert mock_db.runtarget.create.call_count == 1

    def test_invalid_run_type(self, authed_client, mock_db):
        fixture = _fixture(slots=self._four_slots())
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({
                "qrCode": "0964",
                "runType": "invalid",
            }),
        )
        assert resp.status_code == 400

    def test_invalid_slot_snrs_format(self, authed_client, mock_db):
        fixture = _fixture(slots=self._four_slots())
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({
                "qrCode": "0964",
                "slotSnrs": "not-an-array",
            }),
        )
        assert resp.status_code == 400

    def test_slot_snrs_missing_fields(self, authed_client, mock_db):
        fixture = _fixture(slots=self._four_slots())
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({
                "qrCode": "0964",
                "slotSnrs": [{"slotIndex": 0}],
            }),
        )
        assert resp.status_code == 400

    def test_defaults_to_panel_run_type(self, authed_client, mock_db):
        slots = self._four_slots()
        fixture = _fixture(slots=slots)
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)
        created = _run()
        mock_db.testrun.create.return_value = created
        mock_db.testrun.find_unique.return_value = created

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/runs",
            data=json.dumps({"qrCode": "0964"}),
        )
        assert resp.status_code == 201
        # All 4 slots should have targets
        assert mock_db.runtarget.create.call_count == 4
