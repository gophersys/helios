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
class Ublox:
    hw_version: str = None
    fw_version: str = None
    sw_version: str = None
    proto_version: str = None
    supported_constellations: List[str] = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return Ublox(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_ublox(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)
    ublox = Ublox()

    hw_version, fw_version, sw_version, proto_version, supported_constellations, error = (
        mtib_servers.sigma5_cmd_app_get_ublox_version_info(node)
    )
    if error:
        result.error = error
        result.details = ublox.marshall()
        return result

    # Print the IDs out for debugging
    ublox.hw_version = hw_version
    ublox.fw_version = fw_version
    ublox.sw_version = sw_version
    ublox.proto_version = proto_version
    ublox.supported_constellations = supported_constellations

    logging.debug(f"HW version: {ublox.hw_version}")
    logging.debug(f"FW version: {ublox.fw_version}")
    logging.debug(f"SW version: {ublox.sw_version}")
    logging.debug(f"Proto version: {ublox.proto_version}")
    logging.debug(f"Supported constellations: {ublox.supported_constellations}")

    result.details = ublox.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_2_verify_ublox: TestStep = TestStep(
    info=StepInfo(
        name="Verify ublox",
        description="Verify the ublox data.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_ublox,
)
