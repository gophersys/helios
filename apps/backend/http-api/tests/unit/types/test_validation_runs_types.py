"""
Unit tests for validation run types in src/api/v2/sessions/types.py.

Tests all from_json() methods.
"""


# ── RunCreateRequest ─────────────────────────────────────


def test_run_create_valid():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {
        "name": "Alpha REV1.2 Debug",
        "productId": "prod-1",
        "nodeId": "node-1",
        "serialNumber": "70B3D584C01E1FCC",
        "firmwareVariant": "debug",
        "notes": "Stage 4 validation",
    }
    req, err = RunCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.name == "Alpha REV1.2 Debug"
    assert req.product_id == "prod-1"
    assert req.node_id == "node-1"
    assert req.serial_number == "70B3D584C01E1FCC"
    assert req.firmware_variant == "debug"
    assert req.notes == "Stage 4 validation"


def test_run_create_minimal():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {
        "name": "Test Run",
        "productId": "prod-1",
        "nodeId": "node-1",
        "serialNumber": "ABC123",
    }
    req, err = RunCreateRequest.from_json(data)

    assert err is None
    assert req is not None
    assert req.firmware_variant is None
    assert req.config is None
    assert req.notes is None
    assert req.test_filter is None


def test_run_create_missing_name():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {"productId": "prod-1", "nodeId": "node-1", "serialNumber": "ABC"}
    req, err = RunCreateRequest.from_json(data)
    assert req is None
    assert err == "Name is required"


def test_run_create_missing_product_id():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {"name": "Test", "nodeId": "node-1", "serialNumber": "ABC"}
    req, err = RunCreateRequest.from_json(data)
    assert req is None
    assert err == "productId is required"


def test_run_create_missing_node_id():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {"name": "Test", "productId": "prod-1", "serialNumber": "ABC"}
    req, err = RunCreateRequest.from_json(data)
    assert req is None
    assert err == "nodeId is required"


def test_run_create_missing_serial():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {"name": "Test", "productId": "prod-1", "nodeId": "node-1"}
    req, err = RunCreateRequest.from_json(data)
    assert req is None
    assert err == "serialNumber is required"


def test_run_create_empty_body():
    from src.api.v2.sessions.types import RunCreateRequest

    req, err = RunCreateRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = RunCreateRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_run_create_invalid_config():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {
        "name": "Test",
        "productId": "p",
        "nodeId": "n",
        "serialNumber": "s",
        "config": "not-a-dict",
    }
    req, err = RunCreateRequest.from_json(data)
    assert req is None
    assert err == "config must be an object"


def test_run_create_with_test_filter():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {
        "name": "Filtered",
        "productId": "p",
        "nodeId": "n",
        "serialNumber": "s",
        "testFilter": ["test_boot", "test_power"],
    }
    req, err = RunCreateRequest.from_json(data)
    assert err is None
    assert req.test_filter == ["test_boot", "test_power"]


def test_run_create_invalid_test_filter():
    from src.api.v2.sessions.types import RunCreateRequest

    data = {
        "name": "Test",
        "productId": "p",
        "nodeId": "n",
        "serialNumber": "s",
        "testFilter": "not-a-list",
    }
    req, err = RunCreateRequest.from_json(data)
    assert req is None
    assert err == "testFilter must be an array of test names"


# ── ReportStartRequest ───────────────────────────────────


def test_report_start_valid():
    from src.api.v2.sessions.types import ReportStartRequest

    req, err = ReportStartRequest.from_json({"started": True})
    assert err is None
    assert req is not None


def test_report_start_empty():
    from src.api.v2.sessions.types import ReportStartRequest

    req, err = ReportStartRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"


# ── ReportTestStartRequest ───────────────────────────────


def test_report_test_start_valid():
    from src.api.v2.sessions.types import ReportTestStartRequest

    data = {"testName": "test_boot.test_power_on", "module": "test_boot"}
    req, err = ReportTestStartRequest.from_json(data)
    assert err is None
    assert req.test_name == "test_boot.test_power_on"
    assert req.module == "test_boot"


