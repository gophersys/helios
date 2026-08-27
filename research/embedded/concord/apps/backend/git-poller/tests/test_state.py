"""Tests for API-backed PollerState."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from state import PollerState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_URL = "http://api:9001"
API_KEY = "ck_test_key"


def _make_session(load_entries=None, upsert_ok=True, delete_ok=True):
    """Build a mock requests.Session that returns canned responses."""
    session = MagicMock(spec=requests.Session)

    # GET response — load
    load_resp = MagicMock()
    load_resp.status_code = 200
    load_resp.json.return_value = {"data": load_entries or []}
    load_resp.raise_for_status = MagicMock()

    # PUT response — upsert
    put_resp = MagicMock()
    put_resp.status_code = 200 if upsert_ok else 500
    put_resp.raise_for_status = MagicMock(
        side_effect=None if upsert_ok else requests.HTTPError("500")
    )

    # DELETE response — delete
    del_resp = MagicMock()
    del_resp.status_code = 200 if delete_ok else 500
    del_resp.raise_for_status = MagicMock(
        side_effect=None if delete_ok else requests.HTTPError("500")
    )

    session.get.return_value = load_resp
    session.put.return_value = put_resp
    session.delete.return_value = del_resp

    return session


def _state(load_entries=None, upsert_ok=True, delete_ok=True) -> tuple[PollerState, MagicMock]:
    session = _make_session(load_entries, upsert_ok, delete_ok)
    s = PollerState(api_url=API_URL, api_key=API_KEY, session=session)
    return s, session


def _branch_entry(repo="alpha_fw", ref_id="concord-main", sha="abc123"):
    return {
        "id": "pc-1",
        "repoSlug": repo,
        "type": "branch",
        "refId": ref_id,
        "commitSha": sha,
        "metadata": None,
    }


def _pr_entry(repo="alpha_fw", ref_id="42", sha="def456", source="feature/x"):
    return {
        "id": "pc-2",
        "repoSlug": repo,
        "type": "pr",
        "refId": ref_id,
        "commitSha": sha,
        "metadata": {"source_branch": source},
    }


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

class TestPollerStateLoad:
    def test_load_empty_api_starts_fresh(self):
        state, _ = _state(load_entries=[])
        assert state.get_tracked_pr_ids("alpha_fw") == set()

    def test_load_populates_branch_cache(self):
        state, _ = _state(load_entries=[
            _branch_entry(sha="abc123"),
        ])
        assert state.get_branch_sha("alpha_fw", "concord-main") == "abc123"

    def test_load_populates_pr_cache(self):
        state, _ = _state(load_entries=[
            _pr_entry(ref_id="42", sha="def456", source="feature/x"),
        ])
        assert state.get_pr_sha("alpha_fw", 42) == "def456"
        assert state.get_pr_source_branch("alpha_fw", 42) == "feature/x"

    def test_load_populates_multiple_repos(self):
        state, _ = _state(load_entries=[
            _branch_entry(repo="alpha_fw", sha="aaaa"),
            _branch_entry(repo="beta_fw", ref_id="main", sha="bbbb"),
        ])
        assert state.get_branch_sha("alpha_fw", "concord-main") == "aaaa"
        assert state.get_branch_sha("beta_fw", "main") == "bbbb"

    def test_load_api_failure_starts_fresh(self):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("unreachable")
        state = PollerState(api_url=API_URL, api_key=API_KEY, session=session)
        assert state.get_branch_sha("alpha_fw", "main") is None

    def test_load_sends_correct_headers(self):
        state, session = _state()
        call_kwargs = session.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == f"ApiKey {API_KEY}"

    def test_load_hits_correct_url(self):
        state, session = _state()
        call_args = session.get.call_args[0]
        assert call_args[0] == f"{API_URL}/v2/system/poller-state"


# ---------------------------------------------------------------------------
# Branch tracking
# ---------------------------------------------------------------------------

class TestPollerStateBranches:
    def test_get_branch_sha_missing_returns_none(self):
        state, _ = _state()
        assert state.get_branch_sha("alpha_fw", "concord-main") is None

    def test_set_and_get_branch_sha(self):
        state, _ = _state()
        state.set_branch_sha("alpha_fw", "concord-main", "aabbcc")
        assert state.get_branch_sha("alpha_fw", "concord-main") == "aabbcc"

    def test_set_branch_sha_overwrites(self):
        state, _ = _state()
        state.set_branch_sha("alpha_fw", "concord-main", "aabbcc")
        state.set_branch_sha("alpha_fw", "concord-main", "ddeeff")
        assert state.get_branch_sha("alpha_fw", "concord-main") == "ddeeff"

    def test_multiple_repos_isolated(self):
        state, _ = _state()
        state.set_branch_sha("alpha_fw", "main", "aaaa")
        state.set_branch_sha("beta_fw", "main", "bbbb")
        assert state.get_branch_sha("alpha_fw", "main") == "aaaa"
        assert state.get_branch_sha("beta_fw", "main") == "bbbb"

    def test_set_branch_sha_calls_api_put(self):
        state, session = _state()
        state.set_branch_sha("alpha_fw", "concord-main", "sha123")

        session.put.assert_called_once()
        call_kwargs = session.put.call_args[1]
        payload = call_kwargs["json"]
        assert payload["repoSlug"] == "alpha_fw"
        assert payload["type"] == "branch"
        assert payload["refId"] == "concord-main"
        assert payload["commitSha"] == "sha123"

    def test_set_branch_sha_api_failure_does_not_raise(self):
        session = _make_session(upsert_ok=False)
        session.get.return_value.json.return_value = {"data": []}
        state = PollerState(api_url=API_URL, api_key=API_KEY, session=session)
        # Must not raise even when API returns an error
        state.set_branch_sha("alpha_fw", "main", "sha")
        assert state.get_branch_sha("alpha_fw", "main") == "sha"


# ---------------------------------------------------------------------------
# PR tracking
# ---------------------------------------------------------------------------

class TestPollerStatePRs:
    def test_get_pr_sha_missing_returns_none(self):
        state, _ = _state()
        assert state.get_pr_sha("alpha_fw", 42) is None

    def test_set_and_get_pr_sha(self):
        state, _ = _state()
        state.set_pr_sha("alpha_fw", 42, "def456", "feature/x")
        assert state.get_pr_sha("alpha_fw", 42) == "def456"

    def test_get_pr_source_branch(self):
        state, _ = _state()
        state.set_pr_sha("alpha_fw", 42, "def456", "feature/sensor")
        assert state.get_pr_source_branch("alpha_fw", 42) == "feature/sensor"

    def test_get_tracked_pr_ids(self):
        state, _ = _state()
        state.set_pr_sha("alpha_fw", 42, "sha1", "branch1")
        state.set_pr_sha("alpha_fw", 43, "sha2", "branch2")
        assert state.get_tracked_pr_ids("alpha_fw") == {42, 43}

    def test_get_tracked_pr_ids_empty(self):
        state, _ = _state()
        assert state.get_tracked_pr_ids("alpha_fw") == set()

    def test_remove_pr(self):
        state, _ = _state()
        state.set_pr_sha("alpha_fw", 42, "sha1", "branch1")
        state.remove_pr("alpha_fw", 42)
        assert state.get_pr_sha("alpha_fw", 42) is None
        assert 42 not in state.get_tracked_pr_ids("alpha_fw")

    def test_remove_nonexistent_pr_is_safe(self):
        state, _ = _state()
        state.remove_pr("alpha_fw", 999)  # must not raise

    def test_pr_sha_overwrites(self):
        state, _ = _state()
        state.set_pr_sha("alpha_fw", 42, "sha1", "branch1")
        state.set_pr_sha("alpha_fw", 42, "sha2", "branch1")
        assert state.get_pr_sha("alpha_fw", 42) == "sha2"

    def test_set_pr_sha_calls_api_put_with_metadata(self):
        state, session = _state()
        state.set_pr_sha("alpha_fw", 42, "prsha", "feature/sensor")

        # Two puts: one from set_branch_sha called previously (none), then this
        session.put.assert_called_once()
        call_kwargs = session.put.call_args[1]
        payload = call_kwargs["json"]
        assert payload["type"] == "pr"
        assert payload["refId"] == "42"
        assert payload["commitSha"] == "prsha"
        assert payload["metadata"]["source_branch"] == "feature/sensor"

    def test_remove_pr_calls_api_delete(self):
        state, session = _state()
        state.set_pr_sha("alpha_fw", 42, "sha", "branch")
        session.reset_mock()  # clear the put call

        state.remove_pr("alpha_fw", 42)

        session.delete.assert_called_once()
        call_kwargs = session.delete.call_args[1]
        assert call_kwargs["params"]["repoSlug"] == "alpha_fw"
        assert call_kwargs["params"]["type"] == "pr"
        assert call_kwargs["params"]["refId"] == "42"

    def test_remove_pr_api_failure_does_not_raise(self):
        session = _make_session(delete_ok=False)
        session.delete.return_value.status_code = 500
        session.get.return_value.json.return_value = {"data": []}
        state = PollerState(api_url=API_URL, api_key=API_KEY, session=session)
        state.set_pr_sha("alpha_fw", 42, "sha", "branch")
        state.remove_pr("alpha_fw", 42)  # must not raise
        assert state.get_pr_sha("alpha_fw", 42) is None


# ---------------------------------------------------------------------------
# Save is a no-op
# ---------------------------------------------------------------------------

class TestPollerStateSave:
    def test_save_is_noop(self):
        state, session = _state()
        state.set_branch_sha("alpha_fw", "main", "abc123")
        session.reset_mock()
        state.save()  # must not call any API
        session.get.assert_not_called()
        session.put.assert_not_called()
        session.delete.assert_not_called()
