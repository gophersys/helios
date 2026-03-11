"""Integration tests for Nodes API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def test_list_nodes(authed_client, mock_db):
    mock_db.node.count.return_value = 1
    mock_db.node.find_many.return_value = [
        make_obj(
            id="node-1", name="MTIB-01", hostname="verdin-imx8mm-001",
            type="MANUFACTURING", status="ONLINE", ipAddress="10.4.45.1",
            hardwareRevision="REV1.1", metadata=None, fixtureSlot=None,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
    ]

    response = authed_client.get("/v2/devices/mtibs")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 1
    assert data["data"]["pagination"]["total"] == 1


def test_create_node(authed_client, mock_db):
    mock_db.node.find_first.return_value = None
    mock_db.node.create.return_value = make_obj(
        id="node-new", name="MTIB-02", hostname="verdin-imx8mm-002",
        type="VALIDATION", status="ONLINE", ipAddress="10.4.45.2",
        hardwareRevision=None, metadata=None, fixtureSlot=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("api.v2.nodes.nodes.log_audit"):
        response = authed_client.post("/v2/devices/mtibs", data=json.dumps({
            "name": "MTIB-02", "hostname": "verdin-imx8mm-002", "type": "VALIDATION",
        }))

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["hostname"] == "verdin-imx8mm-002"


def test_create_node_duplicate_hostname(authed_client, mock_db):
    mock_db.node.find_first.return_value = make_obj(
        id="existing", name="Existing", hostname="host-dup",
        type="MANUFACTURING", status="ONLINE", ipAddress=None,
        hardwareRevision=None, metadata=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post("/v2/devices/mtibs", data=json.dumps({
        "name": "New Node", "hostname": "host-dup", "type": "MANUFACTURING",
    }))

    assert response.status_code == 409


def test_get_node(authed_client, mock_db):
    mock_db.node.find_unique.return_value = make_obj(
        id="node-1", name="MTIB-01", hostname="verdin-001",
        type="MANUFACTURING", status="ONLINE", ipAddress="10.4.45.1",
        hardwareRevision="REV1.1", metadata=None, fixtureSlot=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.get("/v2/devices/mtibs/node-1")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["id"] == "node-1"


def test_get_node_not_found(authed_client, mock_db):
    mock_db.node.find_unique.return_value = None
    response = authed_client.get("/v2/devices/mtibs/nonexistent")
    assert response.status_code == 404


def test_update_node(authed_client, mock_db):
    mock_db.node.find_unique.return_value = make_obj(
        id="node-1", name="Old Name", hostname="host",
        type="MANUFACTURING", status="ONLINE", ipAddress=None,
        hardwareRevision=None, metadata=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.node.update.return_value = make_obj(
        id="node-1", name="New Name", hostname="host",
        type="MANUFACTURING", status="ONLINE", ipAddress=None,
        hardwareRevision=None, metadata=None, fixtureSlot=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )

    with patch("api.v2.nodes.nodes.log_audit"):
        response = authed_client.put("/v2/devices/mtibs/node-1", data=json.dumps({"name": "New Name"}))

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Name"


def test_delete_node(authed_client, mock_db):
    mock_db.node.find_unique.return_value = make_obj(
        id="node-del", name="To Delete", hostname="host-del",
        type="MANUFACTURING", status="OFFLINE", ipAddress=None,
        hardwareRevision=None, metadata=None, testExecutions=[],
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("api.v2.nodes.nodes.log_audit"):
        response = authed_client.delete("/v2/devices/mtibs/node-del")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True
