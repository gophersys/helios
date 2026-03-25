"""Tests for the ConcordReporter pytest plugin.

These tests verify:
1. Reporter is inactive when CONCORD_RUN_ID is not set.
2. Reporter makes correct HTTP calls when active.
3. Reporter never causes test failures (error resilience).
4. Module-level pytest_configure auto-registers when env is set.

All tests mock HTTP calls — no real API needed.

Note: We load reporter.py via importlib to avoid the broken
corekinect.test.__init__.py import chain (missing mtib_runner dep).
The reporter module itself only depends on stdlib + requests + pytest.

We mock `requests` by replacing the module attribute on the loaded module
rather than using @patch("corekinect.test.reporter.requests"),
because the string-based patch triggers the broken package __init__.py.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Module loader ────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[5]  # lib → tests → http-api → backend → apps → repo
_REPORTER_PATH = _REPO_ROOT / "libs" / "python" / "corekinect" / "test" / "reporter.py"

_MOD_NAME = "corekinect.test.reporter"


def _load_reporter():
    """Load reporter module directly by file path, bypassing corekinect.test.__init__.py."""
    sys.modules.pop(_MOD_NAME, None)

    spec = importlib.util.spec_from_file_location(_MOD_NAME, _REPORTER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Inactive (offline mode) ──────────────────────────────


def test_reporter_inactive_by_default():
    """Reporter is disabled when CONCORD_RUN_ID is not set."""
    env = {k: v for k, v in os.environ.items() if k != "CONCORD_RUN_ID"}
    with patch.dict(os.environ, env, clear=True):
        mod = _load_reporter()
        reporter = mod.ConcordReporter()
        assert reporter.enabled is False


def test_reporter_inactive_without_api_url():
    """Reporter is disabled when CONCORD_API_URL is missing."""
    env = {k: v for k, v in os.environ.items() if k != "CONCORD_API_URL"}
    env["CONCORD_RUN_ID"] = "run-1"
    with patch.dict(os.environ, env, clear=True):
        mod = _load_reporter()
        reporter = mod.ConcordReporter()
        assert reporter.enabled is False


def test_reporter_noop_when_inactive():
    """Inactive reporter's hooks do nothing (no HTTP calls)."""
    env = {k: v for k, v in os.environ.items() if k != "CONCORD_RUN_ID"}
    with patch.dict(os.environ, env, clear=True):
        mod = _load_reporter()
        reporter = mod.ConcordReporter()

        # These should all be no-ops
        reporter.pytest_sessionstart(MagicMock())
        reporter.pytest_runtest_logstart("test_foo", ("file", 1, "test_foo"))
        reporter.pytest_sessionfinish(MagicMock(), 0)


# ── Active mode ───────────────────────────────────────────


@pytest.fixture
def reporter_mod():
    """Load the reporter module with mocked HTTP and active env."""
    env = {
        "CONCORD_RUN_ID": "run-123",
        "CONCORD_API_URL": "http://localhost:9001",
        "CONCORD_API_KEY": "test-key",
    }
    with patch.dict(os.environ, env):
        mod = _load_reporter()
        mock_requests = MagicMock()
        mod.requests = mock_requests
        yield mod, mock_requests


@pytest.fixture
def active_reporter(reporter_mod):
    """Create an active reporter with mocked HTTP."""
    mod, _ = reporter_mod
    reporter = mod.ConcordReporter()
    assert reporter.enabled is True
    return reporter


@pytest.fixture
def mock_requests(reporter_mod):
    """Get the mocked requests module."""
    _, mock_req = reporter_mod
    return mock_req


