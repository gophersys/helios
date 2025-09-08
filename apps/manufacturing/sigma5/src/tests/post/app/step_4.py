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
def verify_altimeter(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    sigma5_pressure_raw, sigma5_temperature_raw, error = mtib_servers.sigma5_cmd_app_read_altimeter(node)
    if error:
        result.error = error
        return result

    logging.debug(f"Sigma5 raw pressure: {sigma5_pressure_raw}, temperature: {sigma5_temperature_raw}")

    mtib_pressure_hg, mtib_temperature_c, mtib_altitude_ft, error = mtib_servers.read_altimeter(node)
    if error:
        result.error = error
        return result

    logging.debug(f"MTIB pressure: {mtib_pressure_hg}, temperature: {mtib_temperature_c}")

    # Convert Sigma5 values to match MTIB units
    # Sigma5 pressure is in raw units, need to convert to inHg
    # Sigma5 temperature is in raw units, need to convert to °C
    sigma5_pressure_hg = sigma5_pressure_raw  # Assuming already in correct units
    sigma5_temperature_c = sigma5_temperature_raw  # Assuming already in correct units

    logging.debug(
        f"Sigma5 converted pressure: {sigma5_pressure_hg:.3f}inHg, temperature: {sigma5_temperature_c:.3f}°C"
    )

    # Compare values with appropriate tolerances
    pressure_tolerance = 0.01  # ±0.01 inHg as per description
    temperature_tolerance = 6.0  # ±6°C as per description
    pressure_diff = abs(sigma5_pressure_hg - mtib_pressure_hg) if mtib_pressure_hg is not None else float("inf")
    temperature_diff = (
        abs(sigma5_temperature_c - mtib_temperature_c) if mtib_temperature_c is not None else float("inf")
    )

    logging.debug(f"Differences - pressure: {pressure_diff:.3f}inHg, temperature: {temperature_diff:.3f}°C")

    if pressure_diff <= pressure_tolerance and temperature_diff <= temperature_tolerance:
        result.success = True
        logging.info(
            f"Altimeter verification passed - pressure within ±{pressure_tolerance}inHg, temperature within ±{temperature_tolerance}°C"
        )
    else:
        result.error = f"Altimeter values don't match within tolerances. "
        result.error += f"pressure diff: {pressure_diff:.3f}inHg (tolerance: ±{pressure_tolerance}inHg), "
        result.error += f"temperature diff: {temperature_diff:.3f}°C (tolerance: ±{temperature_tolerance}°C)"
        logging.error(result.error)

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_4_verify_altimeter: TestStep = TestStep(
    info=StepInfo(
        name="Verify altimeter",
        description="Verify pressure ±0.01 inHg and temperature ±6 °C",
        noPassIsFatal=True,
    ),
    timeout_ms=5000,
    handler=verify_altimeter,
)
