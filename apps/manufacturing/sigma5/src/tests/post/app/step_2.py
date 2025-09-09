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
UBLOX_HW_VERSION = "00080000"
UBLOX_FW_VERSION = "FWVER=SPG 3.01"
UBLOX_SW_VERSION = "ROM CORE 3.01 (107888)"
UBLOX_PROTO_VERSION = "PROTVER=18.00"
UBLOX_SUPPORTED_CONSTELATIONS = "GPS;GLO;GAL;BDS;SBAS;IMES;QZSS"


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class Ublox:
    hw_version: str = None
    fw_version: str = None
    sw_version: str = None
    proto_version: str = None
    supported_constellations: str = None

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

    # Read
    hw_version, fw_version, sw_version, proto_version, supported_constellations, error = (
        mtib_servers.sigma5_cmd_app_get_ublox_version_info(node)
    )
    if error:
        result.error = error
        result.details = ublox.marshall()
        return result

    # Verify
    if hw_version != UBLOX_HW_VERSION:
        result.error = f"HW version {hw_version} does not match expected value {UBLOX_HW_VERSION}"
        result.details = ublox.marshall()
        return result
    if fw_version != UBLOX_FW_VERSION:
        result.error = f"FW version {fw_version} does not match expected value {UBLOX_FW_VERSION}"
        result.details = ublox.marshall()
        return result
    if sw_version != UBLOX_SW_VERSION:
        result.error = f"SW version {sw_version} does not match expected value {UBLOX_SW_VERSION}"
        result.details = ublox.marshall()
        return result
    if proto_version != UBLOX_PROTO_VERSION:
        result.error = f"Proto version {proto_version} does not match expected value {UBLOX_PROTO_VERSION}"
        result.details = ublox.marshall()
        return result
    if supported_constellations != UBLOX_SUPPORTED_CONSTELATIONS:
        result.error = f"Supported constellations {supported_constellations} does not match expected value {UBLOX_SUPPORTED_CONSTELATIONS}"
        result.details = ublox.marshall()
        return result

    # Assign
    ublox.hw_version = hw_version
    ublox.fw_version = fw_version
    ublox.sw_version = sw_version
    ublox.proto_version = proto_version
    ublox.supported_constellations = supported_constellations

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
