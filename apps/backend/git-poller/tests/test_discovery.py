"""Tests for ProductDiscovery."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from discovery import ProductDiscovery, _parse_watch_targets
from models import WatchTarget


# ---------------------------------------------------------------------------
# _parse_watch_targets unit tests
# ---------------------------------------------------------------------------


class TestParseWatchTargets:
    def _product(self, **overrides):
        base = {
            "id": "prod_1",
            "active": True,
            "fwRepoSlug": "alpha_fw",
            "repoSshUrl": "git@bitbucket.org:corekinect/alpha_fw.git",
            "stageConfigs": [
                {
                    "enabled": True,
                    "stage": 5,
                    "watchBranch": "concord-main",
                    "triggerTypes": ["pr_merge", "pr_push"],
                    "boardRevision": {"ckBoardsName": "alpha_b0"},
                }
            ],
        }
        base.update(overrides)
        return base

    def test_parses_single_enabled_stage(self):
        targets = _parse_watch_targets([self._product()])
        assert len(targets) == 1
        t = targets[0]
        assert t.product_id == "prod_1"
        assert t.repo_slug == "alpha_fw"
        assert t.ssh_url == "git@bitbucket.org:corekinect/alpha_fw.git"
        assert t.board == "alpha_b0"
        assert t.stage == 5
        assert t.watch_branch == "concord-main"
        assert set(t.trigger_types) == {"pr_merge", "pr_push"}

    def test_skips_inactive_products(self):
        targets = _parse_watch_targets([self._product(active=False)])
        assert targets == []

    def test_skips_products_without_ssh_url(self):
        targets = _parse_watch_targets([self._product(repoSshUrl="")])
        assert targets == []

    def test_skips_disabled_stages(self):
        product = self._product()
        product["stageConfigs"][0]["enabled"] = False
        targets = _parse_watch_targets([product])
        assert targets == []

    def test_skips_stages_with_no_valid_trigger_types(self):
        product = self._product()
        product["stageConfigs"][0]["triggerTypes"] = ["webhook", "manual"]
        targets = _parse_watch_targets([product])
        assert targets == []

    def test_skips_stages_with_empty_trigger_types(self):
        product = self._product()
        product["stageConfigs"][0]["triggerTypes"] = []
        targets = _parse_watch_targets([product])
        assert targets == []

    def test_multiple_stages_yield_multiple_targets(self):
        product = self._product()
        product["stageConfigs"].append(
            {
                "enabled": True,
                "stage": 4,
                "watchBranch": "release",
                "triggerTypes": ["pr_merge"],
                "boardRevision": {"ckBoardsName": "alpha_b0"},
            }
        )
        targets = _parse_watch_targets([product])
        assert len(targets) == 2
        stages = {t.stage for t in targets}
        assert stages == {4, 5}

    def test_multiple_products(self):
        p2 = {
            "id": "prod_2",
            "active": True,
            "fwRepoSlug": "beta_fw",
            "repoSshUrl": "git@bitbucket.org:corekinect/beta_fw.git",
            "stageConfigs": [
                {
                    "enabled": True,
                    "stage": 3,
                    "watchBranch": "main",
                    "triggerTypes": ["pr_push"],
                    "boardRevision": {"ckBoardsName": "beta_b0"},
                }
            ],
        }
        targets = _parse_watch_targets([self._product(), p2])
        assert len(targets) == 2
        slugs = {t.repo_slug for t in targets}
        assert slugs == {"alpha_fw", "beta_fw"}

    def test_missing_stage_configs_returns_empty(self):
        product = self._product()
        product["stageConfigs"] = []
        targets = _parse_watch_targets([product])
        assert targets == []

    def test_stage_configs_none_returns_empty(self):
        product = self._product()
        product["stageConfigs"] = None
        targets = _parse_watch_targets([product])
        assert targets == []

    def test_watch_branch_defaults_to_concord_main(self):
        product = self._product()
        product["stageConfigs"][0]["watchBranch"] = None
        targets = _parse_watch_targets([product])
        assert targets[0].watch_branch == "concord-main"

    def test_filters_invalid_trigger_types_keeps_valid(self):
        product = self._product()
        product["stageConfigs"][0]["triggerTypes"] = ["pr_merge", "bad_type"]
        targets = _parse_watch_targets([product])
        assert targets[0].trigger_types == ["pr_merge"]


# ---------------------------------------------------------------------------
# ProductDiscovery integration tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestProductDiscovery:
    def _make_response(self, products: list) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"data": products, "pagination": {}}}
        return resp

    def _simple_product(self):
        return {
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

    def test_get_watch_targets_calls_api(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = self._make_response([self._simple_product()])
            disc = ProductDiscovery("http://api:9001", "key123", cache_ttl=60)
            targets = disc.get_watch_targets()
            assert len(targets) == 1
            mock_get.assert_called_once()
            call_url = mock_get.call_args[0][0]
            assert "/v2/products" in call_url

    def test_get_watch_targets_uses_cache(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = self._make_response([self._simple_product()])
            disc = ProductDiscovery("http://api:9001", "key123", cache_ttl=60)
            disc.get_watch_targets()
            disc.get_watch_targets()
            assert mock_get.call_count == 1  # second call used cache

    def test_cache_expires_after_ttl(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = self._make_response([self._simple_product()])
            disc = ProductDiscovery("http://api:9001", "key123", cache_ttl=0)
            disc.get_watch_targets()
            disc.get_watch_targets()
            assert mock_get.call_count == 2

    def test_invalidate_cache_forces_refetch(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = self._make_response([self._simple_product()])
            disc = ProductDiscovery("http://api:9001", "key123", cache_ttl=9999)
            disc.get_watch_targets()
            disc.invalidate_cache()
            disc.get_watch_targets()
            assert mock_get.call_count == 2

    def test_returns_empty_list_on_api_error(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=500, text="error")
            disc = ProductDiscovery("http://api:9001", "key123", cache_ttl=0)
            targets = disc.get_watch_targets()
            assert targets == []

    def test_returns_empty_list_on_request_exception(self):
        with patch("discovery.requests.get", side_effect=requests.ConnectionError("conn")):
            disc = ProductDiscovery("http://api:9001", "key123", cache_ttl=0)
            targets = disc.get_watch_targets()
            assert targets == []

    def test_returns_empty_list_when_no_api_key(self):
        disc = ProductDiscovery("http://api:9001", "", cache_ttl=0)
        targets = disc.get_watch_targets()
        assert targets == []

    def test_sends_authorization_header(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = self._make_response([])
            disc = ProductDiscovery("http://api:9001", "ck_test_key", cache_ttl=0)
            disc.get_watch_targets()
            headers = mock_get.call_args[1]["headers"]
            assert headers["Authorization"] == "ApiKey ck_test_key"

    def test_empty_products_returns_empty_targets(self):
        with patch("discovery.requests.get") as mock_get:
            mock_get.return_value = self._make_response([])
            disc = ProductDiscovery("http://api:9001", "key", cache_ttl=0)
            assert disc.get_watch_targets() == []
