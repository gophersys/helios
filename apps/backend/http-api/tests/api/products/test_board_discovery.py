"""Tests for api/v2/products/board_discovery.py — board discovery and repo check endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _reset_ck_boards_service():
    """Reset the global service reference before/after each test."""
    import api.v2.products.board_discovery as bd
    original = bd._ck_boards_service
    bd._ck_boards_service = None
    yield
    bd._ck_boards_service = original


class TestListBoardBranches:
    def test_service_not_configured_returns_500(self, authed_client, mock_db):
        resp = authed_client.get("/v2/products/boards/branches")
        assert resp.status_code == 500

    def test_service_not_ready_returns_500(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        bd._ck_boards_service = MagicMock(is_ready=False)
        resp = authed_client.get("/v2/products/boards/branches")
        assert resp.status_code == 500

    def test_returns_refs(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.list_refs.return_value = [{"name": "main", "sha": "abc"}]
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/branches")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "main"

    def test_exception_returns_500(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.list_refs.side_effect = Exception("git error")
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/branches")
        assert resp.status_code == 500


class TestDiscoverBoards:
    def test_missing_branch_returns_400(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        bd._ck_boards_service = MagicMock(is_ready=True)
        resp = authed_client.get("/v2/products/boards/discover")
        assert resp.status_code == 400

    def test_service_not_configured_returns_500(self, authed_client, mock_db):
        resp = authed_client.get("/v2/products/boards/discover?branch=main")
        assert resp.status_code == 500

    def test_returns_boards(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_boards.return_value = [{"name": "alpha_b0"}]
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover?branch=main")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data[0]["name"] == "alpha_b0"

    def test_value_error_returns_400(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_boards.side_effect = ValueError("bad config")
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover?branch=main")
        assert resp.status_code == 400

    def test_exception_returns_500(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_boards.side_effect = RuntimeError("git error")
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover?branch=main")
        assert resp.status_code == 500


class TestDiscoverBoardDetail:
    def test_missing_branch_returns_400(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        bd._ck_boards_service = MagicMock(is_ready=True)
        resp = authed_client.get("/v2/products/boards/discover/alpha_b0")
        assert resp.status_code == 400

    def test_returns_detail(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_board_detail.return_value = {"name": "alpha_b0", "targets": []}
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover/alpha_b0?branch=main")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_board_detail.side_effect = ValueError("Board not found on branch")
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover/missing_board?branch=main")
        assert resp.status_code == 404

    def test_value_error_non_not_found_returns_400(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_board_detail.side_effect = ValueError("bad config")
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover/alpha_b0?branch=main")
        assert resp.status_code == 400

    def test_exception_returns_500(self, authed_client, mock_db):
        import api.v2.products.board_discovery as bd
        svc = MagicMock(is_ready=True)
        svc.discover_board_detail.side_effect = RuntimeError("git error")
        bd._ck_boards_service = svc

        resp = authed_client.get("/v2/products/boards/discover/alpha_b0?branch=main")
        assert resp.status_code == 500

    def test_service_not_configured_returns_500(self, authed_client, mock_db):
        resp = authed_client.get("/v2/products/boards/discover/alpha_b0?branch=main")
        assert resp.status_code == 500


class TestCheckRepo:
    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_missing_slug_returns_400(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        resp = authed_client.get("/v2/products/repos/check")
        assert resp.status_code == 400

    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_repo_exists(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        mock_config.BITBUCKET_SSH_KEY = None
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        resp = authed_client.get("/v2/products/repos/check?slug=alpha_fw")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["exists"] is True
        assert data["slug"] == "alpha_fw"

    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_repo_not_exists(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        mock_config.BITBUCKET_SSH_KEY = None
        mock_subprocess_run.return_value = MagicMock(returncode=2)

        resp = authed_client.get("/v2/products/repos/check?slug=nonexistent")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["exists"] is False

    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_exception_returns_exists_false(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        mock_config.BITBUCKET_SSH_KEY = None
        mock_subprocess_run.side_effect = Exception("timeout")

        resp = authed_client.get("/v2/products/repos/check?slug=alpha_fw")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["exists"] is False


class TestListRepoBranches:
    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_missing_slug_returns_400(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        resp = authed_client.get("/v2/products/repos/branches")
        assert resp.status_code == 400

    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_returns_branches(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        mock_config.BITBUCKET_SSH_KEY = None
        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\trefs/heads/main\ndef456\trefs/heads/develop\n",
        )

        resp = authed_client.get("/v2/products/repos/branches?slug=alpha_fw")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "develop" in data["branches"]
        assert "main" in data["branches"]
        assert data["branches"] == sorted(data["branches"])

    @patch("subprocess.run")
    @patch("config.env.env_config")
    def test_git_failure_returns_empty(self, mock_config, mock_subprocess_run, authed_client, mock_db):
        mock_config.BITBUCKET_SSH_KEY = None
        mock_subprocess_run.return_value = MagicMock(returncode=128, stdout="")

        resp = authed_client.get("/v2/products/repos/branches?slug=alpha_fw")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["branches"] == []
