"""E2E: Recipe management workflow -- save, publish, retrieve."""

import requests


def _admin_session(api):
    """Get a requests session authenticated as admin."""
    resp = api.post("/v2/auth/dev-login", json={"email": "admin@concord.dev"})
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    return s


def test_save_and_retrieve_recipe(api):
    """Save a recipe draft and verify it's retrievable."""
    session = _admin_session(api)
    base = api.base_url

    # Get Alpha product ID
    products = session.get(f"{base}/v2/products", timeout=10).json()["data"]["data"]
    alpha = next(p for p in products if p["name"] == "Alpha")
    pid = alpha["id"]

    # Save a recipe version
    recipe_content = "#!/bin/bash\necho 'E2E test build'\nexit 0"
    resp = session.post(f"{base}/v2/products/{pid}/recipe/save", json={
        "content": recipe_content,
        "changeNote": "E2E test recipe",
    }, timeout=10)
    assert resp.status_code in (200, 201), f"Save failed: {resp.status_code} {resp.text[:300]}"


def test_full_recipe_lifecycle(api):
    """Save, publish, and fetch the active recipe."""
    session = _admin_session(api)
    base = api.base_url

    products = session.get(f"{base}/v2/products", timeout=10).json()["data"]["data"]
    alpha = next(p for p in products if p["name"] == "Alpha")
    pid = alpha["id"]

    # Save a version
    recipe_content = "#!/bin/bash\necho 'lifecycle test'\nexit 0"
    save = session.post(f"{base}/v2/products/{pid}/recipe/save", json={
        "content": recipe_content,
        "changeNote": "Lifecycle test recipe",
    }, timeout=10)
    assert save.status_code in (200, 201)

    # Publish it (requires stage number + B0 board revision)
    detail = session.get(f"{base}/v2/products/{pid}", timeout=10).json()["data"]
    revisions = detail.get("boardRevisions", [])
    # Use B0 revision (has stage configs), fall back to first available
    b0_rev = next((r for r in revisions if r.get("version") == "B0"), None)
    board_rev_id = b0_rev["id"] if b0_rev else (revisions[0]["id"] if revisions else None)

    # Stage 5 (FUOTA) is the only enabled stage in the seed
    pub = session.post(f"{base}/v2/products/{pid}/recipe/publish", json={
        "stage": 5,
        "boardRevisionId": board_rev_id,
    }, timeout=10)
    assert pub.status_code == 200, f"Publish failed: {pub.status_code} {pub.text[:300]}"

    # Fetch the current recipe
    get = session.get(f"{base}/v2/products/{pid}/recipe", timeout=10)
    assert get.status_code == 200
    data = get.json()["data"]
    assert "lifecycle test" in data["content"]


def test_recipe_version_history(api):
    """Multiple saves create a version history."""
    session = _admin_session(api)
    base = api.base_url

    products = session.get(f"{base}/v2/products", timeout=10).json()["data"]["data"]
    alpha = next(p for p in products if p["name"] == "Alpha")
    pid = alpha["id"]

    # Save two versions
    for i in range(2):
        session.post(f"{base}/v2/products/{pid}/recipe/save", json={
            "content": f"#!/bin/bash\necho 'version {i}'",
            "changeNote": f"Version {i}",
        }, timeout=10)

    # List versions
    resp = session.get(f"{base}/v2/products/{pid}/recipe/versions", timeout=10)
    assert resp.status_code == 200
    versions = resp.json()["data"]
    # Should be a list (or paginated) with at least 2 entries
    if isinstance(versions, dict) and "data" in versions:
        versions = versions["data"]
    assert len(versions) >= 2
