"""Tests for Flask API endpoints: health, queue, workers, metrics.

All tests create a fresh Flask test client via create_app() and inject
WorkerState through the module-level singleton in src.worker.loop.
No real worker threads or Docker access are required.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.app import create_app
from src.worker.state import WorkerState


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Configured Flask test application."""
    return create_app()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def idle_state() -> WorkerState:
    """A WorkerState in idle (no active job)."""
    return WorkerState(worker_id="test-worker-01")


@pytest.fixture
def busy_state() -> WorkerState:
    """A WorkerState that is actively building a job."""
    state = WorkerState(worker_id="test-worker-01")
    state.start_job("job-abc-123", product="alpha")
    return state


@pytest.fixture
def draining_state() -> WorkerState:
    """A WorkerState that is draining."""
    state = WorkerState(worker_id="test-worker-01")
    state.set_draining()
    return state


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_always_returns_200(self, client):
        """Liveness probe always returns 200 regardless of worker state."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_healthy_status(self, client):
        """Response body contains status=healthy."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/health")
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "build-service"

    def test_health_includes_worker_dict_when_state_present(self, client, idle_state):
        """When a WorkerState exists, worker dict is included in the response."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/health")
        data = resp.get_json()
        assert data["worker"] is not None
        assert data["worker"]["workerId"] == "test-worker-01"

    def test_health_worker_none_when_no_state(self, client):
        """When no WorkerState is initialized, worker field is None."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/health")
        data = resp.get_json()
        assert data["worker"] is None

    def test_health_returns_200_during_draining(self, client, draining_state):
        """Liveness probe stays 200 even when the worker is draining."""
        with patch("src.worker.loop.get_worker_state", return_value=draining_state):
            resp = client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /ready
# ---------------------------------------------------------------------------

class TestReadyEndpoint:
    """Tests for GET /ready."""

    def test_ready_returns_200_when_idle(self, client, idle_state):
        """Returns 200 when worker is initialized and idle."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ready"] is True

    def test_ready_returns_503_when_no_state(self, client):
        """Returns 503 when worker is not yet initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["ready"] is False

    def test_ready_returns_503_when_draining(self, client, draining_state):
        """Returns 503 when the worker is draining (finishing last build)."""
        with patch("src.worker.loop.get_worker_state", return_value=draining_state):
            resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["ready"] is False
        assert "draining" in data["reason"]


# ---------------------------------------------------------------------------
# /drain
# ---------------------------------------------------------------------------

class TestDrainEndpoint:
    """Tests for POST /drain."""

    def test_drain_sets_worker_to_draining(self, client, idle_state):
        """POST /drain transitions the worker to draining status."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.post("/drain")
        assert resp.status_code == 200
        assert idle_state.status == "draining"

    def test_drain_returns_503_when_no_state(self, client):
        """POST /drain returns 503 when no worker is initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.post("/drain")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# /queue
# ---------------------------------------------------------------------------

class TestQueueEndpoint:
    """Tests for GET /queue and GET /queue/jobs."""

    def test_queue_overview_returns_503_when_no_state(self, client):
        """Returns 503 when worker is not initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/queue")
        assert resp.status_code == 503

    def test_queue_overview_returns_200_when_idle(self, client, idle_state):
        """Returns 200 with worker dict when idle."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/queue")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "worker" in data
        assert data["currentJob"] is None

    def test_queue_overview_shows_current_job_when_busy(self, client, busy_state):
        """currentJob is populated when worker is processing a build."""
        with patch("src.worker.loop.get_worker_state", return_value=busy_state):
            resp = client.get("/queue")
        data = resp.get_json()
        assert data["currentJob"] is not None
        assert data["currentJob"]["id"] == "job-abc-123"
        assert data["currentJob"]["product"] == "alpha"

    def test_list_jobs_returns_503_when_no_state(self, client):
        """GET /queue/jobs returns 503 when worker not initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/queue/jobs")
        assert resp.status_code == 503

    def test_list_jobs_returns_empty_when_idle(self, client, idle_state):
        """GET /queue/jobs returns empty data list when idle."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/queue/jobs")
        data = resp.get_json()
        assert data["data"] == []

    def test_list_jobs_includes_active_job_when_busy(self, client, busy_state):
        """GET /queue/jobs includes the active job when busy."""
        with patch("src.worker.loop.get_worker_state", return_value=busy_state):
            resp = client.get("/queue/jobs")
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "job-abc-123"
        assert data["data"][0]["status"] == "active"

    def test_list_jobs_includes_summary_counters(self, client, idle_state):
        """GET /queue/jobs always includes completed/failed summary."""
        idle_state.jobs_completed = 5
        idle_state.jobs_failed = 1
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/queue/jobs")
        data = resp.get_json()
        assert data["summary"]["completed"] == 5
        assert data["summary"]["failed"] == 1


