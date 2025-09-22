# Standard includes
import base64
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

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
#                                                                        Helper Functions
# -------------------------------------------------
def _run_processor_flash_test(
    node: str, 
    config: Sigma5ManufacturingConfig, 
    processor_type: str
) -> Tuple[str, bool, Optional[str]]:
    """
    Run external flash test for a specific processor (app or comms).
    
    Args:
        node: Target node
        config: Test configuration
        processor_type: Either "app" or "comms"
        
    Returns:
        Tuple of (processor_type, success, error_message)
    """
    try:
        # Select config and functions based on processor type
        if processor_type == "app":
            test_string = config.post_test_app_external_flash_test_string
            start_addr = config.post_test_app_external_flash_start
            end_addr = config.post_test_app_external_flash_end
            middle_start = config.post_test_app_external_flash_middle_start
            middle_end = config.post_test_app_external_flash_middle_end
            erase_func = mtib_servers.sigma5_cmd_app_erase_ext_flash
            write_func = mtib_servers.sigma5_cmd_app_write_ext_flash
            read_func = mtib_servers.sigma5_cmd_app_read_ext_flash
        elif processor_type == "comms":
            test_string = config.post_test_comms_external_flash_test_string
            start_addr = config.post_test_comms_external_flash_start
            end_addr = config.post_test_comms_external_flash_end
            middle_start = config.post_test_comms_external_flash_middle_start
            middle_end = config.post_test_comms_external_flash_middle_end
            erase_func = mtib_servers.sigma5_cmd_comms_erase_ext_flash
            write_func = mtib_servers.sigma5_cmd_comms_write_ext_flash
            read_func = mtib_servers.sigma5_cmd_comms_read_ext_flash
        else:
            return processor_type, False, f"Invalid processor type: {processor_type}"

        # Convert test string to base64 for writing
        test_data_b64 = base64.b64encode(test_string.encode("utf-8")).decode("utf-8")

        # Generate random address in middle third
        middle_start_int = int(middle_start, 16)
        middle_end_int = int(middle_end, 16)
        random_middle_address = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

        logging.debug(f"Testing {processor_type} external flash with pattern: {test_string}")
        logging.debug(f"Test addresses - Start: {start_addr}, End: {end_addr}, Middle: {random_middle_address}")

        # Try the test first without erasing
        logging.debug(f"Attempting {processor_type} external flash test without initial erase...")
        test_result = _run_flash_test_operations(node, test_data_b64, random_middle_address, start_addr, end_addr, test_string, write_func, read_func)

        if test_result.success:
            logging.debug(f"{processor_type.capitalize()} first test attempt succeeded!")
            return processor_type, True, None
        else:
            logging.debug(f"{processor_type.capitalize()} first test attempt failed: {test_result.error}. Erasing flash and retrying...")

            # Erase external flash and retry
            erase_success, erase_error = erase_func(node)
            if not erase_success or erase_error:
                return processor_type, False, f"Failed to erase external flash for retry: {erase_error}"

            # Retry the test
            logging.debug(f"Retrying {processor_type} external flash test after erase...")
            test_result = _run_flash_test_operations(node, test_data_b64, random_middle_address, start_addr, end_addr, test_string, write_func, read_func)

            if test_result.success:
                logging.debug(f"{processor_type.capitalize()} second test attempt succeeded!")
                return processor_type, True, None
            else:
                return processor_type, False, f"External flash test failed after retry: {test_result.error}"

    except Exception as e:
        error_msg = f"Exception while testing {processor_type} external flash: {str(e)}"
        logging.error(error_msg)
        return processor_type, False, error_msg


