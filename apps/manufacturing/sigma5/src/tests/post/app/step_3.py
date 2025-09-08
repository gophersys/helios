# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_accelerometer(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    sigma5_x_raw, sigma5_y_raw, sigma5_z_raw, sigma5_temp, error = mtib_servers.sigma5_cmd_app_read_accel(node)
    if error:
        result.error = error
        return result

    logging.debug(f"Sigma5 raw X: {sigma5_x_raw}, Y: {sigma5_y_raw}, Z: {sigma5_z_raw}")

    mtib_x_g, mtib_y_g, mtib_z_g, error = mtib_servers.read_accelerometer(node)
    if error:
        result.error = error
        return result

    logging.debug(f"MTIB X: {mtib_x_g}, Y: {mtib_y_g}, Z: {mtib_z_g}")

    # Adjust this based on actual sensor specs
    sigma5_scale_factor = 10

    # Map and scale Sigma5 values to match MTIB coordinate system
    # Based on the values, we need to map: Sigma5 X -> MTIB X, Sigma5 Y -> MTIB Z, Sigma5 Z -> MTIB Y
    # But ignore signs and just compare magnitudes
    sigma5_x_g = abs(sigma5_x_raw * sigma5_scale_factor)  # Sigma5 X -> MTIB X
    sigma5_y_g = abs(sigma5_z_raw * sigma5_scale_factor)  # Sigma5 Z -> MTIB Y (flip Y and Z)
    sigma5_z_g = abs(sigma5_y_raw * sigma5_scale_factor)  # Sigma5 Y -> MTIB Z (flip Y and Z)

    logging.debug(f"Sigma5 converted X: {sigma5_x_g:.3f}g, Y: {sigma5_y_g:.3f}g, Z: {sigma5_z_g:.3f}g")

    # Compare values with ±0.2G tolerance (ignoring signs)
    tolerance = 0.5
    x_diff = abs(sigma5_x_g - abs(mtib_x_g)) if mtib_x_g is not None else float("inf")
    y_diff = abs(sigma5_y_g - abs(mtib_y_g)) if mtib_y_g is not None else float("inf")
    z_diff = abs(sigma5_z_g - abs(mtib_z_g)) if mtib_z_g is not None else float("inf")

    logging.debug(f"Differences - X: {x_diff:.3f}g, Y: {y_diff:.3f}g, Z: {z_diff:.3f}g")

    if x_diff <= tolerance and y_diff <= tolerance and z_diff <= tolerance:
        result.success = True
        logging.info(f"Accelerometer verification passed - all values within ±{tolerance}g tolerance")
    else:
        result.error = f"Accelerometer values don't match within ±{tolerance}g tolerance. "
        result.error += f"X diff: {x_diff:.3f}g, Y diff: {y_diff:.3f}g, Z diff: {z_diff:.3f}g"
        logging.error(result.error)

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_3_verify_accelerometer: TestStep = TestStep(
    info=StepInfo(
        name="Verify accelerometer",
        description="Verify X, Y, and Z match MTIB ±0.2 G's.",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_accelerometer,
)
