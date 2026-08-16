"""
Unit tests for validation run types in src/api/v2/runs/types.py.

Tests all from_json() methods for the current CreateRunRequest model.
"""


# ── CreateRunRequest ─────────────────────────────────────


def test_run_create_valid():
    from src.api.v2.runs.types import CreateRunRequest

    data = {
        "type": "VALIDATION",
        "productId": "prod-1",
        "fixtureId": "fix-1",
        "serialNumber": "70B3D584C01E1FCC",
        "notes": "Stage 4 validation",
    }
    req, err = CreateRunRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.type == "VALIDATION"
    assert req.product_id == "prod-1"
    assert req.fixture_id == "fix-1"
    assert req.serial_number == "70B3D584C01E1FCC"
    assert req.notes == "Stage 4 validation"


def test_run_create_minimal():
    from src.api.v2.runs.types import CreateRunRequest

    data = {
        "type": "VALIDATION",
        "productId": "prod-1",
    }
    req, err = CreateRunRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.fixture_id is None
    assert req.serial_number is None
    assert req.config is None
    assert req.notes is None


def test_run_create_missing_type():
    from src.api.v2.runs.types import CreateRunRequest

    data = {"productId": "prod-1"}
    req, err = CreateRunRequest.from_json(data)
    assert req is None
    assert err == "type is required"


def test_run_create_invalid_type():
    from src.api.v2.runs.types import CreateRunRequest

    data = {"type": "UNKNOWN", "productId": "prod-1"}
    req, err = CreateRunRequest.from_json(data)
    assert req is None
    assert "type must be one of" in err


def test_run_create_missing_product_id():
    from src.api.v2.runs.types import CreateRunRequest

    data = {"type": "VALIDATION"}
    req, err = CreateRunRequest.from_json(data)
    assert req is None
    assert err == "productId is required"


def test_run_create_empty_body():
    from src.api.v2.runs.types import CreateRunRequest

    req, err = CreateRunRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = CreateRunRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_run_create_invalid_config():
    from src.api.v2.runs.types import CreateRunRequest

    data = {
        "type": "VALIDATION",
        "productId": "p",
        "config": "not-a-dict",
    }
    req, err = CreateRunRequest.from_json(data)
    assert req is None
    assert err == "config must be an object"


def test_run_create_manufacturing_type():
    from src.api.v2.runs.types import CreateRunRequest

    data = {
        "type": "MANUFACTURING",
        "productId": "prod-1",
        "fixtureId": "fix-1",
    }
    req, err = CreateRunRequest.from_json(data)
    assert err is None
    assert req.type == "MANUFACTURING"


def test_run_create_type_case_insensitive():
    from src.api.v2.runs.types import CreateRunRequest

    data = {
        "type": "validation",
        "productId": "prod-1",
    }
    req, err = CreateRunRequest.from_json(data)
    assert err is None
    assert req.type == "VALIDATION"


# ── RunTriggerRequest ────────────────────────────────────


def test_trigger_empty_body():
    from src.api.v2.runs.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = RunTriggerRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_trigger_missing_firmware_version():
    from src.api.v2.runs.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({"firmwarePath": "/path"})
    assert req is None
    assert err == "firmwareVersion is required"


def test_trigger_valid_minimal():
    from src.api.v2.runs.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({"firmwareVersion": "0.1.12"})
    assert err is None
    assert req is not None
    assert req.firmware_version == "0.1.12"
    assert req.firmware_path is None
    assert req.config is None


def test_trigger_valid_full():
    from src.api.v2.runs.types import RunTriggerRequest

    data = {
        "firmwareVersion": "0.1.12",
        "firmwarePath": "firmware/alpha/0.1.12/alpha-0.1.12.zip",
        "config": {"testEnable": {"electrical": True}},
    }
    req, err = RunTriggerRequest.from_json(data)
    assert err is None
    assert req.firmware_version == "0.1.12"
    assert req.firmware_path == "firmware/alpha/0.1.12/alpha-0.1.12.zip"
    assert req.config == {"testEnable": {"electrical": True}}


def test_trigger_invalid_config():
    from src.api.v2.runs.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({
        "firmwareVersion": "1.0",
        "config": "not-a-dict",
    })
    assert req is None
    assert err == "config must be an object"


def test_trigger_firmware_version_trimmed():
    from src.api.v2.runs.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({"firmwareVersion": "  0.1.12  "})
    assert err is None
    assert req.firmware_version == "0.1.12"
