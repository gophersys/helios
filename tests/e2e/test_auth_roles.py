"""E2E: Role-based access control across the real platform."""

import requests


def test_admin_login_and_access(api):
    """Admin can dev-login and access /me."""
    resp = api.post("/v2/auth/dev-login", json={"email": "admin@concord.dev"})
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]

    me = requests.get(
        f"{api.base_url}/v2/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert me.status_code == 200
    data = me.json()["data"]
    assert data["role"] == "ADMIN"
    assert data["email"] == "admin@concord.dev"


def test_all_roles_can_login(api):
    """Each seeded role can log in and get a valid token."""
    emails = [
        ("admin@concord.dev", "ADMIN"),
        ("maintainer@concord.dev", "MAINTAINER"),
        ("developer@concord.dev", "DEVELOPER"),
        ("operator@concord.dev", "OPERATOR"),
    ]
    for email, expected_role in emails:
        resp = api.post("/v2/auth/dev-login", json={"email": email})
        assert resp.status_code == 200, f"Login failed for {email}"
        body = resp.json()["data"]
        assert body["user"]["role"] == expected_role
        assert body["token"]


def test_roles_with_products_view_can_read_products(api):
    """Roles with products:view can list products; operator cannot."""
    can_view = [
        "admin@concord.dev",
        "maintainer@concord.dev",
        "developer@concord.dev",
    ]
    for email in can_view:
        login = api.post("/v2/auth/dev-login", json={"email": email})
        token = login.json()["data"]["token"]

        resp = requests.get(
            f"{api.base_url}/v2/products",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert resp.status_code == 200, f"{email} couldn't read products: {resp.status_code}"


def test_operator_cannot_read_products(api):
    """Operator role lacks products:view — should get 403."""
    login = api.post("/v2/auth/dev-login", json={"email": "operator@concord.dev"})
    token = login.json()["data"]["token"]

    resp = requests.get(
        f"{api.base_url}/v2/products",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert resp.status_code == 403


def test_invalid_login_rejected(api):
    """Non-existent user gets a 404."""
    resp = api.post("/v2/auth/dev-login", json={"email": "nobody@concord.dev"})
    assert resp.status_code == 404
