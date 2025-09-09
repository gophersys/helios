# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers

# Post test includes
from src.tests.post.data import PostTestSharedData

# -------------------------------------------------
#                                           Config
# -------------------------------------------------
ACCELEROMETER_TOLERANCE = 0.5


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_accelerometer_data(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)

    sigma5_x_raw, sigma5_y_raw, sigma5_z_raw, sigma5_temp, error = mtib_servers.sigma5_cmd_app_read_accel(node)
    if error:
        result.error = error
        return result

    mtib_x_g, mtib_y_g, mtib_z_g, error = mtib_servers.read_accelerometer(node)
    if error:
        result.error = error
        return result

    # Adjust this based on actual sensor specs
    sigma5_scale_factor = 10

    # Map and scale Sigma5 values to match MTIB coordinate system
    # Based on the values, we need to map: Sigma5 X -> MTIB X, Sigma5 Y -> MTIB Z, Sigma5 Z -> MTIB Y
    sigma5_x_g = abs(sigma5_x_raw * sigma5_scale_factor)  # Sigma5 X -> MTIB X
    sigma5_y_g = abs(sigma5_z_raw * sigma5_scale_factor)  # Sigma5 Z -> MTIB Y (flip Y and Z)
    sigma5_z_g = abs(sigma5_y_raw * sigma5_scale_factor)  # Sigma5 Y -> MTIB Z (flip Y and Z)

    logging.debug(f"Sigma5 accelerometer data - X: {sigma5_x_g:.3f}g, Y: {sigma5_y_g:.3f}g, Z: {sigma5_z_g:.3f}g")
    logging.debug(f"MTIB accelerometer data - X: {mtib_x_g:.3f}g, Y: {mtib_y_g:.3f}g, Z: {mtib_z_g:.3f}g")

    # Compare values
    x_diff = abs(sigma5_x_g - abs(mtib_x_g)) if mtib_x_g is not None else float("inf")
    y_diff = abs(sigma5_y_g - abs(mtib_y_g)) if mtib_y_g is not None else float("inf")
    z_diff = abs(sigma5_z_g - abs(mtib_z_g)) if mtib_z_g is not None else float("inf")

    logging.debug(f"Accelerometer differences - X: {x_diff:.3f}g, Y: {y_diff:.3f}g, Z: {z_diff:.3f}g")

    if x_diff <= ACCELEROMETER_TOLERANCE and y_diff <= ACCELEROMETER_TOLERANCE and z_diff <= ACCELEROMETER_TOLERANCE:
        result.success = True
        logging.debug(f"Accelerometer verification passed - all values within ±{ACCELEROMETER_TOLERANCE}g tolerance")
    else:
        result.error = f"Accelerometer values don't match within ±{ACCELEROMETER_TOLERANCE}g tolerance. "
        result.error += f"X diff: {x_diff:.3f}g, Y diff: {y_diff:.3f}g, Z diff: {z_diff:.3f}g"
        return result

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_3_verify_accelerometer: TestStep = TestStep(
    info=StepInfo(
        name="Verify accelerometer",
        description="Verify X, Y, and Z match MTIB ±0.5 G's.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_accelerometer_data,
)
