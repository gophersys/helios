"""
Unit tests for inventory types validation in src/api/v2/inventory/types.py.

Tests all from_json() methods and to_update_data() methods.
"""

import pytest


def test_component_create_valid():
    from src.api.v2.inventory.types import ComponentCreateRequest

    data = {
        "name": "nRF9160 SOM",
        "category": "SOM",
        "manufacturer": "Nordic",
        "partNumber": "NRF9160-SICA",
        "description": "LTE-M/NB-IoT SoM",
    }
    req, err = ComponentCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "nRF9160 SOM"
    assert req.category == "SOM"
    assert req.manufacturer == "Nordic"
    assert req.partNumber == "NRF9160-SICA"
    assert req.description == "LTE-M/NB-IoT SoM"


def test_component_create_missing_name():
    from src.api.v2.inventory.types import ComponentCreateRequest

    data = {"category": "SOM", "manufacturer": "Nordic", "partNumber": "ABC123"}
    req, err = ComponentCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_component_create_invalid_category():
    from src.api.v2.inventory.types import ComponentCreateRequest

    data = {
        "name": "Component",
        "category": "INVALID",
        "manufacturer": "Nordic",
        "partNumber": "ABC123",
    }
    req, err = ComponentCreateRequest.from_json(data)

    assert req is None
    assert err == "Category must be SOM, CARRIER_BOARD, or ACCESSORY"


def test_component_create_missing_manufacturer():
    from src.api.v2.inventory.types import ComponentCreateRequest

    data = {"name": "Component", "category": "SOM", "partNumber": "ABC123"}
    req, err = ComponentCreateRequest.from_json(data)

    assert req is None
    assert err == "Manufacturer is required"


def test_component_create_missing_part_number():
    from src.api.v2.inventory.types import ComponentCreateRequest

    data = {"name": "Component", "category": "SOM", "manufacturer": "Nordic"}
    req, err = ComponentCreateRequest.from_json(data)

    assert req is None
    assert err == "Part number is required"


def test_component_update_valid():
    from src.api.v2.inventory.types import ComponentUpdateRequest

    data = {"name": "Updated Component", "category": "ACCESSORY"}
    req, err = ComponentUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated Component"
    assert req.category == "ACCESSORY"

    update_data = req.to_update_data()
    assert update_data["name"] == "Updated Component"
    assert update_data["category"] == "ACCESSORY"


def test_component_update_no_fields():
    from src.api.v2.inventory.types import ComponentUpdateRequest

    req, err = ComponentUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = ComponentUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_component_update_empty_name():
    from src.api.v2.inventory.types import ComponentUpdateRequest

    data = {"name": "   "}
    req, err = ComponentUpdateRequest.from_json(data)

    assert req is None
    assert err == "Name cannot be empty"


def test_component_update_invalid_category():
    from src.api.v2.inventory.types import ComponentUpdateRequest

    data = {"category": "INVALID"}
    req, err = ComponentUpdateRequest.from_json(data)

    assert req is None
    assert err == "Category must be SOM, CARRIER_BOARD, or ACCESSORY"


def test_component_update_to_update_data():
    from src.api.v2.inventory.types import ComponentUpdateRequest

    data = {"description": None, "partNumber": "NEW-PART-123"}
    req, err = ComponentUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "description" in update_data
    assert update_data["description"] is None
    assert update_data["partNumber"] == "NEW-PART-123"


def test_revision_create_valid():
    from src.api.v2.inventory.types import RevisionCreateRequest

    data = {"version": "v1.0", "status": "ACTIVE", "releaseNotes": "Initial release"}
    req, err = RevisionCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "v1.0"
    assert req.status == "ACTIVE"
    assert req.releaseNotes == "Initial release"


def test_revision_create_missing_version():
    from src.api.v2.inventory.types import RevisionCreateRequest

    data = {"status": "ACTIVE"}
    req, err = RevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_revision_create_invalid_status():
    from src.api.v2.inventory.types import RevisionCreateRequest

    data = {"version": "v1.0", "status": "INVALID"}
    req, err = RevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Status must be ACTIVE, DEPRECATED, or EOL"


def test_revision_update_valid():
    from src.api.v2.inventory.types import RevisionUpdateRequest

    data = {"status": "DEPRECATED", "releaseNotes": "No longer supported"}
    req, err = RevisionUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.status == "DEPRECATED"

    update_data = req.to_update_data()
    assert update_data["status"] == "DEPRECATED"
    assert update_data["releaseNotes"] == "No longer supported"


