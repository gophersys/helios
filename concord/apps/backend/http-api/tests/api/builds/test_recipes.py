"""Integration tests for the Build Recipes API.

Covers: get_recipe, update_recipe, save_recipe_version, publish_recipe,
list_recipe_versions, get_recipe_version, validate_recipe, diff_recipe_versions.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

_RECIPE_CONTENT = "#!/bin/bash\nsource /app/sdk/concord-build.sh\nconcord_init\nconcord_finalize\n"


def _make_product(**overrides):
    defaults = dict(
        id="prod-1",
        name="Alpha",
        slug="alpha",
        fwRepoSlug="alpha-fw",
        mfgFwRepoSlug="alpha-mfg",
        builderImage=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_board_revision(**overrides):
    defaults = dict(
        id="rev-1",
        ckBoardsName="alpha_b0",
        version="B0",
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_stage_config(**overrides):
    defaults = dict(
        id="stage-1",
        productId="prod-1",
        stage=5,
        boardRevisionId="rev-1",
        boardRevision=_make_board_revision(),
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_recipe_version(version: int = 1, status: str = "draft", **overrides):
    defaults = dict(
        id=f"ver-{version}",
        productId="prod-1",
        version=version,
        status=status,
        content=_RECIPE_CONTENT,
        changeNote="Initial version",
        createdAt=NOW,
        createdBy=None,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


@pytest.fixture(autouse=True)
def _mock_storage():
    """Mock storage client for all recipe tests."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.read.return_value = _RECIPE_CONTENT.encode("utf-8")
    mock_response.close = MagicMock()
    mock_client.get_object.return_value = mock_response
    mock_client.put_object.return_value = None

    with patch("api.v2.builds.recipes.get_storage_client", return_value=mock_client), \
         patch("api.v2.builds.recipes.get_bucket_name", return_value="test-bucket"):
        yield mock_client


