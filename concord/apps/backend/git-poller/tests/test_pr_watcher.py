"""Tests for PRWatcher."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from pr_watcher import PRWatcher, _parse_pr
from models import PRInfo


def _make_session(responses: list) -> MagicMock:
    """Create a mock session whose .get() returns responses in sequence."""
    session = MagicMock()
    session.get.side_effect = responses
    return session


def _ok_response(values: list, next_url: str = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    data = {"values": values}
    if next_url:
        data["next"] = next_url
    resp.json.return_value = data
    return resp


def _pr_payload(pr_id: int = 42, source: str = "feature/x", target: str = "concord-main",
                sha: str = "abc123", title: str = "My PR") -> dict:
    return {
        "id": pr_id,
        "title": title,
        "source": {
            "branch": {"name": source},
            "commit": {"hash": sha},
        },
        "destination": {
            "branch": {"name": target},
        },
        "author": {"display_name": "Dev User"},
    }


class TestParsePr:
    def test_parses_complete_pr(self):
        payload = _pr_payload()
        info = _parse_pr(payload)
        assert info is not None
        assert info.pr_id == 42
        assert info.title == "My PR"
        assert info.source_branch == "feature/x"
        assert info.target_branch == "concord-main"
        assert info.head_sha == "abc123"
        assert info.author == "Dev User"

    def test_returns_none_on_missing_id(self):
        payload = _pr_payload()
        del payload["id"]
        info = _parse_pr(payload)
        assert info is None

    def test_returns_none_on_broken_structure(self):
        info = _parse_pr({"id": "not-an-int"})
        assert info is None


class TestPRWatcherGetOpenPRs:
    def test_returns_prs_filtered_by_target_branch(self):
        pr_main = _pr_payload(pr_id=1, target="concord-main")
        pr_release = _pr_payload(pr_id=2, target="release")
        session = _make_session([_ok_response([pr_main, pr_release])])
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert len(prs) == 1
        assert prs[0].pr_id == 1

    def test_returns_empty_list_when_no_open_prs(self):
        session = _make_session([_ok_response([])])
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert prs == []

    def test_follows_pagination(self):
        page1 = _ok_response([_pr_payload(pr_id=1)], next_url="https://api/page2")
        page2 = _ok_response([_pr_payload(pr_id=2)])
        session = _make_session([page1, page2])
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert len(prs) == 2
        assert {p.pr_id for p in prs} == {1, 2}

    def test_handles_401_gracefully(self):
        resp = MagicMock()
        resp.status_code = 401
        session = _make_session([resp])
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert prs == []

    def test_handles_500_gracefully(self):
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "server error"
        session = _make_session([resp])
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert prs == []

    def test_handles_request_exception_gracefully(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("refused")
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert prs == []

    def test_builds_correct_bitbucket_url(self):
        session = _make_session([_ok_response([])])
        watcher = PRWatcher("corekinect", "email", "token", session_factory=lambda: session)
        watcher.get_open_prs("alpha_fw", "concord-main")
        call_url = session.get.call_args[0][0]
        assert "corekinect" in call_url
        assert "alpha_fw" in call_url
        assert "state=OPEN" in call_url

    def test_uses_basic_auth(self):
        session = _make_session([_ok_response([])])
        watcher = PRWatcher("ws", "dev@example.com", "mytoken", session_factory=lambda: session)
        watcher.get_open_prs("alpha_fw", "concord-main")
        call_kwargs = session.get.call_args[1]
        auth = call_kwargs["auth"]
        assert auth.username == "dev@example.com"
        assert auth.password == "mytoken"

    def test_returns_empty_on_json_parse_error(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("bad json")
        session = _make_session([resp])
        watcher = PRWatcher("ws", "email", "token", session_factory=lambda: session)
        prs = watcher.get_open_prs("alpha_fw", "concord-main")
        assert prs == []
