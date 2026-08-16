"""Shared fixtures for build-service tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# config fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def config(monkeypatch):
    """BuildServiceConfig loaded from deterministic dummy env vars."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("CONCORD_API_URL", "https://test.concord.local")
    monkeypatch.setenv("CONCORD_API_KEY", "test-api-key-123")
    monkeypatch.setenv("WORKER_ID", "test-worker-01")
    monkeypatch.setenv("POLL_INTERVAL", "5")
    monkeypatch.setenv("WORKSPACE_DIR", "/tmp/test-builds")
    monkeypatch.setenv("BUILD_SERVICE_PORT", "9002")
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("BUILDER_MODE", "local")
    monkeypatch.setenv("DOCKER_SOCKET", "/var/run/docker.sock")
    monkeypatch.setenv("BUILDER_TIMEOUT", "1800")
    monkeypatch.setenv("DEFAULT_BUILDER_IMAGE", "containers.ad.corekinect.com/ncs-fw-dev:2.7.0")
    monkeypatch.setenv("WORKSPACE_VOLUME", "")
    monkeypatch.setenv("CCACHE_VOLUME", "")
    monkeypatch.setenv("BUILDER_NETWORK", "host")
    monkeypatch.setenv("SSH_KEY_PATH", "/root/.ssh/id_rsa")
    monkeypatch.setenv("BITBUCKET_SSH_KEY", "")
    monkeypatch.setenv("BENCH_SIGNING_KEY", "bench-b64-key==")
    monkeypatch.setenv("ENGINEERING_SIGNING_KEY", "engineering-b64-key==")
    monkeypatch.setenv("PRODUCTION_SIGNING_KEY", "production-b64-key==")

    from src.config import BuildServiceConfig
    return BuildServiceConfig(auto_load_env=False)


# ---------------------------------------------------------------------------
# sample_job fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_job():
    """A BuildJob instance with sensible defaults for testing."""
    from src.worker.executor import BuildJob
    return BuildJob(
        id="job-abc-def-123",
        product="alpha",
        board="alpha_b0",
        target="app",
        variant="release",
        branch="main",
        commit_sha="deadbeef01234567",
        status="QUEUED",
        version_bump=False,
        base_job_id=None,
        matrix_label=None,
        version_override=None,
        config_flags={},
        product_id="prod-xyz-001",
        recipe_version_id=None,
        stage=3,
    )


# ---------------------------------------------------------------------------
# sample_build_config fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_build_config() -> Dict[str, Any]:
    """A representative Product.buildConfig dict with targets, cfw, ncsVersion."""
    return {
        "targets": [
            {
                "name": "app",
                "role": "app",
                "appId": 109,
                "processor": "nrf52840",
            },
            {
                "name": "comms",
                "role": "comms",
                "appId": 108,
                "processor": "nrf9151",
            },
        ],
        "cfw": {
            "deviceTypeId": 2,
            "deviceVariantId": 3,
            "apiEnv": "val",
        },
        "ncsVersion": "2.7.0",
        "releaseTrack": "bench",
    }


# ---------------------------------------------------------------------------
# temp_workspace fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Temporary workspace directory mirroring build worker layout."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "scripts").mkdir()
    (ws / "artifacts").mkdir()
    return ws


# ---------------------------------------------------------------------------
# mock_api_client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_api_client() -> MagicMock:
    """MagicMock of ConcordClient with sensible return values."""
    from src.clients.concord import ConcordClient
    mock = MagicMock(spec=ConcordClient)
    mock.api_get.return_value = None
    mock.api_post.return_value = None
    mock.api_patch.return_value = {}
    mock.upload_file.return_value = True
    mock.stream_log_chunk.return_value = None
    mock.heartbeat.return_value = None
    return mock
