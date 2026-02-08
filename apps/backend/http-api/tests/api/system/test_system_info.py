"""
Integration tests for GET /v2/system/info.

This endpoint has no auth requirement — it returns build metadata
useful for debugging and version display in the frontend.
"""

import json
from unittest.mock import patch, MagicMock

from corekinect.utils import BuildInfo


def test_system_info_returns_200(client):
    """GET /v2/system/info should return 200 with build metadata."""
    mock_info = BuildInfo(
        service="concord-http-api",
        version="1.2.3-abc1234",
        environment="test",
        git_commit="abc1234",
        git_branch="main",
        git_dirty=False,
        build_time="2026-01-15T10:30:00Z",
        build_host="build-server",
        python_version="3.12.0",
        arch="x86_64",
        os_info="Alpine Linux v3.19",
    )

    with patch("api.v2.system.info.collect_build_info", return_value=mock_info):
        response = client.get("/v2/system/info")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["service"] == "concord-http-api"
    assert data["data"]["version"] == "1.2.3-abc1234"
    assert data["data"]["environment"] == "test"
    assert data["data"]["gitCommit"] == "abc1234"
    assert data["data"]["gitBranch"] == "main"
    assert data["data"]["gitDirty"] is False
    assert data["data"]["buildTime"] == "2026-01-15T10:30:00Z"
    assert data["data"]["buildHost"] == "build-server"
    assert data["data"]["pythonVersion"] == "3.12.0"
    assert data["data"]["arch"] == "x86_64"
    assert data["data"]["os"] == "Alpine Linux v3.19"
    assert data["errors"] == []


def test_system_info_no_auth_required(client):
    """GET /v2/system/info should work without any Authorization header."""
    mock_info = BuildInfo(service="concord-http-api")

    with patch("api.v2.system.info.collect_build_info", return_value=mock_info):
        response = client.get("/v2/system/info")

    assert response.status_code == 200


def test_system_info_dirty_flag(client):
    """git_dirty should come through as a boolean."""
    mock_info = BuildInfo(
        service="concord-http-api",
        git_dirty=True,
    )

    with patch("api.v2.system.info.collect_build_info", return_value=mock_info):
        response = client.get("/v2/system/info")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["gitDirty"] is True


def test_system_info_handles_exception(client):
    """If collect_build_info raises, endpoint should return 500."""
    with patch("api.v2.system.info.collect_build_info", side_effect=RuntimeError("boom")):
        response = client.get("/v2/system/info")

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["data"] is None
    assert len(data["errors"]) > 0
