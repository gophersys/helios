# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers

# -------------------------------------------------
#                                            Config
# -------------------------------------------------
LORA_AVAILABLE = "yes"
EXT_FLASH_ID = "0xef 0x40 0x17"


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class DeviceIds:
    lora_available: str = None
    ext_flash_id: str = None

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

    # Read
    lora_available, ext_flash_id, error = mtib_servers.sigma5_cmd_comms_get_chip_ids(node)
    if error:
        result.error = error
        result.details = device_ids.marshall()
        return result

    # Verify
    if lora_available != LORA_AVAILABLE:
        result.error = f"LoRa available {lora_available} does not match expected value {LORA_AVAILABLE}"
        result.details = device_ids.marshall()
        return result

    if ext_flash_id != EXT_FLASH_ID:
        result.error = f"Ext flash ID {ext_flash_id} does not match expected value {EXT_FLASH_ID}"
        result.details = device_ids.marshall()
        return result

    # Assign
    device_ids.lora_available = lora_available
    device_ids.ext_flash_id = ext_flash_id

    logging.debug(f"Comms LoRa Available: {device_ids.lora_available}")
    logging.debug(f"Comms Ext Flash ID: {device_ids.ext_flash_id}")

    result.details = device_ids.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_1_verify_chip_ids: TestStep = TestStep(
    info=StepInfo(
        name="Verify chip IDs",
        description="Verify the chip are present and are correct.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_chip_ids,
)
