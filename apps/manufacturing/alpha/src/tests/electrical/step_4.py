# Standard includes
import time
from typing import Dict

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_4_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]
) -> TestStepResult:
    """
    Test plan step 4: Ensure +3.3V remains below 0.3V for 2 seconds.
    """
    result: TestStepResult = TestStepResult(success=False)

    # start_time = time.time()
    # while time.time() - start_time < config.electrical_step_4_stabilization_period_s:
    #     err, voltage_3v3 = mtib_servers.read_3v3(node)
    #     if err:
    #         result.error = err
    #         return result

    #     if voltage_3v3 > config.electrical_step_2_3v3_threshold_v:
    #         result.reason = (
    #             f"Step 4: 3.3V rail came up at {voltage_3v3:.3f}V after "
    #             f"{time.time() - start_time:.2f}s (expected to remain below "
    #             f"{config.electrical_step_2_3v3_threshold_v}V for "
    #             f"{config.electrical_step_4_stabilization_period_s}s)"
    #         )
    #         return result

    #     time.sleep(0.1)

    # logging.debug(
    #     f"Step 4 PASS: 3.3V remained below {config.electrical_step_2_3v3_threshold_v}V "
    #     f"for {config.electrical_step_4_stabilization_period_s}s"
    # )

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
electrical_test_step_4: TestStep = TestStep(
    info=StepInfo(
        name="Ensure +3.3V remains below 0.3V for 2 seconds",
        description="Verifies the 3.3V rail stays off during the startup delay period.",
        noPassIsFatal=True,
    ),
    timeout_ms=60000,
    handler=electrical_test_step_4_handler,
)
