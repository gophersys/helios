"""Tests for BuildTrigger — posts RepoEvent payloads to /v2/builds/events."""

from unittest.mock import MagicMock

import pytest

from trigger import BuildTrigger
from models import WatchTarget, PRInfo


def _make_session(status_code: int = 200, json_body: dict = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.return_value = {"data": {"triggered": 1, "stages": [{"name": "FUOTA"}]}, "errors": []}
    session = MagicMock()
    session.post.return_value = resp
    return session


@pytest.fixture
def target():
    return WatchTarget(
        product_id="prod_abc",
        repo_slug="alpha_fw",
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=5,
        watch_branch="concord-main",
        trigger_types=["pr_merge"],
    )


@pytest.fixture
def pr_info():
    return PRInfo(
        pr_id=42,
        title="feat: sensor support",
        source_branch="feature/sensor",
        target_branch="concord-main",
        head_sha="deadbeef1234",
        author="dev",
    )


class TestBuildTriggerSuccess:
    def test_returns_true_on_success(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(target, "abc123", "pr_merge")
        assert result is True

    def test_posts_to_events_endpoint(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        call_url = session.post.call_args[0][0]
        assert call_url == "http://api:9001/v2/builds/events"

    def test_sends_authorization_header(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_my_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        headers = session.post.call_args[1]["headers"]
        assert headers["Authorization"] == "ApiKey ck_my_key"

    def test_payload_is_repo_event_shape(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123def456", "pr_merge")
        payload = session.post.call_args[1]["json"]

        assert payload["repoSlug"] == "alpha_fw"
        assert payload["commitSha"] == "abc123def456"
        assert payload["eventType"] == "merge"
        assert payload["source"] == "poller"
        assert "metadata" in payload

    def test_merge_event_type_for_pr_merge(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        payload = session.post.call_args[1]["json"]
        assert payload["eventType"] == "merge"

    def test_push_event_type_for_pr_push(self, target, pr_info):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_push", pr_info=pr_info)
        payload = session.post.call_args[1]["json"]
        assert payload["eventType"] == "push"

    def test_branch_is_watch_branch_for_merge(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        payload = session.post.call_args[1]["json"]
        assert payload["branch"] == "concord-main"

    def test_branch_is_source_branch_for_pr_push(self, target, pr_info):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, pr_info.head_sha, "pr_push", pr_info=pr_info)
        payload = session.post.call_args[1]["json"]
        assert payload["branch"] == "feature/sensor"

    def test_metadata_includes_target_branch(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        metadata = session.post.call_args[1]["json"]["metadata"]
        assert metadata["target_branch"] == "concord-main"

    def test_metadata_includes_pr_info_when_given(self, target, pr_info):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, pr_info.head_sha, "pr_push", pr_info=pr_info)
        metadata = session.post.call_args[1]["json"]["metadata"]
        assert metadata["pr_number"] == 42
        assert metadata["pr_title"] == "feat: sensor support"

    def test_metadata_excludes_pr_fields_when_no_pr_info(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        metadata = session.post.call_args[1]["json"]["metadata"]
        assert "pr_number" not in metadata


class TestBuildTriggerErrors:
    def test_returns_false_on_api_error(self, target):
        session = _make_session(status_code=500)
        session.post.return_value.text = "Internal Server Error"
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(target, "abc123", "pr_merge")
        assert result is False

    def test_returns_false_on_request_exception(self, target):
        import requests as req
        session = MagicMock()
        session.post.side_effect = req.ConnectionError("refused")
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(target, "abc123", "pr_merge")
        assert result is False

    def test_returns_false_when_no_api_key(self, target):
        bt = BuildTrigger("http://api:9001", "", session_factory=lambda: MagicMock())
        result = bt.trigger_build(target, "abc123", "pr_merge")
        assert result is False

    def test_returns_false_on_api_errors_in_body(self, target):
        session = _make_session(json_body={"data": None, "errors": [{"message": "Product not found"}]})
        bt = BuildTrigger("http://api:9001", "ck_key", session_factory=lambda: session)
        result = bt.trigger_build(target, "abc123", "pr_merge")
        assert result is False

    def test_strips_trailing_slash_from_api_url(self, target):
        session = _make_session()
        bt = BuildTrigger("http://api:9001/", "ck_key", session_factory=lambda: session)
        bt.trigger_build(target, "abc123", "pr_merge")
        url = session.post.call_args[0][0]
        assert url == "http://api:9001/v2/builds/events"
