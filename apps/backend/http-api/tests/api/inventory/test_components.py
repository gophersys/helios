"""Integration tests for Inventory Components API."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_obj


@pytest.fixture(autouse=True)
def _mock_presigned_url():
    """Mock presigned_url in inventory.shared so no real storage connection is made."""
    with patch("api.v2.inventory.shared.presigned_get_url", return_value=None):
        yield


def test_list_components(authed_client, mock_db):
    """Test listing components with pagination."""
    mock_db.inventorycomponent.count.return_value = 2
    mock_db.inventorycomponent.find_many.return_value = [
        make_obj(
            id="comp-1",
            name="Sigma5 SOM",
            description="Sigma5 system-on-module",
            category="SOM",
            manufacturer="CoreKinect",
            partNumber="SK-SIG5-001",
            imageKey=None,
            createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            revisions=[
                make_obj(
                    id="rev-1",
                    componentId="comp-1",
                    version="1.0",
                    status="ACTIVE",
                    releaseNotes=None,
                    createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                ),
            ],
        ),
        make_obj(
            id="comp-2",
            name="Alpha Carrier",
            description="Alpha carrier board",
            category="CARRIER_BOARD",
            manufacturer="CoreKinect",
            partNumber="CK-ALPHA-CB-001",
            imageKey=None,
            createdAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            updatedAt=datetime(2025, 1, 2, tzinfo=timezone.utc),
            revisions=[],
        ),
    ]

    response = authed_client.get("/v2/inventory/components")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert "data" in data
    assert "data" in data["data"]
    assert "pagination" in data["data"]
    assert len(data["data"]["data"]) == 2
    assert data["data"]["pagination"]["total"] == 2


def test_create_component(authed_client, mock_db):
    """Test creating a new component."""
    mock_db.inventorycomponent.find_first.return_value = None

    mock_db.inventorycomponent.create.return_value = make_obj(
        id="comp-new",
        name="New SOM",
        description="A new system-on-module",
        category="SOM",
        manufacturer="CoreKinect",
        partNumber="CK-NEW-001",
        imageKey=None,
        createdAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        revisions=[],
    )

    with patch("api.v2.inventory.components.log_audit"):
        response = authed_client.post(
            "/v2/inventory/components",
            data=json.dumps({
                "name": "New SOM",
                "description": "A new system-on-module",
                "category": "SOM",
                "manufacturer": "CoreKinect",
                "partNumber": "CK-NEW-001",
            }),
        )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["data"]["name"] == "New SOM"
    assert data["data"]["partNumber"] == "CK-NEW-001"


def test_create_component_duplicate_name(authed_client, mock_db):
    """Test creating component with duplicate name returns 409."""
    mock_db.inventorycomponent.find_first.return_value = make_obj(
        id="existing-comp",
        name="Existing SOM",
        description="",
        category="SOM",
        manufacturer="CoreKinect",
        partNumber="CK-PART-001",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    response = authed_client.post(
        "/v2/inventory/components",
        data=json.dumps({
            "name": "Existing SOM",
            "category": "SOM",
            "manufacturer": "CoreKinect",
            "partNumber": "CK-PART-002",
        }),
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0


def test_get_component(authed_client, mock_db):
    """Test getting a single component."""
    mock_db.inventorycomponent.find_unique.return_value = make_obj(
        id="comp-123",
        name="Test SOM",
        description="A test system-on-module",
        category="SOM",
        manufacturer="CoreKinect",
        partNumber="CK-TEST-123",
        imageKey=None,
        createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
        revisions=[
            make_obj(
                id="rev-1",
                componentId="comp-123",
                version="1.0",
                status="ACTIVE",
                releaseNotes="Initial version",
                createdAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 10, tzinfo=timezone.utc),
            ),
            make_obj(
                id="rev-2",
                componentId="comp-123",
                version="2.0",
                status="ACTIVE",
                releaseNotes="Updated version",
                createdAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 11, tzinfo=timezone.utc),
            ),
        ],
    )

    response = authed_client.get("/v2/inventory/components/comp-123")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["data"]["id"] == "comp-123"
    assert data["data"]["name"] == "Test SOM"
    assert "revisions" in data["data"]
    assert len(data["data"]["revisions"]) == 2


def test_update_component(authed_client, mock_db):
    """Test updating an existing component."""
    existing = make_obj(
        id="comp-update",
        name="Old Name",
        description="Old description",
        category="SOM",
        manufacturer="Old Mfg",
        partNumber="OLD-123",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    mock_db.inventorycomponent.find_unique.return_value = existing

    mock_db.inventorycomponent.update.return_value = make_obj(
        id="comp-update",
        name="Old Name",
        description="New description",
        category="CARRIER_BOARD",
        manufacturer="New Mfg",
        partNumber="OLD-123",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 15, tzinfo=timezone.utc),
        revisions=[],
    )

    with patch("api.v2.inventory.components.log_audit"):
        response = authed_client.put(
            "/v2/inventory/components/comp-update",
            data=json.dumps({
                "description": "New description",
                "category": "CARRIER_BOARD",
                "manufacturer": "New Mfg",
            }),
        )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["description"] == "New description"
    assert data["data"]["category"] == "CARRIER_BOARD"


def test_delete_component(authed_client, mock_db):
    """Test deleting a component with no BOM refs."""
    mock_db.inventorycomponent.find_unique.return_value = make_obj(
        id="comp-delete",
        name="Component to Delete",
        description="",
        category="SOM",
        manufacturer="CoreKinect",
        partNumber="CK-DEL-123",
        imageKey="inventory/components/comp-delete/hero.png",
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        revisions=[
            make_obj(
                id="rev-1",
                componentId="comp-delete",
                version="1.0",
                status="ACTIVE",
                releaseNotes=None,
                createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
        ],
    )

    mock_db.assemblyrevisioncomponent.find_first.return_value = None

    mock_storage = MagicMock()
    mock_storage.remove_object = MagicMock()

    with patch("api.v2.inventory.components.get_storage_client", return_value=mock_storage):
        with patch("api.v2.inventory.components.get_bucket_name", return_value="test-bucket"):
            with patch("api.v2.inventory.components.log_audit"):
                response = authed_client.delete("/v2/inventory/components/comp-delete")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["data"]["deleted"] is True

    mock_storage.remove_object.assert_called_once()


def test_delete_component_with_bom_refs(authed_client, mock_db):
    """Test deleting a component with BOM refs returns 409."""
    mock_db.inventorycomponent.find_unique.return_value = make_obj(
        id="comp-has-refs",
        name="Component with Refs",
        description="",
        category="SOM",
        manufacturer="CoreKinect",
        partNumber="CK-REF-123",
        imageKey=None,
        createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
        revisions=[
            make_obj(
                id="rev-1",
                componentId="comp-has-refs",
                version="1.0",
                status="ACTIVE",
                releaseNotes=None,
                createdAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updatedAt=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
        ],
    )

    mock_db.assemblyrevisioncomponent.find_first.return_value = make_obj(
        id="bom-1",
        inventoryRevisionId="rev-1",
    )

    response = authed_client.delete("/v2/inventory/components/comp-has-refs")
    assert response.status_code == 409
    data = json.loads(response.data)
    assert len(data["errors"]) > 0