def _run_flash_test_operations(
    node: str, 
    test_data_b64: str, 
    random_middle_address: str, 
    start_addr: str, 
    end_addr: str, 
    test_string: str,
    write_func,
    read_func
) -> TestStepResult:
    """Run the actual flash test operations without erase operations."""
    result = TestStepResult(success=False)

    # Step 1: Write known pattern to start of external flash
    logging.debug("Writing test pattern to start of external flash...")
    write_success, write_error = write_func(node, start_addr, test_data_b64)
    if not write_success or write_error:
        result.error = f"Failed to write to start of flash: {write_error}"
        return result

    # Step 2: Write known pattern to end of external flash
    logging.debug("Writing test pattern to end of external flash...")
    write_success, write_error = write_func(node, end_addr, test_data_b64)
    if not write_success or write_error:
        result.error = f"Failed to write to end of flash: {write_error}"
        return result

    # Step 3: Write known pattern to random middle address
    logging.debug(f"Writing test pattern to middle address {random_middle_address}...")
    write_success, write_error = write_func(node, random_middle_address, test_data_b64)
    if not write_success or write_error:
        result.error = f"Failed to write to middle of flash: {write_error}"
        return result

    # Step 4: Verify pattern at start
    logging.debug("Reading and verifying pattern at start...")
    read_data, read_error = read_func(node, start_addr, len(test_string))
    if not read_data or read_error:
        result.error = f"Failed to read from start of flash: {read_error}"
        return result

    # Convert hex data back to string for comparison
    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            result.error = f"Data mismatch at start. Expected: {test_string}, Got: {read_string}"
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from start: {e}"
        return result

    # Step 5: Verify pattern at end
    logging.debug("Reading and verifying pattern at end...")
    read_data, read_error = read_func(node, end_addr, len(test_string))
    if not read_data or read_error:
        result.error = f"Failed to read from end of flash: {read_error}"
        return result

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            result.error = f"Data mismatch at end. Expected: {test_string}, Got: {read_string}"
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from end: {e}"
        return result

    # Step 6: Verify pattern at middle
    logging.debug(f"Reading and verifying pattern at middle address {random_middle_address}...")
    read_data, read_error = read_func(node, random_middle_address, len(test_string))
    if not read_data or read_error:
        result.error = f"Failed to read from middle of flash: {read_error}"
        return result

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            result.error = f"Data mismatch at middle. Expected: {test_string}, Got: {read_string}"
            return result
    except Exception as e:
        result.error = f"Failed to parse read data from middle: {e}"
        return result

    # All tests passed
    result.success = True
    return result


# -------------------------------------------------
#                                           Handler
# -------------------------------------------------
def verify_external_flash_functionality(
    config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, PostTestSharedData]
) -> TestStepResult:
    result = TestStepResult(success=False)
    flash_info = ExternalFlashInfo()

    # Populate flash info with comms config (primary config)
    flash_info.test_pattern = config.post_test_comms_external_flash_test_string
    flash_info.start_address = config.post_test_comms_external_flash_start
    flash_info.end_address = config.post_test_comms_external_flash_end
    flash_info.flash_size = config.post_test_comms_external_flash_size

    # Execute external flash tests for both processors in parallel
    logging.info(f"Starting parallel external flash testing for both app and comms processors on {node}")
    processor_results = {}
    errors = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both processor flash tests
        future_to_processor = {
            executor.submit(_run_processor_flash_test, node, config, "app"): "app",
            executor.submit(_run_processor_flash_test, node, config, "comms"): "comms"
        }

        # Collect results as they complete
        for future in as_completed(future_to_processor):
            processor_type = future_to_processor[future]
            try:
                proc_type_result, success, error = future.result()
                processor_results[proc_type_result] = (success, error)
                
                if error:
                    errors.append(f"{proc_type_result.capitalize()} processor: {error}")
                else:
                    logging.info(f"{proc_type_result.capitalize()} processor external flash test completed successfully")
                    
            except Exception as e:
                error_msg = f"Exception in {processor_type} processor flash test: {str(e)}"
                logging.error(error_msg)
                errors.append(error_msg)
                processor_results[processor_type] = (False, error_msg)

    # Check results and set final status
    if errors:
        result.error = "External flash testing failed:\n" + "\n".join(errors)
        logging.error(f"External flash testing failed with {len(errors)} errors")
    else:
        result.success = True
        logging.info("All external flash tests completed successfully")

    # Always perform cleanup erase for both processors
    logging.debug("Performing cleanup erase of external flash for both processors...")
    cleanup_errors = []
    
    # Cleanup app processor flash
    try:
        erase_success, erase_error = mtib_servers.sigma5_cmd_app_erase_ext_flash(node)
        if not erase_success or erase_error:
            cleanup_errors.append(f"App processor cleanup erase failed: {erase_error}")
    except Exception as e:
        cleanup_errors.append(f"App processor cleanup erase exception: {str(e)}")
    
    # Cleanup comms processor flash
    try:
        erase_success, erase_error = mtib_servers.sigma5_cmd_comms_erase_ext_flash(node)
        if not erase_success or erase_error:
            cleanup_errors.append(f"Comms processor cleanup erase failed: {erase_error}")
    except Exception as e:
        cleanup_errors.append(f"Comms processor cleanup erase exception: {str(e)}")
    
    if cleanup_errors:
        # Don't fail the test for cleanup erase failures, just log them
        logging.warning(f"Cleanup erase issues: {'; '.join(cleanup_errors)}")

    result.details = flash_info.marshall()
    return result




# ---------------------------------------------------------------------------------
#                                                                              Step
# -------------------------------------------------------------------------------*/
comms_post_step_4_verify_external_flash: TestStep = TestStep(
    info=StepInfo(
        name="Verify External Flash (App & Comms)",
        description="Verify external flash is present and writable for both app and comms processors in parallel.",
        noPassIsFatal=True,
    ),
    timeout_ms=120000,  # 2mins, erase can take a long time
    handler=verify_external_flash_functionality,
)
