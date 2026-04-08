"""Tests for manufacturing reporter callbacks — /v2/manufacturing/sessions/<id>/report/."""

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


def _session(**overrides):
    defaults = dict(
        id="s10-sess-1",
        productId="s10-prod-1",
        fixtureId="s10-fix-1",
        status="ACTIVE",
        operatorId="test-user-id",
        panelCount=1,
        passedCount=0,
        failedCount=0,
        config=None,
        startedAt=_now(),
        endedAt=None,
        createdAt=_now(),
        updatedAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _panel(**overrides):
    defaults = dict(
        id="s10-panel-1",
        sessionId="s10-sess-1",
        panelIndex=0,
        qrCode="s10-QR-001",
        status="RUNNING",
        unitCount=4,
        passedUnits=0,
        failedUnits=0,
        startedAt=_now(),
        completedAt=None,
        durationMs=None,
        createdAt=_now(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _unit(**overrides):
    defaults = dict(
        id="s10-unit-1",
        panelId="s10-panel-1",
        slotIndex=0,
        slotId="slot-0",
        serialNumber=None,
        status="RUNNING",
        stages=[],
        errorMessage=None,
        startedAt=_now(),
        completedAt=None,
        durationMs=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_socketio():
    with patch("api.v2.manufacturing.reporter._socketio", new=MagicMock()) as mock_sio:
        yield mock_sio


# ---------------------------------------------------------------------------
# POST /report/panel-start
# ---------------------------------------------------------------------------

class TestPanelStart:
    def test_creates_panel(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingpanel.count.return_value = 0
        mock_db.manufacturingpanel.create.return_value = _panel()
        mock_db.manufacturingsession.update.return_value = _session(panelCount=1)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/panel-start",
            data=json.dumps({"qrCode": "s10-QR-001", "unitCount": 4}),
        )
        assert resp.status_code == 201

    def test_returns_404_if_session_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-missing/report/panel-start",
            data=json.dumps({"qrCode": "s10-QR-001", "unitCount": 4}),
        )
        assert resp.status_code == 404

    def test_returns_400_missing_fields(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/panel-start",
            data=json.dumps({}),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /report/unit-start
# ---------------------------------------------------------------------------

class TestUnitStart:
    def test_creates_unit(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingpanel.find_unique.return_value = _panel()
        mock_db.manufacturingunit.create.return_value = _unit()

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/unit-start",
            data=json.dumps({
                "panelId": "s10-panel-1",
                "slotIndex": 0,
                "slotId": "slot-0",
            }),
        )
        assert resp.status_code == 201

    def test_returns_404_if_panel_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingpanel.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/unit-start",
            data=json.dumps({
                "panelId": "s10-missing",
                "slotIndex": 0,
                "slotId": "slot-0",
            }),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /report/stage-result
# ---------------------------------------------------------------------------

class TestStageResult:
    def test_appends_stage_result(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingunit.find_unique.return_value = _unit(stages=[])
        mock_db.manufacturingunit.update.return_value = _unit(
            stages=[{"name": "Electrical", "status": "PASSED", "durationMs": 500}]
        )

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/stage-result",
            data=json.dumps({
                "unitId": "s10-unit-1",
                "stageName": "Electrical",
                "status": "PASSED",
                "durationMs": 500,
            }),
        )
        assert resp.status_code == 200

    def test_returns_404_if_unit_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingunit.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/stage-result",
            data=json.dumps({
                "unitId": "s10-missing",
                "stageName": "Electrical",
                "status": "PASSED",
            }),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /report/unit-result
# ---------------------------------------------------------------------------

class TestUnitResult:
    def test_updates_unit_status(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingunit.find_unique.return_value = _unit()
        mock_db.manufacturingunit.update.return_value = _unit(status="PASSED")

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/unit-result",
            data=json.dumps({
                "unitId": "s10-unit-1",
                "status": "PASSED",
                "serialNumber": "SN001",
                "durationMs": 3000,
            }),
        )
        assert resp.status_code == 200

    def test_returns_404_if_unit_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingunit.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/unit-result",
            data=json.dumps({
                "unitId": "s10-missing",
                "status": "PASSED",
            }),
        )
        assert resp.status_code == 404

    def test_returns_400_invalid_status(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingunit.find_unique.return_value = _unit()

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/unit-result",
            data=json.dumps({
                "unitId": "s10-unit-1",
                "status": "INVALID_STATUS",
            }),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /report/panel-complete
# ---------------------------------------------------------------------------

class TestPanelComplete:
    def test_completes_panel_and_updates_counts(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingpanel.find_unique.return_value = _panel()
        mock_db.manufacturingpanel.update.return_value = _panel(status="PASSED")
        mock_db.manufacturingsession.update.return_value = _session(passedCount=1)

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/panel-complete",
            data=json.dumps({
                "panelId": "s10-panel-1",
                "status": "PASSED",
                "passedUnits": 4,
                "failedUnits": 0,
                "durationMs": 12000,
            }),
        )
        assert resp.status_code == 200

    def test_returns_404_if_panel_missing(self, authed_client, mock_db):
        mock_db.manufacturingsession.find_unique.return_value = _session()
        mock_db.manufacturingpanel.find_unique.return_value = None

        resp = authed_client.post(
            "/v2/manufacturing/sessions/s10-sess-1/report/panel-complete",
            data=json.dumps({
                "panelId": "s10-missing",
                "status": "PASSED",
                "passedUnits": 4,
                "failedUnits": 0,
            }),
        )
        assert resp.status_code == 404
