from datetime import datetime
from typing import List

from corekinect.test.config import ValidationTestConfig
from corekinect.utils.log import Logger

from .data_types import JumpTrackPositionMessage


def get_last_jumptrack_position_message(
    test_config: ValidationTestConfig,
    dut_id: int,
):
    log = Logger.get_test_case_logger()

    log.debug(f"Getting last position message for DUT {dut_id}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    APIInterface().get_last_jumptrack_position_message(dut_id)


def get_jumptrack_position_messages_since_time(
    test_config: ValidationTestConfig, dut_id: int, start_time: datetime, end_time: datetime = None
) -> List[JumpTrackPositionMessage] | None:
    log = Logger.get_test_case_logger()

    log.debug(f"Getting position messages for DUT {dut_id} since {start_time}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    return APIInterface().get_jumptrack_position_messages_since_time(dut_id, start_time, end_time)


def get_jumptrack_position_messages_since_checkin_id(
    test_config: ValidationTestConfig, dut_id: int, checkin_id: int
) -> List[JumpTrackPositionMessage] | None:
    log = Logger.get_test_case_logger()

    log.debug(f"Getting position messages for DUT {dut_id} since checkin ID {checkin_id}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    return APIInterface().get_jumptrack_position_messages_since_checkin_id(dut_id, checkin_id)
