"""Integration tests for Fixtures API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def test_list_fixtures(authed_client, mock_db):
    mock_db.fixture.count.return_value = 1
    mock_db.fixture.find_many.return_value = [
        make_obj(
            id="fix-1", name="MFG Line 1", productId="prod-1", type="MANUFACTURING",
            description=None, active=True, metadata=None,
            product=make_obj(id="prod-1", name="Sigma5"),
            slots=[make_obj(id="s1", fixtureId="fix-1", slotIndex=0, label="Slot A", nodeId=None, active=True,
                          createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc), updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc))],
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
    ]

    response = authed_client.get("/v2/fixtures")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 1
    assert data["data"]["data"][0]["slotCount"] == 1


def test_create_fixture(authed_client, mock_db):
    mock_db.product.find_unique.return_value = make_obj(id="prod-1", name="Sigma5")
    mock_db.fixture.find_first.return_value = None
    mock_db.fixture.create.return_value = make_obj(
        id="fix-new", name="New Fixture", productId="prod-1", type="MANUFACTURING",
        description=None, active=True, metadata=None,
        product=make_obj(id="prod-1", name="Sigma5"),
        slots=[],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("api.v2.fixtures.fixtures.log_audit"):
        response = authed_client.post("/v2/fixtures", data=json.dumps({
            "name": "New Fixture", "productId": "prod-1", "type": "manufacturing",
        }))

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Fixture"


def test_get_fixture(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = make_obj(
        id="fix-1", name="Fixture 1", productId="prod-1", type="MANUFACTURING",
        description="Test fixture", active=True, metadata=None,
        product=make_obj(id="prod-1", name="Sigma5"),
        slots=[
            make_obj(id="s1", fixtureId="fix-1", slotIndex=0, label="A", nodeId=None, active=True,
                    createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc), updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        ],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.get("/v2/fixtures/fix-1")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["id"] == "fix-1"
    assert "slots" in data["data"]


def test_delete_fixture(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = make_obj(
        id="fix-del", name="Delete Me", productId="prod-1", type="MANUFACTURING",
        description=None, active=True, metadata=None,
        sessions=[], deployments=[],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("api.v2.fixtures.fixtures.log_audit"):
        response = authed_client.delete("/v2/fixtures/fix-del")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_fixture_with_active_sessions(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = make_obj(
        id="fix-active", name="Active", productId="prod-1", type="MANUFACTURING",
        description=None, active=True, metadata=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    # Only active sessions block deletion
    mock_db.manufacturingsession.count.return_value = 1

    response = authed_client.delete("/v2/fixtures/fix-active")
    assert response.status_code == 409


def test_assign_node_to_slot(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = make_obj(
        id="fix-1", name="Fixture", type="MANUFACTURING",
    )
    mock_db.fixtureslot.find_first.side_effect = [
        make_obj(id="slot-1", fixtureId="fix-1", slotIndex=0, label="A", nodeId=None, active=True),
        None,  # no existing assignment for this node
    ]
    mock_db.node.find_unique.return_value = make_obj(
        id="node-1", name="MTIB-01", hostname="host-1", type="MANUFACTURING", status="ONLINE",
    )
    mock_db.fixtureslot.update.return_value = make_obj(
        id="slot-1", fixtureId="fix-1", slotIndex=0, label="A", nodeId="node-1", active=True,
        node=make_obj(id="node-1", name="MTIB-01", hostname="host-1", type="MANUFACTURING", status="ONLINE"),
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )

    with patch("api.v2.fixtures.fixtures.log_audit"):
        response = authed_client.post("/v2/fixtures/fix-1/slots/slot-1/assign", data=json.dumps({"nodeId": "node-1"}))

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["nodeId"] == "node-1"
