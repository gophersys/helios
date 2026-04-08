"""Tests for services/webhook_trigger.py — repo event handling, webhook parsing, auto-progress."""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# handle_repo_event
# ---------------------------------------------------------------------------

class TestHandleRepoEvent:
    """Tests for handle_repo_event()."""

    def _make_event(self, **overrides):
        from src.services.webhook_trigger import RepoEvent
        defaults = dict(
            repo_slug="alpha_fw",
            branch="main",
            commit_sha="abc1234",
            event_type="push",
            source="poller",
            metadata=None,
        )
        defaults.update(overrides)
        return RepoEvent(**defaults)

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_push_triggers_pr_push_stages(self, mock_get_db, mock_trigger):
        """Push events match stages with pr_push trigger type."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db

        product = make_obj(id="prod-1", name="Alpha")
        db.product.find_first.return_value = product

        stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*")
        db.productstageconfig.find_many.return_value = [stage]

        mock_trigger.return_value = {"buildRunId": "run-1"}

        event = self._make_event(event_type="push")
        results = handle_repo_event(event)

        assert len(results) == 1
        assert results[0]["stage"] == 1
        mock_trigger.assert_called_once_with("prod-1", "sc-1", event_metadata=None)

    @patch("src.services.webhook_trigger.get_db_client")
    def test_unknown_event_type_returns_empty(self, mock_get_db):
        """Unknown event types are ignored."""
        from src.services.webhook_trigger import handle_repo_event

        event = self._make_event(event_type="unknown")
        results = handle_repo_event(event)

        assert results == []
        mock_get_db.assert_not_called()

    @patch("src.services.webhook_trigger.get_db_client")
    def test_no_product_returns_empty(self, mock_get_db):
        """Returns empty when no product matches the repo slug."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = None

        event = self._make_event(event_type="push")
        results = handle_repo_event(event)

        assert results == []

    @patch("src.services.webhook_trigger.get_db_client")
    def test_no_matching_stages_returns_empty(self, mock_get_db):
        """Returns empty when no enabled stages match the trigger type."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = []

        event = self._make_event(event_type="push")
        results = handle_repo_event(event)

        assert results == []

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_branch_wildcard_matches_all(self, mock_get_db, mock_trigger):
        """Stages with watchBranch='*' match any branch."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*"),
        ]
        mock_trigger.return_value = {"buildRunId": "run-1"}

        event = self._make_event(branch="feature/xyz")
        results = handle_repo_event(event)

        assert len(results) == 1

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_branch_exact_match(self, mock_get_db, mock_trigger):
        """Stages with exact watchBranch match the correct branch."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="main"),
        ]
        mock_trigger.return_value = {"buildRunId": "run-1"}

        event = self._make_event(branch="main")
        results = handle_repo_event(event)

        assert len(results) == 1

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_branch_no_match_skips_stage(self, mock_get_db, mock_trigger):
        """Stages with non-matching watchBranch are skipped."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="main"),
        ]

        event = self._make_event(branch="develop")
        results = handle_repo_event(event)

        assert results == []
        mock_trigger.assert_not_called()

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_branch_prefix_match(self, mock_get_db, mock_trigger):
        """Stages with watchBranch ending in * match branch prefixes."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="feature/*"),
        ]
        mock_trigger.return_value = {"buildRunId": "run-1"}

        event = self._make_event(branch="feature/new-sensor")
        results = handle_repo_event(event)

        assert len(results) == 1

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_merge_event_maps_to_pr_merge(self, mock_get_db, mock_trigger):
        """Merge events match stages with pr_merge trigger type."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=3, name="Integration", watchBranch=None),
        ]
        mock_trigger.return_value = {"buildRunId": "run-1"}

        event = self._make_event(event_type="merge")
        results = handle_repo_event(event)

        assert len(results) == 1
        # Check trigger_types passed correctly in find_many
        call_args = db.productstageconfig.find_many.call_args
        assert "pr_merge" in call_args[1]["where"]["triggerTypes"]["hasSome"]

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_target_branch_used_for_pr_matching(self, mock_get_db, mock_trigger):
        """PR events use target_branch from metadata for branch matching."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=5, name="FUOTA", watchBranch="concord-main"),
        ]
        mock_trigger.return_value = {"buildRunId": "run-1"}

        event = self._make_event(
            branch="feature/x",
            metadata={"target_branch": "concord-main"},
        )
        results = handle_repo_event(event)

        assert len(results) == 1

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_trigger_returns_none_excluded(self, mock_get_db, mock_trigger):
        """Stages where trigger_stage_build returns None are excluded from results."""
        from src.services.webhook_trigger import handle_repo_event

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_first.return_value = make_obj(id="prod-1", name="Alpha")
        db.productstageconfig.find_many.return_value = [
            make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*"),
        ]
        mock_trigger.return_value = None

        event = self._make_event()
        results = handle_repo_event(event)

        assert results == []


# ---------------------------------------------------------------------------
# parse_bitbucket_webhook
# ---------------------------------------------------------------------------

class TestParseBitbucketWebhook:
    """Tests for parse_bitbucket_webhook()."""

    def test_pr_created_event(self):
        """PR created events parse as push type."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        payload = {
            "repository": {"slug": "alpha_fw"},
            "pullrequest": {
                "source": {
                    "branch": {"name": "feature/x"},
                    "commit": {"hash": "abc123"},
                },
            },
        }
        event = parse_bitbucket_webhook("pullrequest:created", payload)

        assert event is not None
        assert event.event_type == "push"
        assert event.repo_slug == "alpha_fw"
        assert event.branch == "feature/x"
        assert event.commit_sha == "abc123"
        assert event.source == "webhook"

    def test_pr_fulfilled_event(self):
        """PR fulfilled events parse as merge type."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        payload = {
            "repository": {"slug": "alpha_fw"},
            "pullrequest": {
                "source": {
                    "branch": {"name": "feature/y"},
                    "commit": {"hash": "def456"},
                },
            },
        }
        event = parse_bitbucket_webhook("pullrequest:fulfilled", payload)

        assert event is not None
        assert event.event_type == "merge"

    def test_repo_push_event(self):
        """Repo push events extract branch and commit from changes."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        payload = {
            "repository": {"slug": "alpha_fw"},
            "push": {
                "changes": [{
                    "new": {
                        "name": "main",
                        "target": {"hash": "xyz789"},
                    },
                }],
            },
        }
        event = parse_bitbucket_webhook("repo:push", payload)

        assert event is not None
        assert event.event_type == "push"
        assert event.branch == "main"
        assert event.commit_sha == "xyz789"

    def test_unknown_event_key_returns_none(self):
        """Unknown event keys return None."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        result = parse_bitbucket_webhook("repo:fork", {})
        assert result is None

    def test_missing_repository_returns_none(self):
        """Missing repository in payload returns None."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        result = parse_bitbucket_webhook("repo:push", {})
        assert result is None

    def test_empty_push_changes(self):
        """Push event with empty changes list still produces event."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        payload = {
            "repository": {"slug": "alpha_fw"},
            "push": {"changes": []},
        }
        event = parse_bitbucket_webhook("repo:push", payload)

        assert event is not None
        assert event.branch == "unknown"
        assert event.commit_sha is None

    def test_pr_updated_event(self):
        """PR updated events parse as push type."""
        from src.services.webhook_trigger import parse_bitbucket_webhook

        payload = {
            "repository": {"slug": "alpha_fw"},
            "pullrequest": {
                "source": {
                    "branch": {"name": "feature/z"},
                    "commit": {"hash": "111aaa"},
                },
            },
        }
        event = parse_bitbucket_webhook("pullrequest:updated", payload)

        assert event is not None
        assert event.event_type == "push"


# ---------------------------------------------------------------------------
# handle_auto_progress
# ---------------------------------------------------------------------------

class TestHandleAutoProgress:
    """Tests for handle_auto_progress()."""

    @patch("src.services.webhook_trigger.trigger_stage_build")
    @patch("src.services.webhook_trigger.get_db_client")
    def test_triggers_next_stage_with_auto(self, mock_get_db, mock_trigger):
        """Triggers the next stage when it has auto trigger type."""
        from src.services.webhook_trigger import handle_auto_progress

        db = MagicMock()
        mock_get_db.return_value = db
        next_config = make_obj(id="sc-2", stage=2)
        db.productstageconfig.find_first.return_value = next_config
        mock_trigger.return_value = {"buildRunId": "run-2"}

        result = handle_auto_progress("prod-1", completed_stage=1)

        assert result == {"buildRunId": "run-2"}
        mock_trigger.assert_called_once_with("prod-1", "sc-2")

    @patch("src.services.webhook_trigger.get_db_client")
    def test_no_next_stage_returns_none(self, mock_get_db):
        """Returns None when no auto-triggered next stage exists."""
        from src.services.webhook_trigger import handle_auto_progress

        db = MagicMock()
        mock_get_db.return_value = db
        db.productstageconfig.find_first.return_value = None

        result = handle_auto_progress("prod-1", completed_stage=3)

        assert result is None

    @patch("src.services.webhook_trigger.get_db_client")
    def test_stage_5_returns_none(self, mock_get_db):
        """Returns None when completed stage is 5 (max)."""
        from src.services.webhook_trigger import handle_auto_progress

        mock_get_db.return_value = MagicMock()

        result = handle_auto_progress("prod-1", completed_stage=5)
        assert result is None
