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
#                                           Handler
# -------------------------------------------------
def verify_altimeter_data(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
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

    if (
        pressure_diff <= config.post_test_app_altimeter_pressure_error_margin
        and temperature_diff <= config.post_test_app_altimeter_temperature_error_margin
    ):
        result.success = True
        logging.debug(
            f"Altimeter verification passed - all values within ±{config.post_test_app_altimeter_pressure_error_margin}inHg and ±{config.post_test_app_altimeter_temperature_error_margin}°C tolerance"
        )
    else:
        result.error = f"Altimeter values don't match within tolerances. "
        result.error += f"pressure diff: {pressure_diff:.3f}inHg (tolerance: ±{config.post_test_app_altimeter_pressure_error_margin}inHg), "
        result.error += f"temperature diff: {temperature_diff:.3f}°C (tolerance: ±{config.post_test_app_altimeter_temperature_error_margin}°C)"
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
