"""Tests for api/v2/sessions/demo.py — demo simulation endpoint."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_eventlet():
    """Mock eventlet module since it may not be installed in test env."""
    mock_eventlet = MagicMock()
    with patch.dict(sys.modules, {"eventlet": mock_eventlet}):
        yield mock_eventlet


@pytest.fixture(autouse=True)
def _mock_emit():
    with patch("api.v2.sessions.reporter._emit_validation_event"):
        yield


class TestSimulateRun:
    """Tests for simulate_run endpoint."""

    def test_simulate_returns_200(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/demo/simulate?speed=0.1&scenario=mixed")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["runId"] == "run-1"
        assert data["status"] == "SIMULATING"
        assert data["speed"] == 0.1
        assert data["scenario"] == "mixed"

    def test_simulate_happy_scenario(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/demo/simulate?scenario=happy")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["scenario"] == "happy"

    def test_simulate_failing_scenario(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/demo/simulate?scenario=failing")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["scenario"] == "failing"

    def test_simulate_invalid_scenario_returns_400(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/demo/simulate?scenario=chaos")
        assert resp.status_code == 400

    def test_simulate_speed_clamped(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/demo/simulate?speed=50")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["speed"] == 1.0

    def test_simulate_defaults(self, authed_client, mock_db):
        resp = authed_client.post("/v2/sessions/run-1/demo/simulate")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["speed"] == 0.1
        assert data["scenario"] == "mixed"
        assert data["totalTests"] == 16
