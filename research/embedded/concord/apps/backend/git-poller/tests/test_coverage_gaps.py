"""Tests targeting uncovered lines to push coverage from 81% to ≥88%.

Gaps addressed:
- main.py: _setup_ssh_key (all branches), _run_health_server (GET paths)
- poller.py: run() loop, signal_shutdown(), _process_repo branch-SHA cache reuse
- trigger.py: non-JSON response (lines 97-99), _default_session_factory (23-25)
- discovery.py: boardRevisionId fallback (77-78), buildConfig default_board (56, 80),
  unexpected exception in _fetch (180-182), product without stageConfigs key
"""

from __future__ import annotations

import base64
import io
import stat
import threading
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import requests as req

from config import GitPollerConfig
from discovery import ProductDiscovery, _parse_watch_targets
from models import PRInfo, WatchTarget
from poller import GitPoller
from trigger import BuildTrigger


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> MagicMock:
    cfg = MagicMock(spec=GitPollerConfig)
    cfg.concord_api_url = "http://api:9001"
    cfg.concord_api_key = "ck_key"
    cfg.poll_interval = 5
    cfg.product_cache_ttl = 60
    cfg.ssh_key_path = "/tmp/key"
    cfg.bitbucket_workspace = "corekinect"
    cfg.bitbucket_email = "dev@example.com"
    cfg.bitbucket_api_token = "token"
    cfg.bitbucket_ssh_key = ""
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_api_session():
    session = MagicMock(spec=req.Session)
    load_resp = MagicMock()
    load_resp.status_code = 200
    load_resp.json.return_value = {"data": []}
    load_resp.raise_for_status = MagicMock()
    session.get.return_value = load_resp

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status = MagicMock()
    session.put.return_value = ok_resp
    session.delete.return_value = ok_resp
    return session


def _merge_target(repo_slug: str = "alpha_fw", stage: int = 5) -> WatchTarget:
    return WatchTarget(
        product_id="prod_1",
        repo_slug=repo_slug,
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=stage,
        watch_branch="concord-main",
        trigger_types=["pr_merge"],
    )


def _push_target(repo_slug: str = "alpha_fw", stage: int = 5) -> WatchTarget:
    return WatchTarget(
        product_id="prod_1",
        repo_slug=repo_slug,
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=stage,
        watch_branch="concord-main",
        trigger_types=["pr_push"],
    )


def _both_target(repo_slug: str = "alpha_fw", stage: int = 5) -> WatchTarget:
    return WatchTarget(
        product_id="prod_1",
        repo_slug=repo_slug,
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=stage,
        watch_branch="concord-main",
        trigger_types=["pr_merge", "pr_push"],
    )


# ---------------------------------------------------------------------------
# main._setup_ssh_key
# ---------------------------------------------------------------------------


