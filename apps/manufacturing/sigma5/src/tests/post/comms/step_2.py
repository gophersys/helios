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
class ModemFw:
    fw_version: str = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return ModemFw(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_modem_fw(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    modem_fw = ModemFw()

    fw_version, error = mtib_servers.sigma5_cmd_comms_get_modem_fw_version(node)
    if error:
        result.error = error
        result.details = modem_fw.marshall()
        return result

    # Print the IDs out for debugging
    modem_fw.fw_version = fw_version

    logging.debug(f"Comms FW version: {modem_fw.fw_version}")

    # Remove the .zip from the fw_version
    flashed_fw_version = config.fw_flash_test_nrf9160_modem_fw_name.replace(".zip", "")

    # Compare the fw_version with the config.fw_flash_test_nrf9160_modem_fw_name
    if flashed_fw_version != modem_fw.fw_version:
        result.error = (
            f"Flashed modem fw version {flashed_fw_version} does not match expected version {modem_fw.fw_version}"
        )
        result.details = modem_fw.marshall()
        return result

    logging.info(f"Modem fw version verified: {modem_fw.fw_version}")

    result.details = modem_fw.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_2_verify_modem_fw: TestStep = TestStep(
    info=StepInfo(
        name="Verify modem fw",
        description="Verify the modem fw is flashed.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_modem_fw,
)