class TestGetRecipe:
    """Tests for GET /v2/products/<id>/recipe."""

    def test_get_recipe_returns_content(self, authed_client, mock_db):
        """get_recipe returns script content for a valid product+stage."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.boardrevision.find_unique.return_value = None
        mock_db.productstageconfig.find_first.return_value = _make_stage_config()

        response = authed_client.get("/v2/products/prod-1/recipe?stage=5")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["content"] == _RECIPE_CONTENT
        assert data["data"]["product"] == "Alpha"
        assert data["data"]["slug"] == "alpha"

    def test_get_recipe_missing_stage_returns_400(self, authed_client, mock_db):
        """get_recipe requires the stage query parameter."""
        mock_db.product.find_unique.return_value = _make_product()

        response = authed_client.get("/v2/products/prod-1/recipe")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "stage" in data["errors"][0]["message"].lower()

    def test_get_recipe_product_not_found(self, authed_client, mock_db):
        """get_recipe returns 404 when product does not exist."""
        mock_db.product.find_unique.return_value = None

        response = authed_client.get("/v2/products/bad-id/recipe?stage=5")

        assert response.status_code == 404

    def test_get_recipe_no_board_revision_returns_400(self, authed_client, mock_db):
        """get_recipe returns 400 when board revision cannot be resolved."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.boardrevision.find_unique.return_value = None
        mock_db.productstageconfig.find_first.return_value = None  # no config

        response = authed_client.get("/v2/products/prod-1/recipe?stage=5")

        assert response.status_code == 400

    def test_get_recipe_no_such_key_returns_null_content(self, authed_client, mock_db, _mock_storage):
        """get_recipe returns content=None when object does not exist in MinIO."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.boardrevision.find_unique.return_value = None
        mock_db.productstageconfig.find_first.return_value = _make_stage_config()
        _mock_storage.get_object.side_effect = Exception("NoSuchKey: not found")

        response = authed_client.get("/v2/products/prod-1/recipe?stage=5")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["content"] is None


class TestUpdateRecipe:
    """Tests for PUT /v2/products/<id>/recipe."""

    def test_update_recipe_success(self, authed_client, mock_db):
        """update_recipe uploads script content to MinIO and returns metadata."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.boardrevision.find_unique.return_value = None
        mock_db.productstageconfig.find_first.return_value = _make_stage_config()

        with patch("api.v2.builds.recipes.log_audit"):
            response = authed_client.put(
                "/v2/products/prod-1/recipe",
                data=json.dumps({"content": _RECIPE_CONTENT, "stage": 5}),
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["product"] == "Alpha"
        assert "storageKey" in data["data"]
        assert data["data"]["size"] == len(_RECIPE_CONTENT.encode("utf-8"))

    def test_update_recipe_content_too_short(self, authed_client, mock_db):
        """update_recipe rejects content shorter than 10 characters."""
        mock_db.product.find_unique.return_value = _make_product()

        response = authed_client.put(
            "/v2/products/prod-1/recipe",
            data=json.dumps({"content": "short", "stage": 5}),
        )

        assert response.status_code == 400

    def test_update_recipe_missing_content(self, authed_client, mock_db):
        """update_recipe returns 400 when content is missing."""
        mock_db.product.find_unique.return_value = _make_product()

        response = authed_client.put(
            "/v2/products/prod-1/recipe",
            data=json.dumps({"stage": 5}),
        )

        assert response.status_code == 400

    def test_update_recipe_product_not_found(self, authed_client, mock_db):
        """update_recipe returns 404 for unknown product."""
        mock_db.product.find_unique.return_value = None

        response = authed_client.put(
            "/v2/products/bad/recipe",
            data=json.dumps({"content": _RECIPE_CONTENT, "stage": 5}),
        )

        assert response.status_code == 404


class TestSaveRecipeVersion:
    """Tests for POST /v2/products/<id>/recipe/save."""

    def test_save_recipe_version_creates_draft(self, authed_client, mock_db):
        """save_recipe_version creates a new draft version record."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.recipeversion.find_first.return_value = None  # no existing versions
        new_version = _make_recipe_version(version=1)
        mock_db.recipeversion.create.return_value = new_version

        with patch("api.v2.builds.recipes.log_audit"):
            response = authed_client.post(
                "/v2/products/prod-1/recipe/save",
                data=json.dumps({"content": _RECIPE_CONTENT, "changeNote": "First version"}),
            )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["data"]["version"] == 1
        assert data["data"]["status"] == "draft"

    def test_save_recipe_version_increments(self, authed_client, mock_db):
        """save_recipe_version auto-increments version from the latest."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.recipeversion.find_first.return_value = _make_recipe_version(version=3)
        new_version = _make_recipe_version(version=4)
        mock_db.recipeversion.create.return_value = new_version

        with patch("api.v2.builds.recipes.log_audit"):
            response = authed_client.post(
                "/v2/products/prod-1/recipe/save",
                data=json.dumps({"content": _RECIPE_CONTENT}),
            )

        assert response.status_code == 201
        # The create call should pass version=4
        call_kwargs = mock_db.recipeversion.create.call_args
        assert call_kwargs[1]["data"]["version"] == 4

    def test_save_recipe_version_missing_content(self, authed_client, mock_db):
        """save_recipe_version returns 400 when content is absent."""
        mock_db.product.find_unique.return_value = _make_product()

        response = authed_client.post(
            "/v2/products/prod-1/recipe/save",
            data=json.dumps({}),
        )

        assert response.status_code == 400

    def test_save_recipe_version_product_not_found(self, authed_client, mock_db):
        """save_recipe_version returns 404 for unknown product."""
        mock_db.product.find_unique.return_value = None

        response = authed_client.post(
            "/v2/products/bad/recipe/save",
            data=json.dumps({"content": _RECIPE_CONTENT}),
        )

        assert response.status_code == 404


class TestPublishRecipe:
    """Tests for POST /v2/products/<id>/recipe/publish."""

    def test_publish_recipe_latest_draft(self, authed_client, mock_db):
        """publish_recipe finds the latest draft and publishes it."""
        mock_db.product.find_unique.return_value = _make_product()
        draft = _make_recipe_version(version=2, status="draft")
        mock_db.recipeversion.find_first.return_value = draft
        mock_db.boardrevision.find_unique.return_value = None
        mock_db.productstageconfig.find_first.return_value = _make_stage_config()

        with patch("api.v2.builds.recipes.log_audit"):
            response = authed_client.post(
                "/v2/products/prod-1/recipe/publish",
                data=json.dumps({"stage": 5}),
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["version"] == 2
        assert "storageKey" in data["data"]

    def test_publish_recipe_no_draft_returns_404(self, authed_client, mock_db):
        """publish_recipe returns 404 when no draft version exists."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.recipeversion.find_first.return_value = None

        response = authed_client.post(
            "/v2/products/prod-1/recipe/publish",
            data=json.dumps({"stage": 5}),
        )

        assert response.status_code == 404

    def test_publish_recipe_missing_stage_returns_400(self, authed_client, mock_db):
        """publish_recipe returns 400 when stage is not provided."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.recipeversion.find_first.return_value = _make_recipe_version()

        response = authed_client.post(
            "/v2/products/prod-1/recipe/publish",
            data=json.dumps({}),
        )

        assert response.status_code == 400


class TestListRecipeVersions:
    """Tests for GET /v2/products/<id>/recipe/versions."""

    def test_list_versions_returns_paginated(self, authed_client, mock_db):
        """list_recipe_versions returns paginated list of versions."""
        mock_db.product.find_unique.return_value = _make_product()
        mock_db.recipeversion.count.return_value = 2
        mock_db.recipeversion.find_many.return_value = [
            _make_recipe_version(version=2, status="published"),
            _make_recipe_version(version=1, status="published"),
        ]

        response = authed_client.get("/v2/products/prod-1/recipe/versions")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 2
        assert data["totalResults"] == 2

    def test_list_versions_product_not_found(self, authed_client, mock_db):
        """list_recipe_versions returns 404 for unknown product."""
        mock_db.product.find_unique.return_value = None

        response = authed_client.get("/v2/products/bad/recipe/versions")

        assert response.status_code == 404


class TestValidateRecipe:
    """Tests for POST /v2/products/<id>/recipe/validate."""

    def test_validate_recipe_valid_script(self, authed_client, mock_db):
        """validate_recipe returns valid=True for a complete build script."""
        mock_db.product.find_unique.return_value = make_obj(
            id="prod-1", name="Alpha", boards=[]
        )

        valid_content = "source /app/sdk/concord-build.sh\nconcord_init\nwest build\nconcord_finalize\n"
        response = authed_client.post(
            "/v2/products/prod-1/recipe/validate",
            data=json.dumps({"content": valid_content}),
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["valid"] is True
        assert data["data"]["errors"] == []

    def test_validate_recipe_missing_sdk_returns_errors(self, authed_client, mock_db):
        """validate_recipe reports errors when SDK and lifecycle calls are missing."""
        mock_db.product.find_unique.return_value = make_obj(
            id="prod-1", name="Alpha", boards=[]
        )

        response = authed_client.post(
            "/v2/products/prod-1/recipe/validate",
            data=json.dumps({"content": "echo hello world"}),
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["valid"] is False
        assert len(data["data"]["errors"]) >= 3


class TestDiffRecipeVersions:
    """Tests for GET /v2/products/<id>/recipe/diff."""

    def test_diff_returns_unified_diff(self, authed_client, mock_db):
        """diff_recipe_versions returns unified diff between two versions."""
        mock_db.product.find_unique.return_value = _make_product()
        v1 = _make_recipe_version(version=1, content="echo v1\n")
        v2 = _make_recipe_version(version=2, content="echo v2\n")

        def _find_first(**kwargs):
            where = kwargs.get("where", {})
            if where.get("version") == 1:
                return v1
            return v2

        mock_db.recipeversion.find_first.side_effect = _find_first

        response = authed_client.get("/v2/products/prod-1/recipe/diff?from=1&to=2")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["hasChanges"] is True
        assert "diff" in data["data"]

    def test_diff_same_version_returns_400(self, authed_client, mock_db):
        """diff_recipe_versions returns 400 when from==to."""
        mock_db.product.find_unique.return_value = _make_product()

        response = authed_client.get("/v2/products/prod-1/recipe/diff?from=1&to=1")

        assert response.status_code == 400

    def test_diff_missing_params_returns_400(self, authed_client, mock_db):
        """diff_recipe_versions returns 400 when params are missing."""
        mock_db.product.find_unique.return_value = _make_product()

        response = authed_client.get("/v2/products/prod-1/recipe/diff?from=1")

        assert response.status_code == 400
