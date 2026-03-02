# Standard includes
from typing import Dict

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig
from ..shared.rpcs import mtib_servers

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_5_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 5: Verify GPS (GNSS) module communication.
    Ensure GPS is not in shutdown and comms are OK.
    """
    result: TestStepResult = TestStepResult(success=False)

    gps_data, error = mtib_servers.theta_app_cmd_test_gps(node)
    if error:
        result.error = f"GPS test failed: {error}"
        return result

    if not gps_data:
        result.reason = "GPS test returned no data"
        return result

    in_shutdown = gps_data.get("shutdown", True)
    comms_ok = gps_data.get("comms_ok", False)

    if in_shutdown:
        result.reason = "GPS is in shutdown mode - communication failed"
        return result

    logging.debug(
        f"POST Step 5 PASS: GPS shutdown={in_shutdown}, "
        f"tracking={gps_data.get('tracking')}, comms={'OK' if comms_ok else 'FAIL'}"
    )

    result.success = True
    result.details = f"comms_ok={comms_ok}"
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_5_gps: TestStep = TestStep(
    info=StepInfo(
        name="Verify GPS module",
        description="Tests GPS module on the app processor, verifying communication is functional.",
        noPassIsFatal=True,
    ),
    timeout_ms=15000,
    handler=post_step_5_handler,
)
