# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class DeviceIds:
    # App Coproc
    lora_status: str = None
    app_ext_flash_id: str = None

    # Comms Coproc
    accel_id: str = None
    altimeter_id: str = None
    comms_ext_flash_id: str = None
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
def verify_chip_ids(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)
    device_ids = DeviceIds()

    # App Coproc
    lora_status, app_ext_flash_id, error = mtib_servers.sigma5_cmd_app_get_chip_ids(node)
    if error:
        result.error = error
        result.details = device_ids.marshall()
        return result

    # Comms Coproc
    accel_id, altimeter_id, comms_ext_flash_id, gps_hw_version, ble_mac, error = (
        mtib_servers.sigma5_cmd_comms_get_chip_ids(node)
    )
    if error:
        result.error = error
        result.details = device_ids.marshall()
        return result

    #
    device_ids.lora_status = lora_status
    device_ids.app_ext_flash_id = app_ext_flash_id
    device_ids.accel_id = accel_id
    device_ids.altimeter_id = altimeter_id
    device_ids.comms_ext_flash_id = comms_ext_flash_id
    device_ids.gps_hw_version = gps_hw_version
    device_ids.ble_mac = ble_mac

    logging.debug(f"LoRa status: {device_ids.lora_status}")
    logging.debug(f"App External Flash IC ID: {device_ids.app_ext_flash_id}")
    logging.debug(f"Accel ID: {device_ids.accel_id}")
    logging.debug(f"Altimeter ID: {device_ids.altimeter_id}")
    logging.debug(f"Comms External Flash IC ID: {device_ids.comms_ext_flash_id}")
    logging.debug(f"GPS HW Version: {device_ids.gps_hw_version}")
    logging.debug(f"BLE MAC: {device_ids.ble_mac}")

    result.details = device_ids.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
step_1_verify_chip_ids: TestStep = TestStep(
    info=StepInfo(
        name="Verify chip IDs",
        description="Verify the chip are present and are correct.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_chip_ids,
)
