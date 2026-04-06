"""Integration tests for the Fixture Designs API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


# ── Helpers ──────────────────────────────────────────────────


def _make_design(id="design-1", **overrides):
    defaults = {
        "name": "Alpha B0 Fixture",
        "product": "alpha",
        "revision": "1.2",
        "capabilities": ["button", "peltier", "charger_relay"],
        "profileTemplate": {"battery_installed": False},
        "schematicUrl": None,
        "bomUrl": None,
        "assemblyGuide": None,
        "notes": None,
        "createdAt": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "testBenches": [],
    }
    defaults.update(overrides)
    return make_obj(id=id, **defaults)


# ── List ─────────────────────────────────────────────────────


def test_list_designs(authed_client, mock_db):
    """GET /v2/fixtures/designs returns paginated fixture designs."""
    mock_db.fixturedesign.count.return_value = 2
    mock_db.fixturedesign.find_many.return_value = [
        _make_design(id="design-1", name="Alpha B0"),
        _make_design(id="design-2", name="Sigma5 A1", product="sigma5"),
    ]

    response = authed_client.get("/v2/fixtures/designs")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert len(data["errors"]) == 0

    payload = data["data"]
    assert "data" in payload
    assert "pagination" in payload
    assert len(payload["data"]) == 2
    assert payload["pagination"]["total"] == 2


def test_list_designs_unauthorized(client):
    """GET /v2/fixtures/designs without auth returns 401."""
    response = client.get("/v2/fixtures/designs")
    assert response.status_code == 401


# ── Get ──────────────────────────────────────────────────────


def test_get_design(authed_client, mock_db):
    """GET /v2/fixtures/designs/<id> returns design with bench count."""
    design = _make_design(
        id="design-123",
        testBenches=[
            make_obj(stationId="bench-1"),
            make_obj(stationId="bench-2"),
        ],
    )
    mock_db.fixturedesign.find_unique.return_value = design

    response = authed_client.get("/v2/fixtures/designs/design-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "design-123"
    assert data["data"]["name"] == "Alpha B0 Fixture"
    assert data["data"]["benchCount"] == 2
    assert data["data"]["capabilities"] == ["button", "peltier", "charger_relay"]


def test_get_design_not_found(authed_client, mock_db):
    """GET /v2/fixtures/designs/<id> returns 404 when not found."""
    mock_db.fixturedesign.find_unique.return_value = None

    response = authed_client.get("/v2/fixtures/designs/nonexistent")
    assert response.status_code == 404


# ── Create ───────────────────────────────────────────────────


def test_create_design(authed_client, mock_db):
    """POST /v2/fixtures/designs creates a new fixture design."""
    mock_db.fixturedesign.find_unique.return_value = None

    created = _make_design(id="design-new", name="New Design")
    mock_db.fixturedesign.create.return_value = created

    with patch("src.api.v2.fixtures.designs.log_audit"):
        response = authed_client.post(
            "/v2/fixtures/designs",
            data=json.dumps({
                "name": "New Design",
                "product": "alpha",
                "revision": "2.0",
                "capabilities": ["button"],
                "profileTemplate": {"battery_installed": True},
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["id"] == "design-new"
    assert data["data"]["name"] == "New Design"


def test_create_design_duplicate_name(authed_client, mock_db):
    """POST /v2/fixtures/designs returns 409 when name exists."""
    mock_db.fixturedesign.find_unique.return_value = _make_design(id="existing")

    response = authed_client.post(
        "/v2/fixtures/designs",
        data=json.dumps({
            "name": "Alpha B0 Fixture",
            "product": "alpha",
            "revision": "1.2",
        }),
    )
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_create_design_missing_name(authed_client, mock_db):
    """POST /v2/fixtures/designs returns 400 without name."""
    response = authed_client.post(
        "/v2/fixtures/designs",
        data=json.dumps({
            "product": "alpha",
            "revision": "1.0",
        }),
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


# ── Update ───────────────────────────────────────────────────


def test_update_design(authed_client, mock_db):
    """PATCH /v2/fixtures/designs/<id> updates design fields."""
    existing = _make_design(id="design-upd")
    mock_db.fixturedesign.find_unique.return_value = existing

    updated = _make_design(
        id="design-upd",
        notes="Updated notes",
        updatedAt=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    mock_db.fixturedesign.update.return_value = updated

    with patch("src.api.v2.fixtures.designs.log_audit"):
        response = authed_client.patch(
            "/v2/fixtures/designs/design-upd",
            data=json.dumps({"notes": "Updated notes"}),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["notes"] == "Updated notes"


def test_update_design_not_found(authed_client, mock_db):
    """PATCH /v2/fixtures/designs/<id> returns 404 when not found."""
    mock_db.fixturedesign.find_unique.return_value = None

    response = authed_client.patch(
        "/v2/fixtures/designs/missing",
        data=json.dumps({"notes": "x"}),
    )
    assert response.status_code == 404


# ── Delete ───────────────────────────────────────────────────


def test_delete_design(authed_client, mock_db):
    """DELETE /v2/fixtures/designs/<id> deletes design with no benches."""
    mock_db.fixturedesign.find_unique.return_value = _make_design(
        id="design-del", testBenches=[],
    )

    with patch("src.api.v2.fixtures.designs.log_audit"):
        response = authed_client.delete("/v2/fixtures/designs/design-del")

    assert response.status_code == 200
    mock_db.fixturedesign.delete.assert_called_once_with(where={"id": "design-del"})


def test_delete_design_not_found(authed_client, mock_db):
    """DELETE /v2/fixtures/designs/<id> returns 404 when not found."""
    mock_db.fixturedesign.find_unique.return_value = None

    response = authed_client.delete("/v2/fixtures/designs/nonexistent")
    assert response.status_code == 404


def test_delete_design_has_benches(authed_client, mock_db):
    """DELETE /v2/fixtures/designs/<id> returns 400 when benches use it."""
    mock_db.fixturedesign.find_unique.return_value = _make_design(
        id="design-used",
        testBenches=[
            make_obj(stationId="bench-1"),
            make_obj(stationId="bench-2"),
        ],
    )

    response = authed_client.delete("/v2/fixtures/designs/design-used")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
