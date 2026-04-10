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
        product=_product(),
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
