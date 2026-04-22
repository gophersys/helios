"""Test that the seed script populates expected data.

Every test hits the real database through the Flask test client.
"""

import pytest


CI_API_KEY = "ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG"


class TestSeedProducts:
    """Verify seeded product data."""

    def test_seed_creates_alpha_product(self, test_api, admin_headers):
        """Alpha product exists with correct slug and repo slugs."""
        resp = test_api.get("/v2/products", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        products = body["data"]["data"]
        assert len(products) >= 1

        alpha = next((p for p in products if p["name"] == "Alpha"), None)
        assert alpha is not None, "Alpha product not found"
        assert alpha["slug"] == "alpha"
        assert alpha["fwRepoSlug"] == "alpha_fw"
        assert alpha["mfgFwRepoSlug"] == "alpha_mfg_fw"
        assert alpha["active"] is True

    def test_seed_creates_board_revisions(self, test_api, admin_headers):
        """Alpha has A0 and B0 revisions with correct targets."""
        resp = test_api.get("/v2/products", headers=admin_headers)
        products = resp.get_json()["data"]["data"]
        alpha = next(p for p in products if p["name"] == "Alpha")

        # Get the full product with boards
        detail_resp = test_api.get(f"/v2/products/{alpha['id']}", headers=admin_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.get_json()["data"]

        boards = detail.get("boards", [])
        assert len(boards) >= 1, "Alpha must have at least one board"

        board = boards[0]
        revisions = board.get("revisions", [])
        rev_versions = [r["version"] for r in revisions]
        assert "A0" in rev_versions, "Missing A0 revision"
        assert "B0" in rev_versions, "Missing B0 revision"

    def test_seed_creates_stage_configs(self, test_api, admin_headers):
        """5 stages created, 3 enabled, linked to B0."""
        resp = test_api.get("/v2/products", headers=admin_headers)
        products = resp.get_json()["data"]["data"]
        alpha = next(p for p in products if p["name"] == "Alpha")

        stages_resp = test_api.get(f"/v2/products/{alpha['id']}/stages", headers=admin_headers)
        assert stages_resp.status_code == 200
        stages = stages_resp.get_json()["data"]
        assert len(stages) == 5

        enabled = [s for s in stages if s.get("enabled")]
        assert len(enabled) == 3

        stage_names = {s["name"] for s in stages}
        assert stage_names == {"Smoke", "Silicon", "Integration", "Nightly", "FUOTA"}


class TestSeedUsers:
    """Verify seeded user data."""

    def test_seed_creates_users_per_role(self, test_api, admin_headers):
        """Dev users exist: admin, maintainer, developer, operator."""
        resp = test_api.get("/v2/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.get_json()["data"]["data"]

        dev_emails = {u["email"] for u in users if u["email"].endswith("@concord.dev")}
        assert "admin@concord.dev" in dev_emails
        assert "maintainer@concord.dev" in dev_emails
        assert "developer@concord.dev" in dev_emails
        assert "operator@concord.dev" in dev_emails

    def test_seed_creates_team_members(self, test_api, admin_headers):
        """Real team members are seeded."""
        resp = test_api.get("/v2/users", headers=admin_headers)
        users = resp.get_json()["data"]["data"]
        emails = {u["email"] for u in users}
        assert "mateo@corekinect.com" in emails


class TestSeedFixtures:
    """Verify seeded fixture data."""

    def test_seed_creates_fixtures(self, test_api, admin_headers):
        """bench-33 and bench-32 fixtures exist."""
        resp = test_api.get("/v2/fixtures", headers=admin_headers)
        assert resp.status_code == 200
        fixtures = resp.get_json()["data"]

        # fixtures could be nested under "data" or be a direct list
        if isinstance(fixtures, dict) and "data" in fixtures:
            fixtures = fixtures["data"]

        station_ids = {f.get("stationId") for f in fixtures}
        assert "bench-33" in station_ids, "bench-33 fixture not found"
        assert "bench-32" in station_ids, "bench-32 fixture not found"


class TestSeedSigningKeys:
    """Verify seeded signing key data."""

    def test_seed_creates_signing_keys(self, test_api, admin_headers):
        """APP and COMMS signing keys exist."""
        resp = test_api.get("/v2/system/secrets", headers=admin_headers)
        assert resp.status_code == 200
        secrets = resp.get_json()["data"]

        if isinstance(secrets, dict) and "data" in secrets:
            secrets = secrets["data"]

        names = {s["name"] for s in secrets}
        assert "Alpha Bench Signing Key (APP)" in names
        assert "Alpha Bench Signing Key (COMMS)" in names


class TestSeedApiKey:
    """Verify CI API key works."""

    def test_seed_creates_ci_api_key(self, test_api):
        """CI API key works for authenticated requests."""
        headers = {"Authorization": f"ApiKey {CI_API_KEY}", "Content-Type": "application/json"}
        resp = test_api.get("/v2/products", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"] is not None