def test_report_test_start_missing_name():
    from src.api.v2.sessions.types import ReportTestStartRequest

    req, err = ReportTestStartRequest.from_json({"module": "test_boot"})
    assert req is None
    assert err == "testName is required"


# ── ReportTestResultRequest ──────────────────────────────


def test_report_test_result_valid():
    from src.api.v2.sessions.types import ReportTestResultRequest

    data = {
        "testName": "test_power.test_boot_current",
        "passed": True,
        "durationS": 1.234,
        "measurements": {"currentMa": 33.5, "voltageV": 4.5},
    }
    req, err = ReportTestResultRequest.from_json(data)
    assert err is None
    assert req.test_name == "test_power.test_boot_current"
    assert req.passed is True
    assert req.duration_s == 1.234
    assert req.measurements["currentMa"] == 33.5


def test_report_test_result_missing_passed():
    from src.api.v2.sessions.types import ReportTestResultRequest

    data = {"testName": "test_boot"}
    req, err = ReportTestResultRequest.from_json(data)
    assert req is None
    assert err == "passed is required"


def test_report_test_result_passed_not_bool():
    from src.api.v2.sessions.types import ReportTestResultRequest

    data = {"testName": "test_boot", "passed": "yes"}
    req, err = ReportTestResultRequest.from_json(data)
    assert req is None
    assert err == "passed must be a boolean"


def test_report_test_result_invalid_duration():
    from src.api.v2.sessions.types import ReportTestResultRequest

    data = {"testName": "test_boot", "passed": True, "durationS": "fast"}
    req, err = ReportTestResultRequest.from_json(data)
    assert req is None
    assert err == "durationS must be a number"


# ── ReportFinishRequest ──────────────────────────────────


def test_report_finish_valid():
    from src.api.v2.sessions.types import ReportFinishRequest

    data = {"total": 37, "passed": 35, "failed": 2, "errors": 0, "durationS": 120.5}
    req, err = ReportFinishRequest.from_json(data)
    assert err is None
    assert req.total == 37
    assert req.passed == 35
    assert req.failed == 2
    assert req.errors == 0
    assert req.duration_s == 120.5


def test_report_finish_missing_total():
    from src.api.v2.sessions.types import ReportFinishRequest

    data = {"passed": 35, "failed": 2}
    req, err = ReportFinishRequest.from_json(data)
    assert req is None
    assert err == "total is required"


def test_report_finish_negative_values():
    from src.api.v2.sessions.types import ReportFinishRequest

    data = {"total": -1, "passed": 0, "failed": 0}
    req, err = ReportFinishRequest.from_json(data)
    assert req is None
    assert err == "total must be a non-negative integer"


# ── RunTriggerRequest ────────────────────────────────────


def test_trigger_empty_body():
    from src.api.v2.sessions.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json(None)
    assert req is None
    assert err == "Request body must contain JSON data"

    req, err = RunTriggerRequest.from_json({})
    assert req is None
    assert err == "Request body must contain JSON data"


def test_trigger_missing_firmware_version():
    from src.api.v2.sessions.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({"firmwarePath": "/path"})
    assert req is None
    assert err == "firmwareVersion is required"


def test_trigger_valid_minimal():
    from src.api.v2.sessions.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({"firmwareVersion": "0.1.12"})
    assert err is None
    assert req is not None
    assert req.firmware_version == "0.1.12"
    assert req.firmware_path is None
    assert req.config is None


def test_trigger_valid_full():
    from src.api.v2.sessions.types import RunTriggerRequest

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
    from src.api.v2.sessions.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({
        "firmwareVersion": "1.0",
        "config": "not-a-dict",
    })
    assert req is None
    assert err == "config must be an object"


def test_trigger_firmware_version_trimmed():
    from src.api.v2.sessions.types import RunTriggerRequest

    req, err = RunTriggerRequest.from_json({"firmwareVersion": "  0.1.12  "})
    assert err is None
    assert req.firmware_version == "0.1.12"
