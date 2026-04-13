"""Extended tests for services/webhook_trigger.py — poll_for_changes, handle_auto_progress edge cases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from tests.conftest import make_obj


# ---------------------------------------------------------------------------
# poll_for_changes
# ---------------------------------------------------------------------------

class TestPollForChanges:
    """Tests for poll_for_changes()."""

    def _patch_poll(self):
        """Return context managers for the three local imports inside poll_for_changes."""
        return (
            patch("config.env_config"),
            patch("src.services.bitbucket_client.BitbucketClient"),
            patch("src.services.bitbucket_client.parse_pr_metadata"),
            patch("src.services.webhook_trigger.get_db_client"),
            patch("src.services.webhook_trigger.handle_repo_event"),
        )

    def test_not_configured_returns_empty(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.webhook_trigger.get_db_client"):
            mock_config.BITBUCKET_API_TOKEN = ""
            mock_config.BITBUCKET_EMAIL = ""
            mock_config.BITBUCKET_WORKSPACE = ""
            bb = MagicMock(is_configured=False)
            mock_bb_cls.return_value = bb

            result = poll_for_changes()
            assert result == []

    def test_no_stages_returns_empty(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            mock_bb_cls.return_value = bb
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = []

            result = poll_for_changes()
            assert result == []

    def test_skips_draft_prs(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.bitbucket_client.parse_pr_metadata") as mock_parse, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db, \
             patch("src.services.webhook_trigger.handle_repo_event") as mock_handle:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            bb.list_open_prs.return_value = [{"draft": True}]
            mock_bb_cls.return_value = bb

            product = make_obj(id="prod-1", name="Alpha", fwRepoSlug="alpha_fw")
            stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*", product=product)
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = [stage]

            result = poll_for_changes()
            assert result == []
            mock_handle.assert_not_called()

    def test_skips_cached_commits(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.bitbucket_client.parse_pr_metadata") as mock_parse, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db, \
             patch("src.services.webhook_trigger.handle_repo_event") as mock_handle:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            bb.list_open_prs.return_value = [{"draft": False}]
            mock_bb_cls.return_value = bb

            product = make_obj(id="prod-1", name="Alpha", fwRepoSlug="alpha_fw")
            stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*", product=product)
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = [stage]

            mock_parse.return_value = {
                "pr_id": 42, "pr_title": "Test", "source_branch": "feat/x",
                "target_branch": "main", "source_commit": "abc123",
            }
            db.pollcache.find_first.return_value = make_obj(commitSha="abc123")

            result = poll_for_changes()
            assert result == []
            mock_handle.assert_not_called()

    def test_fires_event_on_new_commit(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.bitbucket_client.parse_pr_metadata") as mock_parse, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db, \
             patch("src.services.webhook_trigger.handle_repo_event") as mock_handle:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            bb.list_open_prs.return_value = [{"draft": False}]
            mock_bb_cls.return_value = bb

            product = make_obj(id="prod-1", name="Alpha", fwRepoSlug="alpha_fw")
            stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*", product=product)
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = [stage]

            mock_parse.return_value = {
                "pr_id": 42, "pr_title": "Test", "source_branch": "feat/x",
                "target_branch": "main", "source_commit": "new_sha",
            }
            db.pollcache.find_first.return_value = make_obj(commitSha="old_sha")
            mock_handle.return_value = [{"stage": 1, "name": "Smoke", "buildRunId": "run-1"}]

            result = poll_for_changes()
            assert len(result) == 1
            mock_handle.assert_called_once()
            db.pollcache.upsert.assert_called_once()

    def test_unmatched_branch_skipped(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.bitbucket_client.parse_pr_metadata") as mock_parse, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db, \
             patch("src.services.webhook_trigger.handle_repo_event") as mock_handle:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            bb.list_open_prs.return_value = [{"draft": False}]
            mock_bb_cls.return_value = bb

            product = make_obj(id="prod-1", name="Alpha", fwRepoSlug="alpha_fw")
            stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="main", product=product)
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = [stage]

            mock_parse.return_value = {
                "pr_id": 42, "pr_title": "Test", "source_branch": "feat/x",
                "target_branch": "develop", "source_commit": "abc123",
            }

            result = poll_for_changes()
            assert result == []
            mock_handle.assert_not_called()

    def test_pr_list_failure_continues(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            bb.list_open_prs.side_effect = Exception("API error")
            mock_bb_cls.return_value = bb

            product = make_obj(id="prod-1", name="Alpha", fwRepoSlug="alpha_fw")
            stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*", product=product)
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = [stage]

            result = poll_for_changes()
            assert result == []

    def test_product_without_fw_repo_slug_skipped(self):
        from src.services.webhook_trigger import poll_for_changes

        with patch("config.env_config") as mock_config, \
             patch("src.services.bitbucket_client.BitbucketClient") as mock_bb_cls, \
             patch("src.services.webhook_trigger.get_db_client") as mock_get_db:
            mock_config.BITBUCKET_API_TOKEN = "token"
            mock_config.BITBUCKET_EMAIL = "t@t.com"
            mock_config.BITBUCKET_WORKSPACE = "ws"
            bb = MagicMock(is_configured=True)
            mock_bb_cls.return_value = bb

            product = make_obj(id="prod-1", name="Alpha", fwRepoSlug=None)
            stage = make_obj(id="sc-1", stage=1, name="Smoke", watchBranch="*", product=product)
            db = MagicMock()
            mock_get_db.return_value = db
            db.productstageconfig.find_many.return_value = [stage]

            result = poll_for_changes()
            assert result == []
            bb.list_open_prs.assert_not_called()


# ---------------------------------------------------------------------------
# handle_auto_progress edge cases
# ---------------------------------------------------------------------------

class TestAutoProgressEdgeCases:
    def test_stage_4_returns_none_disabled(self):
        """handle_auto_progress is disabled and always returns None, even for stage 4->5."""
        from src.services.webhook_trigger import handle_auto_progress

        result = handle_auto_progress("prod-1", completed_stage=4)
        assert result is None

    @patch("src.services.webhook_trigger.get_db_client")
    def test_no_auto_stage_returns_none(self, mock_get_db):
        from src.services.webhook_trigger import handle_auto_progress

        db = MagicMock()
        mock_get_db.return_value = db
        db.productstageconfig.find_first.return_value = None

        result = handle_auto_progress("prod-1", completed_stage=2)
        assert result is None
