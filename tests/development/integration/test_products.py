"""Test product CRUD against real database.

Tests create, read, update, and response format validation.
"""

import pytest
import uuid


class TestListProducts:
    """Test product listing."""

    def test_list_products_returns_alpha(self, test_api, admin_headers):
        """GET /v2/products returns at least the seeded Alpha product."""
        resp = test_api.get("/v2/products", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "data" in body
        products = body["data"]["data"]
        assert isinstance(products, list)
        assert len(products) >= 1

    def test_list_products_pagination(self, test_api, admin_headers):
        """GET /v2/products respects page and limit params."""
        resp = test_api.get("/v2/products?page=1&limit=1", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        pagination = body["data"]["pagination"]
        assert pagination["page"] == 1
        assert pagination["limit"] == 1


class TestGetProduct:
    """Test product detail retrieval."""

    def test_get_product_includes_boards(self, test_api, admin_headers):
        """GET /v2/products/<id> returns boards, revisions, and stageConfigs."""
        # First get the product list to find Alpha's ID
        resp = test_api.get("/v2/products", headers=admin_headers)
        products = resp.get_json()["data"]["data"]
        alpha = next(p for p in products if p["name"] == "Alpha")

        detail_resp = test_api.get(f"/v2/products/{alpha['id']}", headers=admin_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.get_json()["data"]

        assert detail["name"] == "Alpha"
        assert "boards" in detail
        assert "stageConfigs" in detail
        assert isinstance(detail["boards"], list)
        assert isinstance(detail["stageConfigs"], list)

    def test_get_product_by_slug(self, test_api, admin_headers):
        """GET /v2/products/by-slug/alpha returns the Alpha product."""
        resp = test_api.get("/v2/products/by-slug/alpha", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "Alpha"
        assert data["slug"] == "alpha"

    def test_get_product_not_found(self, test_api, admin_headers):
        """GET /v2/products/<fake_id> returns 404."""
        fake_id = "clxxxxxxxxxxxxxxxxxxxxxxxxx"
        resp = test_api.get(f"/v2/products/{fake_id}", headers=admin_headers)
        assert resp.status_code == 404


class TestCreateProduct:
    """Test product creation against real DB."""

    def test_create_product(self, test_api, admin_headers):
        """POST /v2/products creates a product in the real DB."""
        unique_name = f"TestProduct-{uuid.uuid4().hex[:8]}"
        resp = test_api.post("/v2/products", headers=admin_headers, json={
            "name": unique_name,
            "slug": unique_name.lower().replace("-", "_"),
            "description": "Integration test product",
            "fwRepoSlug": "test_fw",
            "mfgFwRepoSlug": "test_mfg_fw",
        })
        assert resp.status_code == 201, f"Create failed: {resp.get_json()}"
        data = resp.get_json()["data"]
        assert data["name"] == unique_name
        product_id = data["id"]

        # Verify it persists — fetch it back
        get_resp = test_api.get(f"/v2/products/{product_id}", headers=admin_headers)
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["name"] == unique_name

    def test_create_product_missing_name(self, test_api, admin_headers):
        """POST /v2/products with no name returns 400."""
        resp = test_api.post("/v2/products", headers=admin_headers, json={
            "slug": "no_name",
        })
        assert resp.status_code == 400

    def test_create_product_duplicate_name(self, test_api, admin_headers):
        """POST /v2/products with duplicate name returns 409."""
        resp = test_api.post("/v2/products", headers=admin_headers, json={
            "name": "Alpha",
            "slug": "alpha_dup",
        })
        assert resp.status_code == 409


class TestUpdateProduct:
    """Test product updates."""

    def test_update_product_repo_slugs(self, test_api, admin_headers):
        """PUT /v2/products/<id> updates fwRepoSlug and mfgFwRepoSlug."""
        # Create a product to update
        unique_name = f"UpdateTest-{uuid.uuid4().hex[:8]}"
        create_resp = test_api.post("/v2/products", headers=admin_headers, json={
            "name": unique_name,
            "slug": unique_name.lower().replace("-", "_"),
            "fwRepoSlug": "old_fw",
        })
        assert create_resp.status_code == 201
        product_id = create_resp.get_json()["data"]["id"]

        # Update it
        update_resp = test_api.put(f"/v2/products/{product_id}", headers=admin_headers, json={
            "fwRepoSlug": "new_fw",
            "mfgFwRepoSlug": "new_mfg_fw",
        })
        assert update_resp.status_code == 200
        data = update_resp.get_json()["data"]
        assert data["fwRepoSlug"] == "new_fw"
        assert data["mfgFwRepoSlug"] == "new_mfg_fw"


class TestProductSerialization:
    """Test response format correctness."""

    def test_product_response_has_expected_fields(self, test_api, admin_headers):
        """Product response includes all expected fields with correct types."""
        resp = test_api.get("/v2/products", headers=admin_headers)
        products = resp.get_json()["data"]["data"]
        alpha = next(p for p in products if p["name"] == "Alpha")

        expected_fields = ["id", "name", "slug", "active", "createdAt"]
        for field in expected_fields:
            assert field in alpha, f"Missing field: {field}"

        assert isinstance(alpha["id"], str)
        assert isinstance(alpha["name"], str)
        assert isinstance(alpha["active"], bool)

    def test_api_response_envelope(self, test_api, admin_headers):
        """All responses use the {data, errors} envelope."""
        resp = test_api.get("/v2/products", headers=admin_headers)
        body = resp.get_json()
        assert "data" in body
        assert "errors" in body
        assert isinstance(body["errors"], list)
