"""Tests for manufacturing sessions — /v2/manufacturing/sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _stub_assignable():
    """Sessions are gated on ``Fixture.assignable`` which lives behind a
    K8s call in production. For unit tests, default to "ready" — tests
    that need to exercise the gate override the patches inline."""
    health = {
        "health": "ONLINE",
        "healthDetails": {"nodesReady": 1, "nodesTotal": 1, "mtibsReady": 1, "mtibsTotal": 1},
        "slotStates": {},
    }
    with patch("src.api.v2.fixtures.fixtures._get_mtib_status_map", return_value={}), \
         patch("src.api.v2.fixtures.fixtures._compute_fixture_health", return_value=health):
        yield


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


def _test_package(**overrides):
    """Released MANUFACTURING test package — required by the session-create
    resolver gate (an explicit ``testPackageId`` or a latest-released fallback
    must resolve before a session can lock its fixture)."""
    defaults = dict(
        id="s10-tp-1",
        productId="s10-prod-1",
        type="MANUFACTURING",
        status="RELEASED",
        version="1.0.0",
        releasedVersion="1.0.0",
        boardRevisionId="s10-rev-1",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _slot(**overrides):
    defaults = dict(
        id="s10-slot-0",
        fixtureId="s10-fix-1",
        slotIndex=0,
        name="Slot 1",
        label=None,
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


@pytest.fixture(autouse=True)
def _mock_runner_deploy():
    """Mock runner deployment and MTIB health check — not under test here."""
    with patch("src.services.kubernetes.mtib_deployments.wait_for_mtibs_healthy", return_value={"healthy": [], "unhealthy": []}):
        with patch("src.api.v2.manufacturing.runner.deploy_manufacturing_runner", return_value="runner-1"):
            yield


@pytest.fixture(autouse=True)
def _mock_runner_teardown():
    """Mock runner teardown — not under test here."""
    with patch("src.api.v2.manufacturing.runner.teardown_manufacturing_runner", return_value=None):
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
        # ApiResponse envelope: ``{ data: { data: [...], pagination: {...} }, errors: [] }``
        body = resp.get_json()["data"]
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "MANUFACTURING"

    def test_returns_empty_list(self, authed_client, mock_db):
        mock_db.fixture.find_many.return_value = []
        mock_db.fixture.count.return_value = 0

        resp = authed_client.get("/v2/manufacturing/fixtures")
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["data"] == []
        assert body["pagination"]["total"] == 0


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
        # Sessions also require a resolvable test package. The wizard
        # picks one explicitly, or the resolver falls back to the latest
        # RELEASED — mock that fallback for the happy path.
        mock_db.testpackage.find_first.return_value = _test_package()
        created = _session()
        mock_db.manufacturingsession.create.return_value = created
        # No fixture.update call needed — IN_USE is derived from the new
        # session row.

        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({
                "productId": "s10-prod-1",
                "fixtureId": "s10-fix-1",
            }),
        )
        assert resp.status_code == 201

    def test_returns_409_if_fixture_locked(self, authed_client, mock_db):
        # Fixture itself is fine, but another active session already holds it.
        mock_db.fixture.find_unique.return_value = _fixture()
        mock_db.manufacturingsession.find_many.return_value = [
            make_obj(id="other-sess", fixtureId="s10-fix-1", status="ACTIVE",
                     startedAt=NOW, createdAt=NOW),
        ]
        mock_db.testrun.find_many.return_value = []

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

    def test_dev_fixture_falls_back_to_dev_package_when_no_release(self, authed_client, mock_db):
        """DEV fixture with no released package picks the latest dev package.

        Today the resolver only falls back to ``RELEASED`` regardless of
        fixture purpose, which 409s the operator on a dev rig that has
        never been through a release. DEV rigs are sandboxes — when no
        explicit testPackageId is passed and no released package exists,
        pick the latest DEVELOPMENT package instead so the iteration
        loop just works.
        """
        dev_fixture = _fixture(purpose="DEV")
        mock_db.fixture.find_unique.return_value = dev_fixture
        mock_db.product.find_unique.return_value = _product()
        mock_db.assetset.find_first.return_value = _asset_set(id="s10-as-1", status="COMPLETE")

        # The resolver is called twice in the session-create path
        # (RELEASED-mode, then DEV-mode fallback for a dev fixture).
        # Return the dev package on any call where the where-clause asks
        # for DEVELOPMENT status, None on a RELEASED query. Subsequent
        # calls (e.g., from the runner deploy path) match anything and
        # safely return the dev package too.
        dev_pkg = _test_package(
            id="s10-tp-dev-1", status="DEVELOPMENT", version="dev-foo-1", releasedVersion=None,
        )
        def _testpkg_find_first(*args, **kwargs):
            where = kwargs.get("where") or (args[0] if args else {})
            status = (where or {}).get("status") if isinstance(where, dict) else None
            if status == "RELEASED":
                return None
            return dev_pkg
        mock_db.testpackage.find_first.side_effect = _testpkg_find_first
        mock_db.manufacturingsession.create.return_value = _session()

        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({
                "productId": "s10-prod-1",
                "fixtureId": "s10-fix-1",
            }),
        )
        assert resp.status_code == 201, resp.get_json()

    def test_release_fixture_still_blocks_when_no_release_exists(self, authed_client, mock_db):
        """RELEASE fixture (production) still requires an explicit release."""
        rel_fixture = _fixture(purpose="RELEASE")
        mock_db.fixture.find_unique.return_value = rel_fixture
        mock_db.product.find_unique.return_value = _product()
        mock_db.assetset.find_first.return_value = _asset_set(id="s10-as-1", status="COMPLETE")
        mock_db.testpackage.find_first.return_value = None  # No package at all

        resp = authed_client.post(
            "/v2/manufacturing/sessions",
            data=json.dumps({
                "productId": "s10-prod-1",
                "fixtureId": "s10-fix-1",
            }),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /v2/manufacturing/sessions — list sessions (paginated)
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_returns_paginated_sessions(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_many.return_value = [_session()]
        mock_db.manufacturingsession.count.return_value = 1

        resp = authed_client.get("/v2/manufacturing/sessions")
        assert resp.status_code == 200
        # ApiResponse envelope: ``{ data: { data: [...], pagination: {...} }, errors: [] }``
        body = resp.get_json()["data"]
        assert len(body["data"]) == 1
        assert body["pagination"]["total"] == 1

    def test_pagination_params(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_many.return_value = []
        mock_db.manufacturingsession.count.return_value = 0

        resp = authed_client.get("/v2/manufacturing/sessions?page=2&limit=10")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["pagination"]["page"] == 2

    def test_yj52qt_regression_list_with_runs_and_targets(self, authed_client, mock_db):
        """Regression test for yj52qt — GET /v2/manufacturing/sessions?page=1&limit=25
        returned 500 on app v0.7.1.

        The list-sessions code path is byte-identical between v0.7.1 and
        HEAD (the surrounding create/end paths are what changed), so the
        500 on v0.7.1 was almost certainly a transient — the bug report
        is "already fixed" rather than "fix needed". This test pins the
        contract by serializing a session with the same shape the
        production query produces: include runs and run targets so the
        _compute_board_counts dedupe path is exercised, mix PASSED /
        FAILED / ERROR / RUNNING target statuses, and keep the exact
        page/limit the user reported (page=1&limit=25). If the endpoint
        ever 500s on this shape again, this test catches it.
        """
        run = _run(
            id="run-a",
            status="COMPLETED",
            targets=[
                make_obj(
                    id="t-1", serialNumber="SNR-1", status="PASSED",
                    slotIndex=0, slotId="s10-slot-0", deviceId=None,
                    metadata=None, errorMessage=None,
                    startedAt=NOW, completedAt=NOW, durationMs=1000,
                    runId="run-a", executions=[],
                ),
                make_obj(
                    id="t-2", serialNumber="SNR-2", status="FAILED",
                    slotIndex=1, slotId="s10-slot-1", deviceId=None,
                    metadata=None, errorMessage="hw fault",
                    startedAt=NOW, completedAt=NOW, durationMs=900,
                    runId="run-a", executions=[],
                ),
                make_obj(
                    id="t-3", serialNumber="SNR-3", status="ERROR",
                    slotIndex=2, slotId=None, deviceId=None,
                    metadata=None, errorMessage="mtib disconnect",
                    startedAt=NOW, completedAt=NOW, durationMs=200,
                    runId="run-a", executions=[],
                ),
                make_obj(
                    id="t-4", serialNumber=None, status="RUNNING",
                    slotIndex=3, slotId=None, deviceId=None,
                    metadata=None, errorMessage=None,
                    startedAt=NOW, completedAt=None, durationMs=None,
                    runId="run-a", executions=[],
                ),
            ],
        )
        sess = _session(runs=[run])
        mock_db.manufacturingsession.find_many.return_value = [sess]
        mock_db.manufacturingsession.count.return_value = 1

        # Replay the exact query the user reported in yj52qt.
        resp = authed_client.get("/v2/manufacturing/sessions?page=1&limit=25")
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()["data"]
        assert len(body["data"]) == 1
        s = body["data"][0]
        # Per-board counts should dedupe by serial number, treat
        # FAILED+ERROR as failed, and skip the unscanned (None SNR) slot
        # — verify that the serializer produced sane numbers rather than
        # propagating the v0.7.1 500.
        assert s["totalUnits"] == 4  # 3 SNRs + 1 anonymous (uses target id)
        assert s["passedUnits"] == 1
        assert s["failedUnits"] == 2


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
        slots = [_slot(id=f"s10-slot-{i}", slotIndex=i, name=f"Slot {i + 1}") for i in range(4)]
        fixture_with_slots = _fixture(slots=slots)
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
        # No fixture-unlock write — fixture's derived lockState transitions
        # automatically when the session row flips to COMPLETED.

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
        # No fixture-unlock write — fixture's derived lockState transitions
        # automatically when the session row flips to COMPLETED.

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
        # No fixture-unlock write — fixture's derived lockState transitions
        # automatically when the session row flips to COMPLETED.
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
# _resolve_panel_snrs — unit tests for CoreOps-based SNR resolution
# ---------------------------------------------------------------------------

class TestResolvePanelSnrs:
    def test_singleton_returns_scanned_snr(self):
        from api.v2.manufacturing.sessions import _resolve_panel_snrs
        result = _resolve_panel_snrs("0964", 1)
        assert len(result) == 1
        assert result[0] == {"slotIndex": 0, "snr": "0964", "deviceId": None}

    @patch("api.v2.manufacturing.sessions._get_coreops_client", return_value=None)
    def test_no_coreops_falls_back_to_slot0(self, _mock_coreops):
        from api.v2.manufacturing.sessions import _resolve_panel_snrs
        result = _resolve_panel_snrs("0964", 4)
        assert len(result) == 4
        assert result[0]["snr"] == "0964"
        assert result[1]["snr"] is None
        assert result[2]["snr"] is None
        assert result[3]["snr"] is None

    @patch("api.v2.manufacturing.sessions._get_coreops_client")
    def test_coreops_assembly_maps_boards(self, mock_coreops):
        mock_client = MagicMock()
        mock_client.search_board_assembly.return_value = {
            "boards": [
                {"panelPosition": 0, "boardSerialNumber": "SN-A"},
                {"panelPosition": 1, "boardSerialNumber": "SN-B"},
                {"panelPosition": 2, "boardSerialNumber": "SN-C"},
                {"panelPosition": 3, "boardSerialNumber": "SN-D"},
            ],
        }
        mock_coreops.return_value = mock_client

        from api.v2.manufacturing.sessions import _resolve_panel_snrs
        result = _resolve_panel_snrs("SN-A", 4)
        assert result[0]["snr"] == "SN-A"
        assert result[1]["snr"] == "SN-B"
        assert result[2]["snr"] == "SN-C"
        assert result[3]["snr"] == "SN-D"

    @patch("api.v2.manufacturing.sessions._get_coreops_client")
    def test_coreops_with_position_map(self, mock_coreops):
        mock_client = MagicMock()
        mock_client.search_board_assembly.return_value = {
            "boards": [
                {"panelPosition": 0, "boardSerialNumber": "SN-A"},
                {"panelPosition": 1, "boardSerialNumber": "SN-B"},
            ],
        }
        mock_coreops.return_value = mock_client

        from api.v2.manufacturing.sessions import _resolve_panel_snrs
        # Swap positions 0↔1
        result = _resolve_panel_snrs("SN-A", 2, position_map={0: 1, 1: 0})
        assert result[0]["snr"] == "SN-B"
        assert result[1]["snr"] == "SN-A"


# ---------------------------------------------------------------------------
# POST /v2/manufacturing/sessions/<id>/resolve-panel
# ---------------------------------------------------------------------------

class TestResolvePanel:
    def _four_slots(self):
        return [
            _slot(id=f"s10-slot-{i}", slotIndex=i, name=f"Slot {i + 1}")
            for i in range(4)
        ]

    @patch("api.v2.manufacturing.sessions._get_coreops_client")
    def test_resolves_panel_snrs(self, mock_coreops, authed_client, mock_db):
        mock_client = MagicMock()
        mock_client.search_board_assembly.return_value = {
            "boards": [
                {"panelPosition": 0, "boardSerialNumber": "0964"},
                {"panelPosition": 1, "boardSerialNumber": "0965"},
                {"panelPosition": 2, "boardSerialNumber": "0966"},
                {"panelPosition": 3, "boardSerialNumber": "0967"},
            ],
        }
        mock_client.assign_device_id.return_value = None
        mock_coreops.return_value = mock_client

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

    @patch("api.v2.manufacturing.sessions._get_coreops_client")
    def test_returns_slot_labels(self, mock_coreops, authed_client, mock_db):
        mock_client = MagicMock()
        mock_client.search_board_assembly.return_value = {
            "boards": [
                {"panelPosition": i, "boardSerialNumber": f"SN-{i}"}
                for i in range(4)
            ],
        }
        mock_client.assign_device_id.return_value = None
        mock_coreops.return_value = mock_client

        slots = self._four_slots()
        fixture = _fixture(slots=slots)
        mock_db.manufacturingsession.find_unique.return_value = _session(fixture=fixture)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/resolve-panel",
            data=json.dumps({"snr": "SN-0"}),
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
