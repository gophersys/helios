# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                           Config
# -------------------------------------------------
ALTIMETER_PRESSURE_TOLERANCE = 0.01
ALTIMETER_TEMPERATURE_TOLERANCE = 6.0


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_altimeter_data(config: Sigma5ManufacturingConfig, node: str, usr_data: None) -> TestStepResult:
    result = TestStepResult(success=False)

    sigma5_pressure_hg, sigma5_temperature_c, error = mtib_servers.sigma5_cmd_app_read_altimeter(node)
    if error:
        result.error = error
        return result

    mtib_pressure_hg, mtib_temperature_c, mtib_altitude_ft, error = mtib_servers.read_altimeter(node)
    if error:
        result.error = error
        return result

    logging.debug(f"Sigma5 altimeter data - pressure: {sigma5_pressure_hg}, temperature: {sigma5_temperature_c}")
    logging.debug(f"MTIB altimeter data - pressure: {mtib_pressure_hg}, temperature: {mtib_temperature_c}")

    pressure_diff = abs(sigma5_pressure_hg - mtib_pressure_hg)
    temperature_diff = abs(sigma5_temperature_c - mtib_temperature_c)

    logging.debug(f"Altimeter differences - pressure: {pressure_diff:.3f}inHg, temperature: {temperature_diff:.3f}°C")

    if pressure_diff <= ALTIMETER_PRESSURE_TOLERANCE and temperature_diff <= ALTIMETER_TEMPERATURE_TOLERANCE:
        result.success = True
    else:
        result.error = f"Altimeter values don't match within tolerances. "
        result.error += f"pressure diff: {pressure_diff:.3f}inHg (tolerance: ±{ALTIMETER_PRESSURE_TOLERANCE}inHg), "
        result.error += f"temperature diff: {temperature_diff:.3f}°C (tolerance: ±{ALTIMETER_TEMPERATURE_TOLERANCE}°C)"
        return result

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
    handler=verify_altimeter_data,
)
