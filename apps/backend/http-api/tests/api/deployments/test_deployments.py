"""Integration tests for Deployments API."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import make_obj


def test_list_deployments(authed_client, mock_db):
    mock_db.deployment.count.return_value = 1
    mock_db.deployment.find_many.return_value = [
        make_obj(
            id="dep-1", name="Deploy 1", productId="prod-1", fixtureId="fix-1",
            status="PENDING", config=None, version="1.0",
            fixture=make_obj(id="fix-1", name="Fixture 1", product=make_obj(id="prod-1", name="Sigma5")),
            product=make_obj(id="prod-1", name="Sigma5"),
            createdBy=make_obj(id="user-1", name="Test User"),
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
    ]

    response = authed_client.get("/v2/cluster/managed-deployments")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["data"]["data"]) == 1


def test_create_deployment(authed_client, mock_db):
    mock_db.fixture.find_unique.return_value = make_obj(
        id="fix-1", name="Fixture 1", productId="prod-1",
        product=make_obj(id="prod-1", name="Sigma5"),
    )
    mock_db.deployment.create.return_value = make_obj(
        id="dep-new", name="New Deploy", productId="prod-1", fixtureId="fix-1",
        status="PENDING", config=None, version=None,
        fixture=make_obj(id="fix-1", name="Fixture 1", product=make_obj(id="prod-1", name="Sigma5")),
        product=make_obj(id="prod-1", name="Sigma5"),
        createdBy=make_obj(id="user-1", name="Test User"),
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("api.v2.deployments.deployments.log_audit"):
        response = authed_client.post("/v2/cluster/managed-deployments", data=json.dumps({
            "name": "New Deploy", "fixtureId": "fix-1",
        }))

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New Deploy"
    assert data["data"]["status"] == "PENDING"


def test_delete_deployment(authed_client, mock_db):
    mock_db.deployment.find_unique.return_value = make_obj(
        id="dep-del", name="Delete Me", productId="prod-1", fixtureId="fix-1",
        status="PENDING", config=None, version=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    with patch("api.v2.deployments.deployments.log_audit"):
        response = authed_client.delete("/v2/cluster/managed-deployments/dep-del")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True


def test_delete_running_deployment(authed_client, mock_db):
    mock_db.deployment.find_unique.return_value = make_obj(
        id="dep-running", name="Running", productId="prod-1", fixtureId="fix-1",
        status="RUNNING", config=None, version=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.delete("/v2/cluster/managed-deployments/dep-running")
    assert response.status_code == 409


def test_get_deployment(authed_client, mock_db):
    mock_db.deployment.find_unique.return_value = make_obj(
        id="dep-1", name="Deploy 1", productId="prod-1", fixtureId="fix-1",
        status="PENDING", config=None, version="1.0",
        fixture=make_obj(id="fix-1", name="Fixture 1", product=make_obj(id="prod-1", name="Sigma5")),
        product=make_obj(id="prod-1", name="Sigma5"),
        createdBy=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.get("/v2/cluster/managed-deployments/dep-1")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["id"] == "dep-1"
    assert data["data"]["fixtureName"] == "Fixture 1"
