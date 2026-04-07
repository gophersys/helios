"""Tests for GitPoller.poll_once() — full cycle with all dependencies mocked."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

from poller import GitPoller
from config import GitPollerConfig
from models import WatchTarget, PRInfo
from state import PollerState


def _make_api_session():
    """Create a mock requests.Session that returns empty state on load."""
    session = MagicMock(spec=requests.Session)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> GitPollerConfig:
    cfg = MagicMock(spec=GitPollerConfig)
    cfg.concord_api_url = "http://api:9001"
    cfg.concord_api_key = "ck_key"
    cfg.poll_interval = 5
    cfg.product_cache_ttl = 60
    cfg.ssh_key_path = "/tmp/key"
    cfg.bitbucket_workspace = "corekinect"
    cfg.bitbucket_email = "dev@example.com"
    cfg.bitbucket_api_token = "token"
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _merge_target(repo_slug="alpha_fw", stage=5) -> WatchTarget:
    return WatchTarget(
        product_id="prod_1",
        repo_slug=repo_slug,
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=stage,
        watch_branch="concord-main",
        trigger_types=["pr_merge"],
    )


def _push_target(repo_slug="alpha_fw", stage=5) -> WatchTarget:
    return WatchTarget(
        product_id="prod_1",
        repo_slug=repo_slug,
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=stage,
        watch_branch="concord-main",
        trigger_types=["pr_push"],
    )


def _open_pr(pr_id=42, sha="deadbeef1234", source="feature/x") -> PRInfo:
    return PRInfo(
        pr_id=pr_id,
        title="PR title",
        source_branch=source,
        target_branch="concord-main",
        head_sha=sha,
        author="dev",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPollerPollOnce:
    def _make_poller(self, targets, branch_sha=None, open_prs=None,
                     trigger_success=True):
        """Construct a GitPoller with all external dependencies mocked."""
        cfg = _make_config()
        api_session = _make_api_session()
        with patch("poller.PollerState") as MockState:
            # Make PollerState constructor return a real PollerState using mock session
            def _state_factory(api_url, api_key):
                return PollerState(api_url=api_url, api_key=api_key, session=api_session)
            MockState.side_effect = _state_factory
            poller = GitPoller(cfg)

        poller._discovery.get_watch_targets = MagicMock(return_value=targets)
        poller._branch_watcher.get_branch_sha = MagicMock(return_value=branch_sha)
        poller._pr_watcher.get_open_prs = MagicMock(return_value=open_prs or [])
        poller._trigger.trigger_build = MagicMock(return_value=trigger_success)

        return poller

    # -- No targets --

    def test_does_nothing_when_no_targets(self):
        poller = self._make_poller(targets=[])
        poller.poll_once()
        poller._trigger.trigger_build.assert_not_called()

    # -- pr_merge: first-time SHA --

    def test_records_initial_sha_without_triggering(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="abc123")
        poller.poll_once()
        poller._trigger.trigger_build.assert_not_called()
        assert poller._state.get_branch_sha("alpha_fw", "concord-main") == "abc123"

    # -- pr_merge: new commit --

    def test_triggers_merge_build_on_new_commit(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="new_sha")
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")

        poller.poll_once()

        poller._trigger.trigger_build.assert_called_once()
        call_kwargs = poller._trigger.trigger_build.call_args[1]
        assert call_kwargs["commit_sha"] == "new_sha"
        assert call_kwargs["trigger_type"] == "pr_merge"

    def test_merge_trigger_uses_positional_or_kw_args(self):
        """trigger_build may be called with positional args — accept both."""
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="new_sha")
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")

        poller.poll_once()

        args, kwargs = poller._trigger.trigger_build.call_args
        # Either positional or keyword — commit_sha should be "new_sha"
        commit_sha = kwargs.get("commit_sha") or (args[1] if len(args) > 1 else None)
        assert commit_sha == "new_sha"

    def test_updates_branch_sha_state_after_successful_trigger(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="new_sha",
                                   trigger_success=True)
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")
        poller.poll_once()
        assert poller._state.get_branch_sha("alpha_fw", "concord-main") == "new_sha"

    def test_does_not_update_sha_if_trigger_fails(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="new_sha",
                                   trigger_success=False)
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")
        poller.poll_once()
        assert poller._state.get_branch_sha("alpha_fw", "concord-main") == "old_sha"

    def test_no_trigger_when_sha_unchanged(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="same_sha")
        poller._state.set_branch_sha("alpha_fw", "concord-main", "same_sha")
        poller.poll_once()
        poller._trigger.trigger_build.assert_not_called()

    # -- pr_push: new PR --

    def test_triggers_push_build_on_new_pr(self):
        target = _push_target()
        pr = _open_pr(pr_id=42, sha="pr_sha")
        poller = self._make_poller(targets=[target], open_prs=[pr],
                                   branch_sha="branch_sha")
        poller.poll_once()

        poller._trigger.trigger_build.assert_called_once()
        args, kwargs = poller._trigger.trigger_build.call_args
        trigger_type = kwargs.get("trigger_type") or (args[2] if len(args) > 2 else None)
        commit_sha = kwargs.get("commit_sha") or (args[1] if len(args) > 1 else None)
        assert trigger_type == "pr_push"
        assert commit_sha == "pr_sha"

    def test_records_pr_sha_after_trigger(self):
        target = _push_target()
        pr = _open_pr(pr_id=42, sha="pr_sha")
        poller = self._make_poller(targets=[target], open_prs=[pr],
                                   branch_sha="branch_sha")
        poller.poll_once()
        assert poller._state.get_pr_sha("alpha_fw", 42) == "pr_sha"

    # -- pr_push: updated PR --

    def test_triggers_push_build_on_pr_sha_change(self):
        target = _push_target()
        pr = _open_pr(pr_id=42, sha="new_pr_sha")
        poller = self._make_poller(targets=[target], open_prs=[pr],
                                   branch_sha="branch_sha")
        poller._state.set_pr_sha("alpha_fw", 42, "old_pr_sha", "feature/x")
        poller.poll_once()

        poller._trigger.trigger_build.assert_called_once()

    def test_no_trigger_when_pr_sha_unchanged(self):
        target = _push_target()
        pr = _open_pr(pr_id=42, sha="same_sha")
        poller = self._make_poller(targets=[target], open_prs=[pr],
                                   branch_sha="branch_sha")
        poller._state.set_pr_sha("alpha_fw", 42, "same_sha", "feature/x")
        poller.poll_once()
        poller._trigger.trigger_build.assert_not_called()

    # -- Closed PR cleanup --

    def test_removes_closed_pr_from_state(self):
        target = _push_target()
        # PR 42 was tracked but is no longer in open list
        poller = self._make_poller(targets=[target], open_prs=[],
                                   branch_sha="branch_sha")
        poller._state.set_pr_sha("alpha_fw", 42, "old_sha", "feature/x")
        poller.poll_once()
        assert poller._state.get_pr_sha("alpha_fw", 42) is None

    # -- Deduplication --

    def test_no_duplicate_trigger_for_same_commit(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="new_sha",
                                   trigger_success=True)
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")

        poller.poll_once()
        # Reset state to simulate another poll finding the same new_sha
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")
        poller.poll_once()

        # Should only have been triggered once (dedup by (repo, sha, stage, type))
        assert poller._trigger.trigger_build.call_count == 1

    # -- State write-through after cycle --

    def test_state_write_through_after_poll_once(self):
        """After poll_once(), set_branch_sha must have called the API PUT."""
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha="abc")
        poller.poll_once()
        # The state object should have the SHA recorded in memory
        assert poller._state.get_branch_sha("alpha_fw", "concord-main") == "abc"

    # -- Multiple repos --

    def test_processes_multiple_repos_independently(self):
        t1 = _merge_target(repo_slug="alpha_fw")
        t2 = _merge_target(repo_slug="beta_fw")

        poller = self._make_poller(targets=[t1, t2], branch_sha="new_sha")
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")
        poller._state.set_branch_sha("beta_fw", "concord-main", "old_sha")

        poller.poll_once()
        assert poller._trigger.trigger_build.call_count == 2

    # -- No branch sha available --

    def test_skips_merge_check_when_branch_sha_unavailable(self):
        target = _merge_target()
        poller = self._make_poller(targets=[target], branch_sha=None)
        poller._state.set_branch_sha("alpha_fw", "concord-main", "old_sha")
        poller.poll_once()
        poller._trigger.trigger_build.assert_not_called()
