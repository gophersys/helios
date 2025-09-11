# Standard includes
import json
import base64
import random
from dataclasses import asdict, dataclass

# Corekinect libraries
from src.tests.lib import *

# Shared includes
from src.tests.shared.config import Sigma5ManufacturingConfig
from src.tests.shared.rpcs import mtib_servers

# Post test includes
from src.tests.post.data import PostTestSharedData


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

    # Erase external flash before testing
    logging.debug("Erasing external flash before testing...")
    erase_success, erase_error = mtib_servers.sigma5_cmd_app_erase_ext_flash(node)
    if not erase_success or erase_error:
        result.error = f"Failed to erase external flash: {erase_error}"
        result.details = flash_info.marshall()
        return result

    # Convert test string to base64 for writing
    test_data_b64 = base64.b64encode(config.post_test_app_external_flash_test_string.encode("utf-8")).decode("utf-8")

    # Generate random address in middle third
    middle_start = int(config.post_test_app_external_flash_middle_start, 16)
    middle_end = int(config.post_test_app_external_flash_middle_end, 16)
    random_middle_address = f"0x{random.randint(middle_start, middle_end):06X}"

    # Populate flash info
    flash_info.test_pattern = config.post_test_app_external_flash_test_string
    flash_info.start_address = config.post_test_app_external_flash_start
    flash_info.end_address = config.post_test_app_external_flash_end
    flash_info.middle_address = random_middle_address
    flash_info.flash_size = config.post_test_app_external_flash_size

    logging.debug(f"Testing external flash with pattern: {config.post_test_app_external_flash_test_string}")
    logging.debug(
        f"Test addresses - Start: {config.post_test_app_external_flash_start}, End: {config.post_test_app_external_flash_end}, Middle: {random_middle_address}"
    )

    # Step 1: Write known pattern to start of external flash
    logging.debug("Writing test pattern to start of external flash...")
    write_success, write_error = mtib_servers.sigma5_cmd_app_write_ext_flash(
        node, config.post_test_app_external_flash_start, test_data_b64
    )
    if not write_success or write_error:
        result.error = f"Failed to write to start of flash: {write_error}"
        result.details = flash_info.marshall()
        return result

    # Step 2: Write known pattern to end of external flash
    logging.debug("Writing test pattern to end of external flash...")
    write_success, write_error = mtib_servers.sigma5_cmd_app_write_ext_flash(
        node, config.post_test_app_external_flash_end, test_data_b64
    )
    if not write_success or write_error:
        result.error = f"Failed to write to end of flash: {write_error}"
        result.details = flash_info.marshall()
        return result

    # Step 3: Write known pattern to random middle address
    logging.debug(f"Writing test pattern to middle address {random_middle_address}...")
    write_success, write_error = mtib_servers.sigma5_cmd_app_write_ext_flash(
        node, random_middle_address, test_data_b64
    )
    if not write_success or write_error:
        result.error = f"Failed to write to middle of flash: {write_error}"
        result.details = flash_info.marshall()
        return result

    # Step 4: Verify pattern at start
    logging.debug("Reading and verifying pattern at start...")
    read_data, read_error = mtib_servers.sigma5_cmd_app_read_ext_flash(
        node, config.post_test_app_external_flash_start, len(config.post_test_app_external_flash_test_string)
    )
    if not read_data or read_error:
        result.error = f"Failed to read from start of flash: {read_error}"
        result.details = flash_info.marshall()
        return result

    # Convert hex data back to string for comparison
    try:
        # Convert hex string to bytes, then decode
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != config.post_test_app_external_flash_test_string:
            result.error = f"Data mismatch at start. Expected: {config.post_test_app_external_flash_test_string}, Got: {read_string}"
            result.details = flash_info.marshall()
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from start: {e}"
        result.details = flash_info.marshall()
        return result

    # Step 5: Verify pattern at end
    logging.debug("Reading and verifying pattern at end...")
    read_data, read_error = mtib_servers.sigma5_cmd_app_read_ext_flash(
        node, config.post_test_app_external_flash_end, len(config.post_test_app_external_flash_test_string)
    )
    if not read_data or read_error:
        result.error = f"Failed to read from end of flash: {read_error}"
        result.details = flash_info.marshall()
        return result

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != config.post_test_app_external_flash_test_string:
            result.error = f"Data mismatch at end. Expected: {config.post_test_app_external_flash_test_string}, Got: {read_string}"
            result.details = flash_info.marshall()
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from end: {e}"
        result.details = flash_info.marshall()
        return result

    # Step 6: Verify pattern at middle
    logging.debug(f"Reading and verifying pattern at middle address {random_middle_address}...")
    read_data, read_error = mtib_servers.sigma5_cmd_app_read_ext_flash(
        node, random_middle_address, len(config.post_test_app_external_flash_test_string)
    )
    if not read_data or read_error:
        result.error = f"Failed to read from middle of flash: {read_error}"
        result.details = flash_info.marshall()
        return result

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != config.post_test_app_external_flash_test_string:
            result.error = f"Data mismatch at middle. Expected: {config.post_test_app_external_flash_test_string}, Got: {read_string}"
            result.details = flash_info.marshall()
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from middle: {e}"
        result.details = flash_info.marshall()
        return result

    # Step 7: Erase external flash
    logging.debug("Erasing external flash...")
    erase_success, erase_error = mtib_servers.sigma5_cmd_app_erase_ext_flash(node)
    if not erase_success or erase_error:
        result.error = f"Failed to erase external flash: {erase_error}"
        result.details = flash_info.marshall()
        return result

    # All tests passed
    result.success = True
    result.details = flash_info.marshall()

    return result


# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
app_post_step_6_verify_external_flash: TestStep = TestStep(
    info=StepInfo(
        name="Verify External Flash",
        description="Verify external flash is present and is writable.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,  # 2mins, erase can take a long time
    handler=verify_external_flash_functionality,
)
