# Standard includes
import logging
from typing import Dict

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import FwFlashTestSharedData


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def fw_flash_test_step_1_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, FwFlashTestSharedData]
) -> TestStepResult:
    """
    Flash all firmware serially:
    1. Flash nRF52840 app firmware via debug session
    2. Flash nRF9151 modem firmware via debug session
    """

    result: TestStepResult = TestStepResult(success=False)
    client = usr_data[node].client

    # Log power status before flashing
    err, power_status = client.power_status(channel=0)
    if not err and power_status:
        logging.debug(
            f"Node {node} power before flashing: {power_status.voltage_v:.2f}V, {power_status.current_ma:.1f}mA"
        )

    time.sleep(5)

    # Flash nRF52840 app firmware (retry once on failure)
    err, session = client.debug_connect(target_id="nrf52840", probe_id="")
    if err:
        result.error = f"nRF52840 debug connect failed: {err}"
        return result

    err, flash_result = client.flash_program(
        session_id=session.session_id,
        filename=config.fw_flash_nrf52840_app_fw_name,
        erase_before=True,
        verify_after=True,
        reset_after=True,
    )
    client.debug_disconnect(session.session_id)

    if err:
        logging.warning(f"nRF52840 flash failed on first attempt: {err}, retrying...")
        time.sleep(2)

        err, session = client.debug_connect(target_id="nrf52840", probe_id="")
        if err:
            result.error = f"nRF52840 debug connect failed on retry: {err}"
            return result

        err, flash_result = client.flash_program(
            session_id=session.session_id,
            filename=config.fw_flash_nrf52840_app_fw_name,
            erase_before=True,
            verify_after=True,
            reset_after=True,
        )
        client.debug_disconnect(session.session_id)

        if err:
            result.error = f"nRF52840 flash failed after retry: {err}"
            return result

    logging.debug(
        f"nRF52840 app firmware {config.fw_flash_nrf52840_app_fw_name} flashed in {flash_result.time_ms}ms"
    )

    # Flash modem firmware
    err, session = client.debug_connect(target_id="nrf9151", probe_id="")
    if err:
        result.error = f"nRF9151 modem debug connect failed: {err}"
        return result

    err, flash_result = client.flash_program(
        session_id=session.session_id,
        filename=config.fw_flash_nrf9151_modem_fw_name,
        erase_before=True,
        verify_after=True,
        reset_after=True,
    )
    client.debug_disconnect(session.session_id)

    if err:
        result.error = f"Modem flash failed: {err}"
        return result

    logging.debug(
        f"Modem firmware {config.fw_flash_nrf9151_modem_fw_name} flashed in {flash_result.time_ms}ms"
    )

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
fw_flash_test_step_1: TestStep = TestStep(
    info=StepInfo(
        name="Flash modem firmware and nRF52840 app",
        description="Flashes the nRF9151 modem firmware and nRF52840 app firmware serially.",
        noPassIsFatal=True,
    ),
    timeout_ms=300000,  # 5 minutes for both firmwares
    handler=fw_flash_test_step_1_handler,
)
