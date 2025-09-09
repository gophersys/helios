# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Post test includes
from src.tests.post.data import PostTestSharedData

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class BleInfo:
    rssi: str = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return BleInfo(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_ble_functionality(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    ble_info = BleInfo()

    # TODO: Implement
    # The `usr_data` variable can be used to pass in the expected MAC address from the step that
    # gets this info from the device.

    result.details = ble_info.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_5_verify_ble: TestStep = TestStep(
    info=StepInfo(
        name="Verify BLE",
        description="Verify chip broadcasts with the correct MAC address and a reasonable RSSI.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_ble_functionality,
)
