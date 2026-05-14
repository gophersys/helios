"""Tests for fixture design CRUD endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import make_obj


def _make_design(id="design-1", **overrides):
    defaults = {
        "name": "Alpha B0 Fixture",
        "boardRevisionId": "rev-1",
        "revision": "1.2",
        "profileTemplate": {"battery_installed": False},
        "schematicUrl": None,
        "bomUrl": None,
        "assemblyGuide": None,
        "notes": None,
        "createdAt": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "updatedAt": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "fixtures": [],
        "boardRevision": make_obj(
            id="rev-1", version="B0", ckBoardsName="alpha_b0",
            board=make_obj(name="Main Board", product=make_obj(name="Alpha")),
        ),
    }
    defaults.update(overrides)
    return make_obj(id=id, **defaults)


def test_list_designs(authed_client, mock_db):
    mock_db.testbeddesign.count.return_value = 1
    mock_db.testbeddesign.find_many.return_value = [_make_design()]

    resp = authed_client.get("/v2/test-bed-designs")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert len(data["data"]["data"]) == 1
    assert data["data"]["data"][0]["name"] == "Alpha B0 Fixture"
    assert data["data"]["data"][0]["boardRevisionId"] == "rev-1"
    assert data["data"]["data"][0]["productName"] == "Alpha"


def test_get_design(authed_client, mock_db):
    mock_db.testbeddesign.find_unique.return_value = _make_design()

    resp = authed_client.get("/v2/test-bed-designs/design-1")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["data"]["name"] == "Alpha B0 Fixture"
    assert data["data"]["fixtureCount"] == 0
    assert data["data"]["boardRevision"]["version"] == "B0"


def test_get_design_not_found(authed_client, mock_db):
    mock_db.testbeddesign.find_unique.return_value = None

    resp = authed_client.get("/v2/test-bed-designs/bad-id")
    assert resp.status_code == 404


@patch("api.v2.fixtures.designs.log_audit")
def test_create_design(mock_audit, authed_client, mock_db):
    mock_db.boardrevision.find_unique.return_value = make_obj(id="rev-1")
    mock_db.testbeddesign.find_unique.return_value = None  # no duplicate
    mock_db.testbeddesign.create.return_value = _make_design()

    resp = authed_client.post("/v2/test-bed-designs", data=json.dumps({
        "name": "Alpha B0 Fixture",
        "boardRevisionId": "rev-1",
        "revision": "1.2",
        "profileTemplate": {"battery_installed": False},
    }))
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["data"]["name"] == "Alpha B0 Fixture"
    mock_audit.assert_called_once()


def test_create_design_missing_name(authed_client, mock_db):
    resp = authed_client.post("/v2/test-bed-designs", data=json.dumps({
        "boardRevisionId": "rev-1",
        "revision": "1.2",
    }))
    assert resp.status_code == 400


@patch("api.v2.fixtures.designs.log_audit")
def test_create_design_duplicate_name(mock_audit, authed_client, mock_db):
    mock_db.boardrevision.find_unique.return_value = make_obj(id="rev-1")
    mock_db.testbeddesign.find_unique.return_value = _make_design()  # already exists

    resp = authed_client.post("/v2/test-bed-designs", data=json.dumps({
        "name": "Alpha B0 Fixture",
        "boardRevisionId": "rev-1",
        "revision": "1.2",
    }))
    assert resp.status_code == 409


@patch("api.v2.fixtures.designs.log_audit")
def test_update_design(mock_audit, authed_client, mock_db):
    mock_db.testbeddesign.find_unique.return_value = _make_design()
    mock_db.testbeddesign.update.return_value = _make_design(notes="Updated")

    resp = authed_client.patch("/v2/test-bed-designs/design-1", data=json.dumps({
        "notes": "Updated",
    }))
    assert resp.status_code == 200


@patch("api.v2.fixtures.designs.log_audit")
def test_delete_design(mock_audit, authed_client, mock_db):
    mock_db.testbeddesign.find_unique.return_value = _make_design(fixtures=[])

    resp = authed_client.delete("/v2/test-bed-designs/design-1")
    assert resp.status_code == 200


@patch("api.v2.fixtures.designs.log_audit")
def test_delete_design_has_fixtures(mock_audit, authed_client, mock_db):
    mock_db.testbeddesign.find_unique.return_value = _make_design(
        fixtures=[make_obj(id="fix-1", name="Fixture 1")],
    )

    resp = authed_client.delete("/v2/test-bed-designs/design-1")
    assert resp.status_code == 409
