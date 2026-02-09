# Standard includes
import base64
import random
import concurrent.futures
from typing import Dict, Optional

from tests.lib import *

# Shared includes
from ..shared.config import ThetaFixtureConfig

# Test includes
from .data import PostTestSharedData


# ---------------------------------------------------------------------------------
#                                                                          Helpers
# -------------------------------------------------------------------------------*/
def _run_flash_test_operations(
    test_data_b64: str, random_middle_address: str,
    start_addr: str, end_addr: str, test_string: str,
    write_func, read_func,
) -> Optional[str]:
    """Run flash test write/read/verify operations for a single processor."""
    # Write to start
    success, err = write_func(start_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to start: {err}"

    # Write to end
    success, err = write_func(end_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to end: {err}"

    # Write to middle
    success, err = write_func(random_middle_address, test_data_b64)
    if not success or err:
        return f"Failed to write to middle: {err}"

    # Verify start
    read_data, err = read_func(start_addr, len(test_string))
    if not read_data or err:
        return f"Failed to read from start: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at start. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from start: {e}"

    # Verify end
    read_data, err = read_func(end_addr, len(test_string))
    if not read_data or err:
        return f"Failed to read from end: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at end. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from end: {e}"

    # Verify middle
    read_data, err = read_func(random_middle_address, len(test_string))
    if not read_data or err:
        return f"Failed to read from middle: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at middle. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from middle: {e}"

    return None


def _verify_comms_flash(comms_cmds, config: ThetaFixtureConfig) -> Optional[str]:
    """Verify comms processor external flash functionality."""
    test_string = config.post_ext_flash_test_pattern
    test_data_b64 = base64.b64encode(test_string.encode("utf-8")).decode("utf-8")

    middle_start_int = int(config.post_ext_flash_middle_start, 16)
    middle_end_int = int(config.post_ext_flash_middle_end, 16)
    random_middle_address = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

    def write_func(addr, data):
        return comms_cmds.write_ext_flash(addr, data)

    def read_func(addr, length):
        return comms_cmds.read_ext_flash(addr, length)

    # Try without erasing first
    err = _run_flash_test_operations(
        test_data_b64, random_middle_address,
        config.post_ext_flash_start_addr, config.post_ext_flash_end_addr,
        test_string, write_func, read_func,
    )

    if not err:
        # Cleanup erase
        comms_cmds.erase_ext_flash()
        return None

    # Erase and retry
    logging.debug(f"[Comms] First attempt failed: {err}. Erasing and retrying...")
    erase_success, erase_err = comms_cmds.erase_ext_flash()
    if not erase_success or erase_err:
        return f"[Comms] Failed to erase flash for retry: {erase_err}"

    err = _run_flash_test_operations(
        test_data_b64, random_middle_address,
        config.post_ext_flash_start_addr, config.post_ext_flash_end_addr,
        test_string, write_func, read_func,
    )

    if err:
        return f"[Comms] Flash test failed after retry: {err}"

    # Cleanup erase
    comms_cmds.erase_ext_flash()
    return None


def _verify_app_flash(app_cmds, config: ThetaFixtureConfig) -> Optional[str]:
    """Verify app processor external flash functionality."""
    test_string = config.post_ext_flash_test_pattern
    test_data_b64 = base64.b64encode(test_string.encode("utf-8")).decode("utf-8")

    middle_start_int = int(config.post_ext_flash_middle_start, 16)
    middle_end_int = int(config.post_ext_flash_middle_end, 16)
    random_middle_address = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

    def write_func(addr, data):
        return app_cmds.write_ext_flash(addr, data)

    def read_func(addr, length):
        return app_cmds.read_ext_flash(addr, length)

    # Try without erasing first
    err = _run_flash_test_operations(
        test_data_b64, random_middle_address,
        config.post_ext_flash_start_addr, config.post_ext_flash_end_addr,
        test_string, write_func, read_func,
    )

    if not err:
        # Cleanup erase
        app_cmds.erase_ext_flash()
        return None

    # Erase and retry
    logging.debug(f"[App] First attempt failed: {err}. Erasing and retrying...")
    erase_success, erase_err = app_cmds.erase_ext_flash()
    if not erase_success or erase_err:
        return f"[App] Failed to erase flash for retry: {erase_err}"

    err = _run_flash_test_operations(
        test_data_b64, random_middle_address,
        config.post_ext_flash_start_addr, config.post_ext_flash_end_addr,
        test_string, write_func, read_func,
    )

    if err:
        return f"[App] Flash test failed after retry: {err}"

    # Cleanup erase
    app_cmds.erase_ext_flash()
    return None


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def post_step_8_handler(
    config: ThetaFixtureConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    """
    Step 8: Verify external flash on both processors in parallel.
    Write/read/verify pattern at start, end, and random middle address.
    """
    result: TestStepResult = TestStepResult(success=False)

    comms_cmds = usr_data[node].comms_cmds
    app_cmds = usr_data[node].app_cmds

    errors = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_verify_comms_flash, comms_cmds, config): "comms",
            executor.submit(_verify_app_flash, app_cmds, config): "app",
        }

        for future in concurrent.futures.as_completed(futures):
            processor = futures[future]
            try:
                err = future.result()
                if err:
                    errors.append(f"{processor}: {err}")
            except Exception as e:
                errors.append(f"{processor}: Exception - {str(e)}")

    if errors:
        result.reason = "; ".join(errors)
        return result

    logging.debug("POST Step 8 PASS: External flash verified on both processors")

    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
post_step_8_ext_flash: TestStep = TestStep(
    info=StepInfo(
        name="Verify external flash (comms + app)",
        description="Verifies external flash on both processors by writing/reading/verifying test patterns.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,
    handler=post_step_8_handler,
)
