"""Post-deploy smoke tests — verify critical endpoints are alive."""

import pytest


class TestHealth:
    def test_api_reachable(self, api):
        resp = api.get("/v2/healthcheck")
        assert resp.status_code == 200

    def test_docs_endpoint(self, api):
        resp = api.get("/v2/docs")
        assert resp.status_code == 200


class TestAuth:
    def test_api_key_works(self, api):
        resp = api.get("/v2/products")
        assert resp.status_code == 200

    def test_invalid_key_rejected(self, api, target_url):
        import requests as req
        resp = req.get(f"{target_url}/v2/products",
                      headers={"Authorization": "ApiKey invalid"},
                      verify=False)
        assert resp.status_code == 401


class TestData:
    def test_products_exist(self, api):
        resp = api.get("/v2/products")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["pagination"]["total"] >= 1

    def test_product_detail_loads(self, api):
        resp = api.get("/v2/products")
        products = resp.json()["data"]["data"]
        if not products:
            pytest.skip("No products in this environment")

        pid = products[0]["id"]
        detail = api.get(f"/v2/products/{pid}")
        assert detail.status_code == 200
        product = detail.json()["data"]
        assert "name" in product
        assert "slug" in product

    def test_permission_sets_exist(self, api):
        resp = api.get("/v2/permissions")
        assert resp.status_code == 200

    def test_fixtures_endpoint(self, api):
        resp = api.get("/v2/fixtures")
        assert resp.status_code == 200

    def test_sessions_endpoint(self, api):
        resp = api.get("/v2/sessions")
        assert resp.status_code == 200


class TestFrontend:
    def test_frontend_loads(self, target_url):
        import requests as req
        resp = req.get(target_url, verify=False)
        assert resp.status_code == 200
        assert "html" in resp.text.lower()
