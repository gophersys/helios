# Standard includes
import json
from dataclasses import asdict, dataclass
from typing import List

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class ImeiIccids:
    imei: str = None
    iccids: List[str] = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return ImeiIccids(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_imei_iccids(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)
    device_ids = ImeiIccids()

    imei, iccids, error = mtib_servers.sigma5_cmd_comms_get_imei_iccid(node)
    if error:
        result.error = error
        result.details = device_ids.marshall()
        return result

    device_ids.imei = imei
    device_ids.iccids = iccids

    logging.debug(f"IMEI: {device_ids.imei}")
    logging.debug(f"ICCID: {device_ids.iccids}")

    result.details = device_ids.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_3_verify_imei_iccids: TestStep = TestStep(
    info=StepInfo(
        name="Verify IMEI ICCIDs",
        description="Verify the IMEI and ICCIDs are present and are corre3ct.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_imei_iccids,
)
