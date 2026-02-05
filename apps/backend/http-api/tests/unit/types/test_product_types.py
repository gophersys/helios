"""
Unit tests for product types validation in src/api/v2/products/types.py.

Tests all from_json() methods and to_update_data() methods.
"""

import pytest


def test_product_create_valid():
    from src.api.v2.products.types import ProductCreateRequest

    data = {"name": "Sigma5 Device", "description": "IoT sensor", "active": True}
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


def test_board_revision_create_valid():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"version": "v1.2", "chipsets": ["nRF9160", "nRF52840"], "status": "ACTIVE"}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.version == "v1.2"
    assert req.chipsets == ["nRF9160", "nRF52840"]
    assert req.status == "ACTIVE"


def test_board_revision_create_missing_version():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"chipsets": ["nRF9160"]}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Version is required"


def test_board_revision_create_invalid_status():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"version": "v1.0", "status": "INVALID_STATUS"}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert req is None
    assert err == "Status must be ACTIVE, DEPRECATED, or EOL"


def test_board_revision_create_invalid_chipset():
    from src.api.v2.products.types import BoardRevisionCreateRequest

    data = {"version": "v1.0", "chipsets": ["InvalidChipset"]}
    req, err = BoardRevisionCreateRequest.from_json(data)

    assert req is None
    assert "Unsupported SoC(s): InvalidChipset" in err


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


def test_board_revision_update_invalid_chipset():
    from src.api.v2.products.types import BoardRevisionUpdateRequest

    data = {"chipsets": ["InvalidChipset"]}
    req, err = BoardRevisionUpdateRequest.from_json(data)

    assert req is None
    assert "Unsupported SoC(s): InvalidChipset" in err


def test_board_revision_update_to_update_data():
    from src.api.v2.products.types import BoardRevisionUpdateRequest

    data = {"notes": None, "chipsets": ["nRF9160"]}
    req, err = BoardRevisionUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "notes" in update_data
    assert update_data["notes"] is None
    assert update_data["chipsets"] == ["nRF9160"]


def test_firmware_app_create_valid():
    from src.api.v2.products.types import FirmwareAppCreateRequest

    data = {
        "applicationId": 42,
        "name": "Sigma5 Main App",
        "targetMcu": "nRF9160",
        "chipset": "Sigma5 Cx",
    }
    req, err = FirmwareAppCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.applicationId == 42
    assert req.name == "Sigma5 Main App"
    assert req.targetMcu == "nRF9160"
    assert req.chipset == "Sigma5 Cx"


def test_firmware_app_create_missing_application_id():
    from src.api.v2.products.types import FirmwareAppCreateRequest

    data = {"name": "Test App"}
    req, err = FirmwareAppCreateRequest.from_json(data)

    assert req is None
    assert err == "Application ID is required"


def test_firmware_app_create_negative_application_id():
    from src.api.v2.products.types import FirmwareAppCreateRequest

    data = {"applicationId": -1, "name": "Test App"}
    req, err = FirmwareAppCreateRequest.from_json(data)

    assert req is None
    assert err == "Application ID must be a non-negative integer"


def test_firmware_app_create_invalid_chipset():
    from src.api.v2.products.types import FirmwareAppCreateRequest

    data = {"applicationId": 1, "name": "Test App", "chipset": "InvalidChipset"}
    req, err = FirmwareAppCreateRequest.from_json(data)

    assert req is None
    assert "Unsupported chipset: InvalidChipset" in err


def test_firmware_app_create_invalid_target_mcu_for_chipset():
    from src.api.v2.products.types import FirmwareAppCreateRequest

    data = {
        "applicationId": 1,
        "name": "Test App",
        "chipset": "Sigma5 Cx",
        "targetMcu": "nRF9151",  # Not valid for Sigma5 Cx
    }
    req, err = FirmwareAppCreateRequest.from_json(data)

    assert req is None
    assert "Target MCU 'nRF9151' is not valid for chipset 'Sigma5 Cx'" in err


def test_firmware_app_update_valid():
    from src.api.v2.products.types import FirmwareAppUpdateRequest

    data = {"name": "Updated App", "chipset": "Alpha Bx"}
    req, err = FirmwareAppUpdateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Updated App"
    assert req.chipset == "Alpha Bx"

    update_data = req.to_update_data()
    assert update_data["name"] == "Updated App"
    assert update_data["chipset"] == "Alpha Bx"


def test_firmware_app_update_no_fields():
    from src.api.v2.products.types import FirmwareAppUpdateRequest

    req, err = FirmwareAppUpdateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    # Empty dict is also falsy, so same error
    req, err = FirmwareAppUpdateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_firmware_app_update_invalid_chipset():
    from src.api.v2.products.types import FirmwareAppUpdateRequest

    data = {"chipset": "InvalidChipset"}
    req, err = FirmwareAppUpdateRequest.from_json(data)

    assert req is None
    assert "Unsupported chipset: InvalidChipset" in err


def test_firmware_app_update_to_update_data():
    from src.api.v2.products.types import FirmwareAppUpdateRequest

    data = {"notes": None, "targetMcu": "nRF52840"}
    req, err = FirmwareAppUpdateRequest.from_json(data)

    assert err is None
    update_data = req.to_update_data()
    assert "notes" in update_data
    assert update_data["notes"] is None
    assert update_data["targetMcu"] == "nRF52840"


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
