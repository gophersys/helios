# Standard includes
import json
import base64
import random
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Post test includes
from src.tests.post.data import PostTestSharedData

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers


# -------------------------------------------------
#                                              Data
# -------------------------------------------------
@dataclass
class ExternalFlashInfo:
    test_pattern: str = None
    start_address: str = None
    end_address: str = None
    middle_address: str = None
    flash_size: int = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return ExternalFlashInfo(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_external_flash_functionality(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    flash_info = ExternalFlashInfo()

    # Convert test string to base64 for writing
    test_data_b64 = base64.b64encode(config.post_test_comms_external_flash_test_string.encode("utf-8")).decode("utf-8")

    # Generate random address in middle third
    middle_start = int(config.post_test_comms_external_flash_middle_start, 16)
    middle_end = int(config.post_test_comms_external_flash_middle_end, 16)
    random_middle_address = f"0x{random.randint(middle_start, middle_end):06X}"

    # Populate flash info
    flash_info.test_pattern = config.post_test_comms_external_flash_test_string
    flash_info.start_address = config.post_test_comms_external_flash_start
    flash_info.end_address = config.post_test_comms_external_flash_end
    flash_info.middle_address = random_middle_address
    flash_info.flash_size = config.post_test_comms_external_flash_size

    logging.debug(f"Testing external flash with pattern: {config.post_test_comms_external_flash_test_string}")
    logging.debug(
        f"Test addresses - Start: {config.post_test_comms_external_flash_start}, End: {config.post_test_comms_external_flash_end}, Middle: {random_middle_address}"
    )

    # Try the test first without erasing
    logging.debug("Attempting external flash test without initial erase...")
    test_result = _run_flash_test(node, config, test_data_b64, random_middle_address)

    if test_result.success:
        logging.debug("First test attempt succeeded!")
        result.success = True
        result.details = flash_info.marshall()
    else:
        logging.debug(f"First test attempt failed: {test_result.error}. Erasing flash and retrying...")

        # Erase external flash and retry
        erase_success, erase_error = mtib_servers.sigma5_cmd_comms_erase_ext_flash(node)
        if not erase_success or erase_error:
            result.error = f"Failed to erase external flash for retry: {erase_error}"
            result.details = flash_info.marshall()
            return result

        # Retry the test
        logging.debug("Retrying external flash test after erase...")
        test_result = _run_flash_test(node, config, test_data_b64, random_middle_address)

        if test_result.success:
            logging.debug("Second test attempt succeeded!")
            result.success = True
            result.details = flash_info.marshall()
        else:
            logging.debug(f"Second test attempt also failed: {test_result.error}")
            result.error = f"External flash test failed after retry: {test_result.error}"
            result.details = flash_info.marshall()

    # Always perform cleanup erase at the end
    logging.debug("Performing cleanup erase of external flash...")
    erase_success, erase_error = mtib_servers.sigma5_cmd_comms_erase_ext_flash(node)
    if not erase_success or erase_error:
        # Don't fail the test for cleanup erase failure, just log it
        logging.warning(f"Failed to perform cleanup erase: {erase_error}")

    return result


def _run_flash_test(
    node: str, config: Sigma5ManufacturingConfig, test_data_b64: str, random_middle_address: str
) -> TestStepResult:
    """Run the actual flash test operations without erase operations."""
    result = TestStepResult(success=False)

    # Step 1: Write known pattern to start of external flash
    logging.debug("Writing test pattern to start of external flash...")
    write_success, write_error = mtib_servers.sigma5_cmd_comms_write_ext_flash(
        node, config.post_test_comms_external_flash_start, test_data_b64
    )
    if not write_success or write_error:
        result.error = f"Failed to write to start of flash: {write_error}"
        return result

    # Step 2: Write known pattern to end of external flash
    logging.debug("Writing test pattern to end of external flash...")
    write_success, write_error = mtib_servers.sigma5_cmd_comms_write_ext_flash(
        node, config.post_test_comms_external_flash_end, test_data_b64
    )
    if not write_success or write_error:
        result.error = f"Failed to write to end of flash: {write_error}"
        return result

    # Step 3: Write known pattern to random middle address
    logging.debug(f"Writing test pattern to middle address {random_middle_address}...")
    write_success, write_error = mtib_servers.sigma5_cmd_comms_write_ext_flash(
        node, random_middle_address, test_data_b64
    )
    if not write_success or write_error:
        result.error = f"Failed to write to middle of flash: {write_error}"
        return result

    # Step 4: Verify pattern at start
    logging.debug("Reading and verifying pattern at start...")
    read_data, read_error = mtib_servers.sigma5_cmd_comms_read_ext_flash(
        node, config.post_test_comms_external_flash_start, len(config.post_test_comms_external_flash_test_string)
    )
    if not read_data or read_error:
        result.error = f"Failed to read from start of flash: {read_error}"
        return result

    # Convert hex data back to string for comparison
    try:
        # Convert hex string to bytes, then decode
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != config.post_test_comms_external_flash_test_string:
            result.error = f"Data mismatch at start. Expected: {config.post_test_comms_external_flash_test_string}, Got: {read_string}"
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from start: {e}"
        return result

    # Step 5: Verify pattern at end
    logging.debug("Reading and verifying pattern at end...")
    read_data, read_error = mtib_servers.sigma5_cmd_comms_read_ext_flash(
        node, config.post_test_comms_external_flash_end, len(config.post_test_comms_external_flash_test_string)
    )
    if not read_data or read_error:
        result.error = f"Failed to read from end of flash: {read_error}"
        return result

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != config.post_test_comms_external_flash_test_string:
            result.error = f"Data mismatch at end. Expected: {config.post_test_comms_external_flash_test_string}, Got: {read_string}"
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from end: {e}"
        return result

    # Step 6: Verify pattern at middle
    logging.debug(f"Reading and verifying pattern at middle address {random_middle_address}...")
    read_data, read_error = mtib_servers.sigma5_cmd_comms_read_ext_flash(
        node, random_middle_address, len(config.post_test_comms_external_flash_test_string)
    )
    if not read_data or read_error:
        result.error = f"Failed to read from middle of flash: {read_error}"
        return result

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != config.post_test_comms_external_flash_test_string:
            result.error = f"Data mismatch at middle. Expected: {config.post_test_comms_external_flash_test_string}, Got: {read_string}"
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from middle: {e}"
        return result

    # All tests passed
    result.success = True
    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_4_verify_external_flash: TestStep = TestStep(
    info=StepInfo(
        name="Verify External Flash",
        description="Verify external flash is present and is writable.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,  # 2mins, erase can take a long time
    handler=verify_external_flash_functionality,
)
