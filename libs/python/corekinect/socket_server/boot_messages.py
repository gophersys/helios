from datetime import datetime
from typing import List

from corekinect.test.config import ValidationTestConfig
from corekinect.utils.log import Logger

from .data_types import JumpTrackBootMessage


def get_last_jumptrack_boot_message(
    test_config: ValidationTestConfig,
    dut_id: int,
) -> JumpTrackBootMessage | None:
    """
    Get the last boot message for a DUT

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackBootMessage: The last boot message for the DUT. None if no boot message is found.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported.

    """
    log = Logger.get_test_case_logger()

    log.debug(f"Getting last boot message for DUT {dut_id}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    return APIInterface().get_last_jumptrack_boot_message(dut_id)


def get_jumptrack_boot_messages_since_time(
    test_config: ValidationTestConfig, dut_id: int, start_time: datetime, end_time: datetime = None
) -> List[JumpTrackBootMessage] | None:
    """
    Get boot messages for a DUT since a given time

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        start_time (datetime): The start time to get boot messages from.
        end_time (datetime): The end time to get boot messages to. Defaults to None.

    Returns:
        List[JumpTrackBootMessage]: A list of boot messages for the DUT. None if no boot messages are found.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported.
    """
    log = Logger.get_test_case_logger()

    log.debug(f"Getting boot messages for DUT {dut_id} since {start_time}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    return APIInterface().get_jumptrack_boot_messages_since_time(dut_id, start_time, end_time)


def get_jumptrack_boot_messages_since_checkin_id(
    test_config: ValidationTestConfig, dut_id: int, checkin_id: int
) -> List[JumpTrackBootMessage] | None:
    """
    Get boot messages for a DUT since a given checkin ID

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        checkin_id (int): The checkin ID to get boot messages from.

    Returns:
        List[JumpTrackBootMessage]: A list of boot messages for the DUT. None if no boot messages are found.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported
    """
    log = Logger.get_test_case_logger()

    log.debug(f"Getting boot messages for DUT {dut_id} since checkin ID {checkin_id}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    return APIInterface().get_jumptrack_boot_messages_since_checkin_id(dut_id, checkin_id)