def test_revision_update_no_fields():
    from src.api.v2.inventory.types import RevisionUpdateRequest

    req, err = RevisionUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = RevisionUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_revision_update_to_update_data():
    from src.api.v2.inventory.types import RevisionUpdateRequest

    data = {"releaseNotes": None}
    req, err = RevisionUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "releaseNotes" in update_data
    assert update_data["releaseNotes"] is None


def test_assembly_create_valid():
    from src.api.v2.inventory.types import AssemblyCreateRequest

    data = {"name": "Sigma5 Full Assembly", "description": "Complete device"}
    req, err = AssemblyCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Sigma5 Full Assembly"
    assert req.description == "Complete device"


def test_assembly_create_missing_name():
    from src.api.v2.inventory.types import AssemblyCreateRequest

    data = {"description": "Test"}
    req, err = AssemblyCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_assembly_update_valid():
    from src.api.v2.inventory.types import AssemblyUpdateRequest

    data = {"name": "Updated Assembly"}
    req, err = AssemblyUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated Assembly"

    update_data = req.to_update_data()
    assert update_data["name"] == "Updated Assembly"


def test_assembly_update_no_fields():
    from src.api.v2.inventory.types import AssemblyUpdateRequest

    req, err = AssemblyUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = AssemblyUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_assembly_update_to_update_data():
    from src.api.v2.inventory.types import AssemblyUpdateRequest

    data = {"description": None}
    req, err = AssemblyUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "description" in update_data
    assert update_data["description"] is None


def test_assembly_revision_create_valid():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {
        "version": "v1.0",
        "status": "ACTIVE",
        "bom": [
            {"inventoryRevisionId": "rev-1", "quantity": 2},
            {"inventoryRevisionId": "rev-2", "quantity": 1},
        ],
    }
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "v1.0"
    assert len(req.bom) == 2
    assert req.bom[0].inventoryRevisionId == "rev-1"
    assert req.bom[0].quantity == 2


def test_assembly_revision_create_missing_version():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {"status": "ACTIVE"}
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_assembly_revision_create_invalid_status():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {"version": "v1.0", "status": "INVALID"}
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Status must be ACTIVE, DEPRECATED, or EOL"


def test_assembly_revision_create_bom_duplicate_ids():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {
        "version": "v1.0",
        "bom": [
            {"inventoryRevisionId": "rev-1", "quantity": 1},
            {"inventoryRevisionId": "rev-1", "quantity": 2},
        ],
    }
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert "Duplicate inventoryRevisionId in BOM: rev-1" in err


def test_assembly_revision_create_bom_invalid_quantity_zero():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {
        "version": "v1.0",
        "bom": [{"inventoryRevisionId": "rev-1", "quantity": 0}],
    }
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Quantity must be between 1 and 1,000,000"


def test_assembly_revision_create_bom_invalid_quantity_negative():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {
        "version": "v1.0",
        "bom": [{"inventoryRevisionId": "rev-1", "quantity": -5}],
    }
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Quantity must be between 1 and 1,000,000"


def test_assembly_revision_create_bom_invalid_quantity_too_large():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {
        "version": "v1.0",
        "bom": [{"inventoryRevisionId": "rev-1", "quantity": 1_000_001}],
    }
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Quantity must be between 1 and 1,000,000"


def test_assembly_revision_create_bom_missing_inventory_revision_id():
    from src.api.v2.inventory.types import AssemblyRevisionCreateRequest

    data = {
        "version": "v1.0",
        "bom": [{"quantity": 1}],
    }
    req, err = AssemblyRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Each BOM item must have inventoryRevisionId"


def test_assembly_revision_update_valid():
    from src.api.v2.inventory.types import AssemblyRevisionUpdateRequest

    data = {"status": "DEPRECATED"}
    req, err = AssemblyRevisionUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.status == "DEPRECATED"

    update_data = req.to_update_data()
    assert update_data["status"] == "DEPRECATED"


def test_assembly_revision_update_no_fields():
    from src.api.v2.inventory.types import AssemblyRevisionUpdateRequest

    req, err = AssemblyRevisionUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = AssemblyRevisionUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_assembly_revision_update_to_update_data():
    from src.api.v2.inventory.types import AssemblyRevisionUpdateRequest

    data = {"releaseNotes": None, "version": "v2.0"}
    req, err = AssemblyRevisionUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "releaseNotes" in update_data
    assert update_data["releaseNotes"] is None
    assert update_data["version"] == "v2.0"
