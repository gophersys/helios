"""Unit tests for fixture types validation."""

import pytest


def test_fixture_create_valid():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    data = {"name": "MFG Line 1", "productId": "prod-1", "type": "manufacturing"}
    req, err = FixtureCreateRequest.from_json(data)
    assert err is None
    assert req.name == "MFG Line 1"
    assert req.productId == "prod-1"
    assert req.type == "MANUFACTURING"


def test_fixture_create_missing_name():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    req, err = FixtureCreateRequest.from_json({"productId": "p1", "type": "manufacturing"})
    assert req is None
    assert err == "Name is required"


def test_fixture_create_missing_product_id():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    req, err = FixtureCreateRequest.from_json({"name": "Fixture", "type": "manufacturing"})
    assert req is None
    assert err == "Product ID is required"


def test_fixture_create_invalid_type():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    req, err = FixtureCreateRequest.from_json({"name": "F", "productId": "p", "type": "INVALID"})
    assert req is None
    assert err == "Type must be MANUFACTURING or VALIDATION"


def test_fixture_create_with_slots():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    data = {"name": "F", "productId": "p", "type": "manufacturing", "slots": [{"slotIndex": 0, "label": "Slot A"}]}
    req, err = FixtureCreateRequest.from_json(data)
    assert err is None
    assert len(req.slots) == 1


def test_fixture_create_invalid_slots():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    data = {"name": "F", "productId": "p", "type": "manufacturing", "slots": "not-array"}
    req, err = FixtureCreateRequest.from_json(data)
    assert req is None
    assert err == "Slots must be an array"


def test_fixture_create_slot_missing_index():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    data = {"name": "F", "productId": "p", "type": "manufacturing", "slots": [{"label": "A"}]}
    req, err = FixtureCreateRequest.from_json(data)
    assert req is None
    assert "slotIndex" in err


def test_fixture_create_null_body():
    from src.api.v2.fixtures.types import FixtureCreateRequest
    req, err = FixtureCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_fixture_update_valid():
    from src.api.v2.fixtures.types import FixtureUpdateRequest
    data = {"name": "Updated", "active": False}
    req, err = FixtureUpdateRequest.from_json(data)
    assert err is None
    assert req.name == "Updated"
    assert req.active is False
    update = req.to_update_data()
    assert update["name"] == "Updated"
    assert update["active"] is False


def test_fixture_update_empty_name():
    from src.api.v2.fixtures.types import FixtureUpdateRequest
    req, err = FixtureUpdateRequest.from_json({"name": "   "})
    assert req is None
    assert err == "Name cannot be empty"


def test_fixture_update_invalid_active():
    from src.api.v2.fixtures.types import FixtureUpdateRequest
    req, err = FixtureUpdateRequest.from_json({"active": "yes"})
    assert req is None
    assert err == "Active must be a boolean"


def test_fixture_update_no_fields():
    from src.api.v2.fixtures.types import FixtureUpdateRequest
    req, err = FixtureUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_fixture_update_nullable_description():
    from src.api.v2.fixtures.types import FixtureUpdateRequest
    data = {"description": None}
    req, err = FixtureUpdateRequest.from_json(data)
    assert err is None
    update = req.to_update_data()
    assert "description" in update
    assert update["description"] is None


def test_slot_create_valid():
    from src.api.v2.fixtures.types import SlotCreateRequest
    req, err = SlotCreateRequest.from_json({"slotIndex": 0, "label": "Slot A"})
    assert err is None
    assert req.slotIndex == 0
    assert req.label == "Slot A"


def test_slot_create_missing_index():
    from src.api.v2.fixtures.types import SlotCreateRequest
    req, err = SlotCreateRequest.from_json({"label": "A"})
    assert req is None
    assert err == "slotIndex is required"


def test_slot_create_negative_index():
    from src.api.v2.fixtures.types import SlotCreateRequest
    req, err = SlotCreateRequest.from_json({"slotIndex": -1})
    assert req is None
    assert "non-negative" in err


def test_slot_update_valid():
    from src.api.v2.fixtures.types import SlotUpdateRequest
    data = {"label": "Updated Label", "active": False}
    req, err = SlotUpdateRequest.from_json(data)
    assert err is None
    assert req.label == "Updated Label"
    assert req.active is False
    update = req.to_update_data()
    assert update["label"] == "Updated Label"
    assert update["active"] is False


def test_slot_update_no_fields():
    from src.api.v2.fixtures.types import SlotUpdateRequest
    req, err = SlotUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_slot_update_null_body():
    from src.api.v2.fixtures.types import SlotUpdateRequest
    req, err = SlotUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_slot_update_invalid_active():
    from src.api.v2.fixtures.types import SlotUpdateRequest
    req, err = SlotUpdateRequest.from_json({"active": "yes"})
    assert req is None
    assert err == "Active must be a boolean"


def test_slot_update_nullable_label():
    from src.api.v2.fixtures.types import SlotUpdateRequest
    data = {"label": None}
    req, err = SlotUpdateRequest.from_json(data)
    assert err is None
    update = req.to_update_data()
    assert "label" in update
    assert update["label"] is None


def test_slot_update_to_update_data_selective():
    from src.api.v2.fixtures.types import SlotUpdateRequest
    data = {"active": True}
    req, err = SlotUpdateRequest.from_json(data)
    assert err is None
    update = req.to_update_data()
    assert update == {"active": True}
    assert "label" not in update


def test_slot_assign_valid():
    from src.api.v2.fixtures.types import SlotAssignRequest
    req, err = SlotAssignRequest.from_json({"nodeId": "node-123"})
    assert err is None
    assert req.nodeId == "node-123"


def test_slot_assign_null_unassign():
    from src.api.v2.fixtures.types import SlotAssignRequest
    req, err = SlotAssignRequest.from_json({"nodeId": None})
    assert err is None
    assert req.nodeId is None


def test_slot_assign_empty_string():
    from src.api.v2.fixtures.types import SlotAssignRequest
    req, err = SlotAssignRequest.from_json({"nodeId": "  "})
    assert req is None
    assert "empty" in err.lower()
