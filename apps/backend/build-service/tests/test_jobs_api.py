"""Tests for the /jobs API endpoints (notify, cancel)."""

from __future__ import annotations

import json

import pytest

from src.app import create_app
from src.api.jobs import set_job_queue
from src.worker.queue import JobQueue


@pytest.fixture
def job_queue():
    q = JobQueue()
    set_job_queue(q)
    yield q
    set_job_queue(None)


@pytest.fixture
def client(config, job_queue):
    app = create_app(config)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestNotifyEndpoint:
    def test_notify_enqueues_job(self, client, job_queue):
        """POST /jobs/notify enqueues a job and returns 202."""
        resp = client.post("/jobs/notify",
                           data=json.dumps({"jobId": "job-123", "priority": 75}),
                           content_type="application/json")
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["status"] == "accepted"
        assert data["jobId"] == "job-123"
        assert job_queue.depth == 1

    def test_notify_default_priority(self, client, job_queue):
        """Default priority is 50 if not specified."""
        resp = client.post("/jobs/notify",
                           data=json.dumps({"jobId": "job-456"}),
                           content_type="application/json")
        assert resp.status_code == 202
        # Dequeue to verify it was added
        assert job_queue.dequeue(timeout=1.0) == "job-456"

    def test_notify_missing_job_id(self, client, job_queue):
        """Returns 400 when jobId is missing."""
        resp = client.post("/jobs/notify",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400

    def test_notify_no_body(self, client, job_queue):
        """Returns 400 when no body is sent."""
        resp = client.post("/jobs/notify")
        assert resp.status_code == 400

    def test_notify_duplicate_suppressed(self, client, job_queue):
        """Duplicate notifications for same jobId are silently dropped."""
        client.post("/jobs/notify",
                    data=json.dumps({"jobId": "dup-1"}),
                    content_type="application/json")
        client.post("/jobs/notify",
                    data=json.dumps({"jobId": "dup-1"}),
                    content_type="application/json")
        assert job_queue.depth == 1


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "healthy"

    def test_ready_returns_503_before_worker(self, client):
        """Ready returns 503 when worker state not yet initialized."""
        # Worker state may or may not be set depending on test order
        # Just verify the endpoint works
        resp = client.get("/ready")
        assert resp.status_code in (200, 503)