def _setup_ok_response(mock_requests, json_data=None):
    """Configure mock_requests.post to return a 200 OK response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data or {"data": {}}
    mock_requests.post.return_value = resp
    return resp


def test_reporter_active_with_env(active_reporter):
    """Reporter is enabled when both CONCORD_RUN_ID and CONCORD_API_URL are set."""
    assert active_reporter.run_id == "run-123"
    assert active_reporter.api_url == "http://localhost:9001"
    assert active_reporter.api_key == "test-key"


def test_session_start_posts(active_reporter, mock_requests):
    """pytest_sessionstart posts to /report/start."""
    _setup_ok_response(mock_requests, {"data": {"status": "ACTIVE"}})

    active_reporter.pytest_sessionstart(MagicMock())

    mock_requests.post.assert_called_once()
    url = mock_requests.post.call_args[0][0]
    assert url == "http://localhost:9001/v2/sessions/run-123/report/start"
    assert mock_requests.post.call_args[1]["json"] == {"started": True}


def test_test_start_posts(active_reporter, mock_requests):
    """pytest_runtest_logstart posts to /report/test-start."""
    _setup_ok_response(mock_requests)

    active_reporter.pytest_runtest_logstart(
        "tests/stage4/test_boot.py::test_power_cycle",
        ("tests/stage4/test_boot.py", 10, "test_power_cycle"),
    )

    mock_requests.post.assert_called_once()
    json_data = mock_requests.post.call_args[1]["json"]
    assert json_data["testName"] == "test_power_cycle"
    assert json_data["module"] == "test_boot"


def test_session_finish_posts(active_reporter, mock_requests):
    """pytest_sessionfinish posts to /report/finish with accumulated counts."""
    _setup_ok_response(mock_requests)

    # Simulate some test results
    active_reporter._total = 10
    active_reporter._passed = 8
    active_reporter._failed = 1
    active_reporter._errors = 1
    active_reporter._start_time = 0  # monotonic start

    active_reporter.pytest_sessionfinish(MagicMock(), 0)

    mock_requests.post.assert_called_once()
    json_data = mock_requests.post.call_args[1]["json"]
    assert json_data["total"] == 10
    assert json_data["passed"] == 8
    assert json_data["failed"] == 1
    assert json_data["errors"] == 1
    assert json_data["durationS"] is not None


def test_auth_header_sent(active_reporter, mock_requests):
    """API key is sent as Authorization: ApiKey header."""
    _setup_ok_response(mock_requests)

    active_reporter.pytest_sessionstart(MagicMock())

    headers = mock_requests.post.call_args[1]["headers"]
    assert headers["Authorization"] == "ApiKey test-key"
    assert headers["Content-Type"] == "application/json"


# ── Error resilience ──────────────────────────────────────


def test_reporter_survives_connection_error(active_reporter, mock_requests):
    """Reporter logs warning but doesn't raise when API is unreachable."""
    mock_requests.post.side_effect = ConnectionError("Connection refused")

    # Should not raise
    active_reporter.pytest_sessionstart(MagicMock())
    active_reporter.pytest_runtest_logstart("test_foo", ("file", 1, "test_foo"))
    active_reporter.pytest_sessionfinish(MagicMock(), 0)


def test_reporter_survives_http_error(active_reporter, mock_requests):
    """Reporter logs warning but doesn't raise on HTTP 500."""
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "Internal Server Error"
    mock_requests.post.return_value = resp

    # Should not raise
    active_reporter.pytest_sessionstart(MagicMock())


def test_reporter_survives_timeout(active_reporter, mock_requests):
    """Reporter logs warning but doesn't raise on timeout."""
    import requests as real_requests
    mock_requests.post.side_effect = real_requests.exceptions.Timeout("Timeout")

    # Should not raise
    active_reporter.pytest_sessionstart(MagicMock())


# ── pytest_configure registration ─────────────────────────


def test_pytest_configure_registers_when_env_set():
    """pytest_configure registers the plugin when CONCORD_RUN_ID is set."""
    with patch.dict(os.environ, {
        "CONCORD_RUN_ID": "run-99",
        "CONCORD_API_URL": "http://localhost:9001",
    }):
        mod = _load_reporter()
        mock_config = MagicMock()
        mod.pytest_configure(mock_config)
        mock_config.pluginmanager.register.assert_called_once()
        args = mock_config.pluginmanager.register.call_args
        assert args[1] == "concord_reporter" or args[0][1] == "concord_reporter"


def test_pytest_configure_skips_when_no_env():
    """pytest_configure does nothing when CONCORD_RUN_ID is not set."""
    env = {k: v for k, v in os.environ.items() if k != "CONCORD_RUN_ID"}
    with patch.dict(os.environ, env, clear=True):
        mod = _load_reporter()
        mock_config = MagicMock()
        mod.pytest_configure(mock_config)
        mock_config.pluginmanager.register.assert_not_called()
