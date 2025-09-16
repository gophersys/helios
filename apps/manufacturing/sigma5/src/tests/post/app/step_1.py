# Standard includes
import json
from dataclasses import asdict, dataclass
from typing import Dict

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers

# Post test includes
from src.tests.post.data import PostTestSharedData


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class DeviceIds:
    accel_id: str = None
    altimeter_id: str = None
    app_ext_flash_id: str = None
    gps_hw_version: str = None
    ble_mac: str = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return DeviceIds(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_chip_ids(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    device_ids = DeviceIds()

    # Read
    accel_id, altimeter_id, app_ext_flash_id, gps_hw_version, ble_mac, error = (
        mtib_servers.sigma5_cmd_app_get_chip_ids(node)
    )
    if error:
        result.error = error
        result.details = device_ids.marshall()
        return result

    # Verify
    if accel_id != config.post_test_app_accel_chip_id:
        result.error = (
            f"Accelerometer chip ID {accel_id} does not match expected value {config.post_test_app_accel_chip_id}"
        )
        result.details = device_ids.marshall()
        return result

    if altimeter_id != config.post_test_app_altimeter_chip_id:
        result.error = (
            f"Altimeter chip ID {altimeter_id} does not match expected value {config.post_test_app_altimeter_chip_id}"
        )
        result.details = device_ids.marshall()
        return result

    if app_ext_flash_id != config.post_test_app_external_flash_chip_id:
        result.error = f"App external flash chip ID {app_ext_flash_id} does not match expected value {config.post_test_app_external_flash_chip_id}"
        result.details = device_ids.marshall()
        return result

    # Assign
    device_ids.accel_id = accel_id
    device_ids.altimeter_id = altimeter_id
    device_ids.app_ext_flash_id = app_ext_flash_id
    device_ids.ble_mac = ble_mac

    logging.debug(f"App accelerometer chip ID: {device_ids.accel_id}")
    logging.debug(f"App altimeter chip ID: {device_ids.altimeter_id}")
    logging.debug(f"App external flash chip ID: {device_ids.app_ext_flash_id}")
    logging.debug(f"App BLE MAC: {device_ids.ble_mac}")

    # Save user data
    usr_data[node].ble_mac = device_ids.ble_mac

    result.details = device_ids.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_1_verify_chip_ids: TestStep = TestStep(
    info=StepInfo(
        name="Verify chip IDs",
        description="Verify the chip are present and are correct.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_chip_ids,
)
