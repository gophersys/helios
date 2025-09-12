# Standard includes
import json
import time
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
def verify_ublox_module(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    ublox = Ublox()

    # Read with retry logic
    max_retries = 20  # 10 seconds total (20 * 0.5 seconds)
    retry_delay = 0.5

    for attempt in range(max_retries):
        hw_version, fw_version, sw_version, proto_version, supported_constellations, error = (
            mtib_servers.sigma5_cmd_app_get_ublox_version_info(node)
        )

        if error:
            result.error = error
            result.details = ublox.marshall()
            return result

        # Check if any of the results are empty, 0, or None
        if hw_version is None or hw_version == 0 or hw_version == "":

            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                time.sleep(retry_delay)
                continue
            else:
                # Last attempt failed, return error
                result.error = "Failed to get valid version info after retries - received empty/zero/None values"
                result.details = ublox.marshall()
                return result
        else:
            break  # Success - break out of retry loop

    # Verify
    if hw_version != config.post_test_app_gps_ublox_hw_version:
        result.error = (
            f"HW version {hw_version} does not match expected value {config.post_test_app_gps_ublox_hw_version}"
        )
        result.details = ublox.marshall()
        return result
    if fw_version != config.post_test_app_gps_ublox_fw_version:
        result.error = (
            f"FW version {fw_version} does not match expected value {config.post_test_app_gps_ublox_fw_version}"
        )
        result.details = ublox.marshall()
        return result
    if sw_version != config.post_test_app_gps_ublox_sw_version:
        result.error = (
            f"SW version {sw_version} does not match expected value {config.post_test_app_gps_ublox_sw_version}"
        )
        result.details = ublox.marshall()
        return result
    if proto_version != config.post_test_app_gps_ublox_proto_version:
        result.error = f"Proto version {proto_version} does not match expected value {config.post_test_app_gps_ublox_proto_version}"
        result.details = ublox.marshall()
        return result
    if supported_constellations != config.post_test_app_gps_ublox_constellations:
        result.error = f"Supported constellations {supported_constellations} does not match expected value {config.post_test_app_gps_ublox_constellations}"
        result.details = ublox.marshall()
        return result

    # Assign
    ublox.hw_version = hw_version
    ublox.fw_version = fw_version
    ublox.sw_version = sw_version
    ublox.proto_version = proto_version
    ublox.supported_constellations = supported_constellations

    logging.debug(f"Ublox HW version: {ublox.hw_version}")
    logging.debug(f"Ublox FW version: {ublox.fw_version}")
    logging.debug(f"Ublox SW version: {ublox.sw_version}")
    logging.debug(f"Ublox Proto version: {ublox.proto_version}")
    logging.debug(f"Ublox Supported constellations: {ublox.supported_constellations}")

    result.details = ublox.marshall()
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_2_verify_ublox: TestStep = TestStep(
    info=StepInfo(
        name="Verify ublox",
        description="Verify the ublox GPS module data.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_ublox_module,
)
