# Standard includes
import json
import logging
from typing import List
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import TestStepResult

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import CMD_GET_MODEM_FW_VER_Response, runnners_controller


def verify_modem_fw(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    response: CMD_GET_MODEM_FW_VER_Response
    result.error, response = runnners_controller.dut_command_get_modem_fw(node)
    if result.error:
        return result

    expected_fw_version = config.fw_flash_test_nrf9160_modem_fw_name.strip(".zip")

    if not response.fw_version == expected_fw_version:
        result.reason = f"Modem FW mismatch: {response.fw_version} vs {expected_fw_version}"
        return result

    result.success = True
    return result
