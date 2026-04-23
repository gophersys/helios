"""Tests for graceful drain — /drain endpoint and readiness during drain."""

from __future__ import annotations

import json

import pytest

from src.app import create_app
from src.worker.state import WorkerState


@pytest.fixture
def worker_state(monkeypatch):
    """Set up a global worker state for the test."""
    import src.worker.loop as loop_mod
    state = WorkerState(worker_id="test-worker")
    monkeypatch.setattr(loop_mod, "_worker_state", state)
    return state


@pytest.fixture
def client(config, worker_state):
    app = create_app(config)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestDrainEndpoint:
    def test_drain_sets_draining(self, client, worker_state):
        """POST /drain sets worker state to draining."""
        assert worker_state.status == "idle"

        resp = client.post("/drain")
        assert resp.status_code == 200

        assert worker_state.status == "draining"

    def test_drain_returns_state(self, client, worker_state):
        """POST /drain returns the updated worker state."""
        resp = client.post("/drain")
        data = resp.get_json()
        assert data["status"] == "draining"
        assert data["workerId"] == "test-worker"

    def test_drain_idempotent(self, client, worker_state):
        """Calling /drain twice is safe."""
        client.post("/drain")
        resp = client.post("/drain")
        assert resp.status_code == 200
        assert worker_state.status == "draining"

    def test_drain_while_building(self, client, worker_state):
        """Drain while a build is in progress."""
        worker_state.start_job("job-123", product="alpha")
        assert worker_state.status == "building"

        resp = client.post("/drain")
        assert resp.status_code == 200
        assert worker_state.status == "draining"
        # Job info preserved — build should finish
        assert worker_state.current_job_id == "job-123"


class TestReadyDuringDrain:
    def test_ready_when_idle(self, client, worker_state):
        """GET /ready returns 200 when idle."""
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.get_json()["ready"] is True

    def test_ready_when_building(self, client, worker_state):
        """GET /ready returns 200 when building (still accepting work)."""
        worker_state.start_job("job-456")
        resp = client.get("/ready")
        assert resp.status_code == 200

    def test_ready_returns_503_when_draining(self, client, worker_state):
        """GET /ready returns 503 when draining — K8s removes from Service."""
        worker_state.set_draining()

        resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["ready"] is False
        assert "draining" in data["reason"]

    def test_health_always_200(self, client, worker_state):
        """GET /health returns 200 even when draining (liveness must stay up)."""
        worker_state.set_draining()

        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "healthy"
