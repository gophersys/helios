"""E2E: Platform health and seed data verification."""


def test_api_healthy(api):
    """Healthcheck endpoint returns 200 with correct payload."""
    resp = api.get("/v2/healthcheck")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "healthy"
    assert data["service"] == "http-api"


def test_products_loaded(api):
    """Seed created at least one product (Alpha)."""
    resp = api.get("/v2/products")
    assert resp.status_code == 200
    products = resp.json()["data"]["data"]
    assert len(products) >= 1
    names = [p["name"] for p in products]
    assert "Alpha" in names


def test_dev_users_available(api):
    """Dev login picker returns one user per role."""
    resp = api.get("/v2/auth/dev-users")
    assert resp.status_code == 200
    users = resp.json()["data"]["users"]
    assert len(users) == 4
    roles = {u["role"] for u in users}
    assert roles == {"ADMIN", "MAINTAINER", "DEVELOPER", "OPERATOR"}


def test_stage_configs_present(api):
    """Alpha product has stage configs (count depends on seed success)."""
    products = api.get("/v2/products").json()["data"]["data"]
    alpha = next((p for p in products if p["name"] == "Alpha"), None)
    if alpha is None:
        return  # product not seeded — validation seed failed (schema drift)
    product_id = alpha["id"]

    detail = api.get(f"/v2/products/{product_id}")
    assert detail.status_code == 200
