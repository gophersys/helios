"""
Unit tests for catalog types validation in src/api/v2/catalog/types.py.

Tests all from_json() methods and to_update_data() methods.
"""

import pytest


# ── Product Types ──────────────────────────────────────


def test_product_create_valid():
    from src.api.v2.products.types import ProductCreateRequest

    data = {
        "name": "Sigma5 Device",
        "description": "IoT sensor",
        "active": True,
    }
    req, err = ProductCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Sigma5 Device"
    assert req.description == "IoT sensor"
    assert req.active is True


def test_product_create_missing_name():
    from src.api.v2.products.types import ProductCreateRequest

    data = {"description": "IoT sensor"}
    req, err = ProductCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_product_create_empty_body():
    from src.api.v2.products.types import ProductCreateRequest

    req, err = ProductCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    # Empty dict is also falsy in Python, so same error
    req, err = ProductCreateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = ProductCreateRequest.from_json({"name": ""})
    assert req is None
    assert err == "Name is required"


def test_product_create_active_non_bool():
    from src.api.v2.products.types import ProductCreateRequest

    data = {"name": "Product", "active": "true"}
    req, err = ProductCreateRequest.from_json(data)

    assert req is None
    assert err == "Active must be a boolean"


def test_product_update_valid():
    from src.api.v2.products.types import ProductUpdateRequest

    data = {"name": "Updated Product", "active": False}
    req, err = ProductUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated Product"
    assert req.active is False

    update_data = req.to_update_data()
    assert update_data == {"name": "Updated Product", "active": False}


def test_product_update_no_fields():
    from src.api.v2.products.types import ProductUpdateRequest

    req, err = ProductUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    # Empty dict is also falsy, so same error
    req, err = ProductUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_product_update_empty_name():
    from src.api.v2.products.types import ProductUpdateRequest

    data = {"name": "   "}
    req, err = ProductUpdateRequest.from_json(data)

    assert req is None
    assert err == "Name cannot be empty"


def test_product_update_to_update_data():
    from src.api.v2.products.types import ProductUpdateRequest

    data = {"description": None, "active": True}
    req, err = ProductUpdateRequest.from_json(data)

    assert err is None
    assert req is not None

    update_data = req.to_update_data()
    assert "description" in update_data
    assert update_data["description"] is None
    assert update_data["active"] is True
    assert "name" not in update_data


# ── Board Types ────────────────────────────────────────


def test_board_create_valid():
    from src.api.v2.products.types import BoardCreateRequest

    data = {"name": "Main Board", "ckBoardsFamily": "main_board", "description": "Primary PCB", "active": True}
    req, err = BoardCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Main Board"
    assert req.ckBoardsFamily == "main_board"
    assert req.vendor == "corekinect"
    assert req.description == "Primary PCB"
    assert req.active is True


def test_board_create_missing_name():
    from src.api.v2.products.types import BoardCreateRequest

    data = {"description": "A board"}
    req, err = BoardCreateRequest.from_json(data)

    assert req is None
    assert err == "Name is required"


def test_board_create_empty_body():
    from src.api.v2.products.types import BoardCreateRequest

    req, err = BoardCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


def test_board_update_valid():
    from src.api.v2.products.types import BoardUpdateRequest

    data = {"name": "Updated Board", "active": False}
    req, err = BoardUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated Board"
    assert req.active is False

    update_data = req.to_update_data()
    assert update_data == {"name": "Updated Board", "active": False}


def test_board_update_no_fields():
    from src.api.v2.products.types import BoardUpdateRequest

    req, err = BoardUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_board_update_empty_name():
    from src.api.v2.products.types import BoardUpdateRequest

    data = {"name": "   "}
    req, err = BoardUpdateRequest.from_json(data)

    assert req is None
    assert err == "Name cannot be empty"


# ── Board Revision Types ──────────────────────────────


def test_board_revision_create_valid():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"version": "v1.2", "ckBoardsName": "alpha_a0", "status": "ACTIVE"}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "v1.2"
    assert req.ckBoardsName == "alpha_a0"
    assert req.status == "ACTIVE"


def test_board_revision_create_missing_version():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"status": "ACTIVE"}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_board_revision_create_invalid_status():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"version": "v1.0", "ckBoardsName": "alpha_a0", "status": "INVALID_STATUS"}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Status must be ACTIVE, DEPRECATED, or EOL"


def test_board_revision_update_valid():
    from src.api.v2.products.types import BoardRevisionUpdateRequest

    data = {"version": "v2.0", "status": "DEPRECATED"}
    req, err = BoardRevisionUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "v2.0"
    assert req.status == "DEPRECATED"

    update_data = req.to_update_data()
    assert update_data["version"] == "v2.0"
    assert update_data["status"] == "DEPRECATED"


def test_board_revision_update_no_fields():
    from src.api.v2.products.types import BoardRevisionUpdateRequest

    req, err = BoardRevisionUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    # Empty dict is also falsy, so same error
    req, err = BoardRevisionUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_board_revision_update_to_update_data():
    from src.api.v2.products.types import BoardRevisionUpdateRequest

    data = {"notes": None}
    req, err = BoardRevisionUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "notes" in update_data
    assert update_data["notes"] is None


# ── Firmware Build Types ──────────────────────────────


def test_firmware_build_update_valid():
    from src.api.v2.products.types import FirmwareBuildUpdateRequest

    data = {"status": "RELEASED", "notes": "Production ready"}
    req, err = FirmwareBuildUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.status == "RELEASED"
    assert req.notes == "Production ready"

    update_data = req.to_update_data()
    assert update_data["status"] == "RELEASED"
    assert update_data["notes"] == "Production ready"


def test_firmware_build_update_invalid_status():
    from src.api.v2.products.types import FirmwareBuildUpdateRequest

    data = {"status": "INVALID_STATUS"}
    req, err = FirmwareBuildUpdateRequest.from_json(data)

    assert req is None
    assert err == "Status must be DRAFT, RELEASED, or DEPRECATED"


def test_firmware_build_update_no_fields():
    from src.api.v2.products.types import FirmwareBuildUpdateRequest

    req, err = FirmwareBuildUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    # Empty dict is also falsy, so same error
    req, err = FirmwareBuildUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_firmware_build_update_to_update_data():
    from src.api.v2.products.types import FirmwareBuildUpdateRequest

    data = {"notes": None}
    req, err = FirmwareBuildUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "notes" in update_data
    assert update_data["notes"] is None
    assert "status" not in update_data