# ---------------------------------------------------------------------------
# /workers
# ---------------------------------------------------------------------------

class TestWorkersEndpoint:
    """Tests for GET /workers, GET /workers/<id>, PATCH /workers/<id>."""

    def test_list_workers_returns_empty_when_no_state(self, client):
        """Returns empty data list when no worker is initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/workers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []

    def test_list_workers_returns_worker_list(self, client, idle_state):
        """Returns a list with one entry when worker is initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/workers")
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["workerId"] == "test-worker-01"

    def test_get_worker_returns_404_when_wrong_id(self, client, idle_state):
        """Returns 404 when requested worker ID does not match this worker."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/workers/wrong-worker-id")
        assert resp.status_code == 404

    def test_get_worker_returns_200_for_correct_id(self, client, idle_state):
        """Returns 200 with worker detail for the correct worker ID."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/workers/test-worker-01")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["workerId"] == "test-worker-01"

    def test_get_worker_returns_404_when_no_state(self, client):
        """Returns 404 when no state is initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/workers/any-id")
        assert resp.status_code == 404

    def test_patch_worker_drain_sets_draining(self, client, idle_state):
        """PATCH with status=draining transitions worker to draining."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.patch(
                "/workers/test-worker-01",
                json={"status": "draining"},
            )
        assert resp.status_code == 200
        assert idle_state.status == "draining"

    def test_patch_worker_returns_4xx_without_json_body(self, client, idle_state):
        """PATCH without a JSON body returns a 4xx error (400 or 415)."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.patch(
                "/workers/test-worker-01",
                data="not-json",
                content_type="text/plain",
            )
        assert resp.status_code in (400, 415)

    def test_patch_worker_returns_404_when_wrong_id(self, client, idle_state):
        """PATCH with wrong worker ID returns 404."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.patch("/workers/other-worker", json={"status": "draining"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    """Tests for GET /metrics (Prometheus text format)."""

    def test_metrics_returns_empty_body_when_no_state(self, client):
        """Returns 200 with empty body when worker not initialized."""
        with patch("src.worker.loop.get_worker_state", return_value=None):
            resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/plain")

    def test_metrics_includes_worker_status_gauge(self, client, idle_state):
        """Includes build_service_worker_status gauge line."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/metrics")
        body = resp.data.decode()
        assert "build_service_worker_status" in body
        assert "test-worker-01" in body

    def test_metrics_includes_completed_counter(self, client, idle_state):
        """Includes build_service_jobs_completed_total counter."""
        idle_state.jobs_completed = 7
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/metrics")
        body = resp.data.decode()
        assert "build_service_jobs_completed_total 7" in body

    def test_metrics_includes_failed_counter(self, client, idle_state):
        """Includes build_service_jobs_failed_total counter."""
        idle_state.jobs_failed = 3
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/metrics")
        body = resp.data.decode()
        assert "build_service_jobs_failed_total 3" in body

    def test_metrics_busy_gauge_is_1_when_building(self, client, busy_state):
        """build_service_busy is 1 when processing a job."""
        with patch("src.worker.loop.get_worker_state", return_value=busy_state):
            resp = client.get("/metrics")
        body = resp.data.decode()
        assert "build_service_busy 1" in body

    def test_metrics_busy_gauge_is_0_when_idle(self, client, idle_state):
        """build_service_busy is 0 when idle."""
        with patch("src.worker.loop.get_worker_state", return_value=idle_state):
            resp = client.get("/metrics")
        body = resp.data.decode()
        assert "build_service_busy 0" in body

    @pytest.mark.parametrize("status,expected_value", [
        ("idle", 1),
        ("building", 2),
        ("draining", 3),
        ("offline", 0),
    ])
    def test_metrics_status_mapping(self, client, status, expected_value):
        """Worker status is mapped to the correct integer value."""
        state = WorkerState(worker_id="w1")
        state.status = status
        with patch("src.worker.loop.get_worker_state", return_value=state):
            resp = client.get("/metrics")
        body = resp.data.decode()
        assert f'build_service_worker_status{{worker="w1"}} {expected_value}' in body