class TestSetupSshKey:
    """Tests for the _setup_ssh_key function in main.py."""

    def _import(self):
        import importlib
        import main as _main
        importlib.reload(_main)  # ensure clean module state
        return _main

    def test_writes_key_to_disk_when_env_var_set(self, tmp_path, monkeypatch):
        """_setup_ssh_key decodes base64 key and writes it with 0o400 permissions."""
        import main as _main

        key_bytes = b"-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n"
        encoded = base64.b64encode(key_bytes).decode()
        key_path = tmp_path / ".ssh" / "id_ed25519"

        cfg = MagicMock()
        cfg.bitbucket_ssh_key = encoded
        cfg.ssh_key_path = str(key_path)

        monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)

        _main._setup_ssh_key(cfg)

        assert key_path.exists()
        assert key_path.read_bytes() == key_bytes
        assert key_path.stat().st_mode & 0o777 == stat.S_IRUSR

    def test_returns_early_when_ssh_agent_active(self, tmp_path, monkeypatch):
        """_setup_ssh_key skips file write when SSH_AUTH_SOCK points to a real socket."""
        import main as _main

        # Create a fake socket file
        sock = tmp_path / "ssh-agent.sock"
        sock.touch()

        key_path = tmp_path / "id_rsa"
        cfg = MagicMock()
        cfg.bitbucket_ssh_key = base64.b64encode(b"key").decode()
        cfg.ssh_key_path = str(key_path)

        monkeypatch.setenv("SSH_AUTH_SOCK", str(sock))

        _main._setup_ssh_key(cfg)

        # File must NOT have been created (agent path taken)
        assert not key_path.exists()

    def test_warns_when_no_key_and_file_missing(self, tmp_path, monkeypatch, caplog):
        """_setup_ssh_key logs a warning when key is absent and key file doesn't exist."""
        import main as _main
        import logging

        monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)

        missing_path = tmp_path / "nonexistent_key"
        cfg = MagicMock()
        cfg.bitbucket_ssh_key = ""
        cfg.ssh_key_path = str(missing_path)

        with caplog.at_level(logging.WARNING, logger="git-poller"):
            _main._setup_ssh_key(cfg)

        assert any("git operations will fail" in r.message for r in caplog.records)

    def test_no_warning_when_no_key_but_file_exists(self, tmp_path, monkeypatch, caplog):
        """_setup_ssh_key silently passes when key file already exists on disk."""
        import main as _main
        import logging

        monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)

        key_file = tmp_path / "existing_key"
        key_file.write_bytes(b"key_data")

        cfg = MagicMock()
        cfg.bitbucket_ssh_key = ""
        cfg.ssh_key_path = str(key_file)

        with caplog.at_level(logging.WARNING, logger="git-poller"):
            _main._setup_ssh_key(cfg)

        assert not any("git operations will fail" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# main._run_health_server (handler logic via direct invocation)
# ---------------------------------------------------------------------------


class TestHealthServerHandler:
    """Tests for the HTTP handler embedded inside _run_health_server."""

    def _make_handler(self, path: str):
        """Build the handler class and return an instance with mocked request."""
        import main as _main

        # _run_health_server defines _Handler inside it; we need to trigger it
        # by starting a real server on a free port and sending a real request.
        # Instead, we directly exercise the do_GET method by capturing what
        # _run_health_server's inner class would produce via a fake wfile.

        # We patch HTTPServer to intercept the handler class registration.
        captured: dict = {}

        class _FakeServer:
            def __init__(self, addr, handler_cls):
                captured["handler_cls"] = handler_cls

            def serve_forever(self):
                pass

        with patch("main.HTTPServer", _FakeServer):
            t = threading.Thread(target=_main._run_health_server, args=(19999,), daemon=True)
            t.start()
            t.join(timeout=0.5)

        handler_cls = captured["handler_cls"]

        # Construct a handler instance with minimal fakes
        req_mock = MagicMock()
        req_mock.makefile.return_value = io.BytesIO()

        handler = handler_cls.__new__(handler_cls)
        handler.path = path
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.log_message = MagicMock()

        return handler

    def test_health_endpoint_returns_200(self):
        """/health returns 200 with status ok."""
        import main as _main

        _main._ready = False
        handler = self._make_handler("/health")
        handler.do_GET()

        handler.send_response.assert_called_once_with(200)
        body = handler.wfile.getvalue().decode()
        assert "ok" in body

    def test_ready_endpoint_returns_503_when_not_ready(self):
        """/ready returns 503 before first poll completes."""
        import main as _main

        _main._ready = False
        handler = self._make_handler("/ready")
        handler.do_GET()

        handler.send_response.assert_called_once_with(503)
        body = handler.wfile.getvalue().decode()
        assert "not_ready" in body

    def test_ready_endpoint_returns_200_when_ready(self):
        """/ready returns 200 after _ready flag is set."""
        import main as _main

        _main._ready = True
        try:
            handler = self._make_handler("/ready")
            handler.do_GET()
            handler.send_response.assert_called_once_with(200)
        finally:
            _main._ready = False  # restore module state

    def test_unknown_path_returns_404(self):
        """Unrecognised paths return 404."""
        handler = self._make_handler("/nonexistent")
        handler.do_GET()

        handler.send_response.assert_called_once_with(404)


# ---------------------------------------------------------------------------
# poller.GitPoller.run() loop
# ---------------------------------------------------------------------------


class TestPollerRunLoop:
    """Tests for GitPoller.run() — the main polling loop."""

    def _make_poller(self, targets=None, branch_sha="abc", trigger_success=True):
        cfg = _make_config()
        api_session = _make_api_session()
        from state import PollerState

        with patch("poller.PollerState") as MockState:
            MockState.side_effect = lambda api_url, api_key: PollerState(
                api_url=api_url, api_key=api_key, session=api_session
            )
            poller = GitPoller(cfg)

        poller._discovery.get_watch_targets = MagicMock(return_value=targets or [])
        poller._branch_watcher.get_branch_sha = MagicMock(return_value=branch_sha)
        poller._pr_watcher.get_open_prs = MagicMock(return_value=[])
        poller._trigger.trigger_build = MagicMock(return_value=trigger_success)
        return poller

    def test_run_calls_on_first_success_once(self):
        """run() invokes on_first_success exactly once after first successful poll."""
        poller = self._make_poller(targets=[])
        callback = MagicMock()

        def _run():
            poller.run(on_first_success=callback)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        # Give it time to fire the callback, then shut down
        import time
        time.sleep(0.05)
        poller.signal_shutdown()
        t.join(timeout=2)

        callback.assert_called_once()

    def test_run_without_callback_does_not_raise(self):
        """run() is safe when on_first_success is None."""
        poller = self._make_poller(targets=[])

        def _run():
            poller.run(on_first_success=None)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        import time
        time.sleep(0.05)
        poller.signal_shutdown()
        t.join(timeout=2)
        # If no exception propagated, the thread should have exited cleanly

    def test_run_continues_after_poll_exception(self):
        """run() catches exceptions from poll_once() and keeps looping."""
        poller = self._make_poller(targets=[])
        # Override poll_interval so the wait between cycles is tiny
        poller._config.poll_interval = 0

        original_poll = poller.poll_once
        call_count = [0]

        def _flaky_poll():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("transient error")
            original_poll()

        poller.poll_once = _flaky_poll

        import time
        t = threading.Thread(target=lambda: poller.run(on_first_success=None), daemon=True)
        t.start()
        # With poll_interval=0, second iteration fires almost immediately
        time.sleep(0.3)
        poller.signal_shutdown()
        t.join(timeout=2)

        assert call_count[0] >= 2, "run() should have called poll_once at least twice"

    def test_signal_shutdown_stops_run_loop(self):
        """signal_shutdown() causes run() to exit within poll_interval."""
        poller = self._make_poller(targets=[])

        import time
        start = time.monotonic()
        t = threading.Thread(target=lambda: poller.run(), daemon=True)
        t.start()
        time.sleep(0.05)
        poller.signal_shutdown()
        t.join(timeout=3)
        elapsed = time.monotonic() - start

        assert not t.is_alive(), "run() did not exit after signal_shutdown()"
        # Should have stopped well before a full poll_interval (5s)
        assert elapsed < 3


# ---------------------------------------------------------------------------
# poller._process_repo — branch SHA cache reuse
# ---------------------------------------------------------------------------


class TestProcessRepoBranchShaCache:
    """Tests that _process_repo reuses already-fetched branch SHAs."""

    def _make_poller(self, targets, branch_sha="cached_sha", trigger_success=True):
        cfg = _make_config()
        api_session = _make_api_session()
        from state import PollerState

        with patch("poller.PollerState") as MockState:
            MockState.side_effect = lambda api_url, api_key: PollerState(
                api_url=api_url, api_key=api_key, session=api_session
            )
            poller = GitPoller(cfg)

        poller._discovery.get_watch_targets = MagicMock(return_value=targets)
        poller._branch_watcher.get_branch_sha = MagicMock(return_value=branch_sha)
        poller._pr_watcher.get_open_prs = MagicMock(return_value=[])
        poller._trigger.trigger_build = MagicMock(return_value=trigger_success)
        return poller

    def test_branch_sha_fetched_once_when_merge_and_push_share_branch(self):
        """When both merge and push targets watch the same branch, SHA is only fetched once."""
        # A target with BOTH trigger types shares the same (ssh_url, branch) key
        target = _both_target()
        poller = self._make_poller(targets=[target])
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")

        poller.poll_once()

        # get_branch_sha should have been called exactly once for the branch
        assert poller._branch_watcher.get_branch_sha.call_count == 1

    def test_push_target_reuses_sha_already_fetched_by_merge_target(self):
        """Push target for same (ssh_url, branch) must not re-fetch the SHA."""
        # Two separate targets watching the same repo/branch — one merge, one push
        merge = _merge_target()
        push = _push_target()

        poller = self._make_poller(targets=[merge, push])
        # Set old SHA so merge path tries to trigger
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")
        poller._pr_watcher.get_open_prs = MagicMock(
            return_value=[
                PRInfo(
                    pr_id=7,
                    title="t",
                    source_branch="feat/x",
                    target_branch="concord-main",
                    head_sha="pr_head_sha",
                    author="dev",
                )
            ]
        )

        poller.poll_once()

        # Despite two targets, get_branch_sha should only be called once
        assert poller._branch_watcher.get_branch_sha.call_count == 1


# ---------------------------------------------------------------------------
# trigger.py — non-JSON response body (lines 97-99)
# ---------------------------------------------------------------------------


class TestBuildTriggerNonJsonResponse:
    """Tests for trigger.py edge cases not covered by test_trigger.py."""

    def _make_target(self):
        return WatchTarget(
            product_id="prod_abc",
            repo_slug="alpha_fw",
            ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
            board="alpha_b0",
            stage=5,
            watch_branch="concord-main",
            trigger_types=["pr_merge"],
        )

    def test_returns_true_when_response_body_is_not_json(self):
        """trigger_build returns True for a 200 with non-JSON body (lines 97-99)."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("no JSON")
        session = MagicMock()
        session.post.return_value = resp

        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(self._make_target(), "abc123", "pr_merge")

        assert result is True

    def test_returns_true_when_errors_list_is_empty(self):
        """trigger_build returns True when errors key is present but list is empty."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"triggered": 0, "stages": []}, "errors": []}
        session = MagicMock()
        session.post.return_value = resp

        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(self._make_target(), "abc123", "pr_merge")

        assert result is True

    def test_returns_true_when_errors_list_has_entries_without_message(self):
        """trigger_build returns True when error entries have no 'message' field."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": {"triggered": 1, "stages": []},
            "errors": [{"code": "WARN_SOMETHING"}],  # no 'message'
        }
        session = MagicMock()
        session.post.return_value = resp

        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(self._make_target(), "abc123", "pr_merge")

        assert result is True

    def test_default_session_factory_is_callable(self):
        """_default_session_factory returns a requests.Session (lines 23-25)."""
        from trigger import _default_session_factory

        # urllib3 is imported inside the function body, so patch it at the
        # urllib3 module level (not as a trigger attribute)
        with patch("urllib3.disable_warnings") as mock_disable:
            session = _default_session_factory()

        assert isinstance(session, req.Session)
        mock_disable.assert_called_once()


# ---------------------------------------------------------------------------
# discovery._parse_watch_targets — board resolution fallbacks
# ---------------------------------------------------------------------------


class TestParseWatchTargetsBoardFallbacks:
    """Tests for board name resolution paths not hit by existing tests."""

    def _base_product(self):
        return {
            "id": "prod_1",
            "active": True,
            "fwRepoSlug": "alpha_fw",
            "repoSshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
        }

    def test_board_from_revision_id_when_no_board_revision_object(self):
        """Board is resolved via boardRevisionId + product.revisions[] (lines 77-78)."""
        product = self._base_product()
        product["revisions"] = [{"id": "rev_42", "ckBoardsName": "alpha_b0"}]
        product["stageConfigs"] = [
            {
                "enabled": True,
                "stage": 5,
                "watchBranch": "concord-main",
                "triggerTypes": ["pr_merge"],
                "boardRevisionId": "rev_42",
                # boardRevision key absent — forces fallback to revisionId lookup
            }
        ]
        targets = _parse_watch_targets([product])
        assert len(targets) == 1
        assert targets[0].board == "alpha_b0"

    def test_board_from_build_config_when_all_revision_lookups_fail(self):
        """Board falls back to buildConfig.board when revision lookup yields nothing (lines 56, 80)."""
        product = self._base_product()
        product["buildConfig"] = {"board": "fallback_board"}
        product["stageConfigs"] = [
            {
                "enabled": True,
                "stage": 5,
                "watchBranch": "concord-main",
                "triggerTypes": ["pr_merge"],
                # No boardRevision, no boardRevisionId
            }
        ]
        targets = _parse_watch_targets([product])
        assert len(targets) == 1
        assert targets[0].board == "fallback_board"

    def test_product_without_stage_configs_key_returns_empty(self):
        """Product dict with no stageConfigs key at all produces no targets."""
        product = self._base_product()
        # Omit stageConfigs entirely (not even None — key not present)
        targets = _parse_watch_targets([product])
        assert targets == []

    def test_product_with_only_disabled_stages_returns_empty(self):
        """Product with stageConfigs but all stages disabled produces no targets."""
        product = self._base_product()
        product["stageConfigs"] = [
            {
                "enabled": False,
                "stage": 5,
                "watchBranch": "concord-main",
                "triggerTypes": ["pr_merge"],
                "boardRevision": {"ckBoardsName": "alpha_b0"},
            }
        ]
        targets = _parse_watch_targets([product])
        assert targets == []


# ---------------------------------------------------------------------------
# discovery.ProductDiscovery._fetch — unexpected exception path
# ---------------------------------------------------------------------------


class TestProductDiscoveryUnexpectedException:
    """Tests for the bare-except branch in _fetch (lines 180-182)."""

    def test_returns_empty_on_unexpected_json_decode_error(self):
        """_fetch returns empty list when resp.json() raises an unexpected exception."""
        with patch("discovery.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.side_effect = Exception("unexpected decode failure")
            mock_get.return_value = resp

            disc = ProductDiscovery("http://api:9001", "ck_key", cache_ttl=0)
            targets = disc.get_watch_targets()

        assert targets == []

    def test_stale_cache_returned_when_fetch_fails_and_cache_exists(self):
        """get_watch_targets returns stale cache when fetch fails (not None branch)."""
        stale_product = {
            "id": "prod_1",
            "active": True,
            "fwRepoSlug": "alpha_fw",
            "repoSshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
            "stageConfigs": [
                {
                    "enabled": True,
                    "stage": 5,
                    "watchBranch": "concord-main",
                    "triggerTypes": ["pr_merge"],
                    "boardRevision": {"ckBoardsName": "alpha_b0"},
                }
            ],
        }

        with patch("discovery.requests.get") as mock_get:
            # First call succeeds — populates cache
            ok_resp = MagicMock()
            ok_resp.status_code = 200
            ok_resp.json.return_value = {"data": {"data": [stale_product], "pagination": {}}}

            # Second call fails
            fail_resp = MagicMock()
            fail_resp.status_code = 500
            fail_resp.text = "internal error"

            mock_get.side_effect = [ok_resp, fail_resp]

            disc = ProductDiscovery("http://api:9001", "ck_key", cache_ttl=0)
            first = disc.get_watch_targets()
            second = disc.get_watch_targets()

        assert len(first) == 1
        # Stale cache is returned when fetch fails
        assert second == first
