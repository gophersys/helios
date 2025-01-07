from corekinect.test.config import ValidationTestConfig
from corekinect.utils.log import Logger

from .data_types import JumpTrackRebootMessage


def send_jumptrack_reboot_9160(test_config: ValidationTestConfig, dut_id: int, preserve_device_state=False) -> None:
    """
    Reboot the 9160 device with the given DUT ID.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        preserve_device_state (bool): Whether to preserve the device state after reboot.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported
    """
    log = Logger.get_test_case_logger()

    reboot_message = JumpTrackRebootMessage()
    reboot_message.reboot_9160 = True
    reboot_message.reboot_52840 = False
    reboot_message.preserve_device_state = preserve_device_state
    reboot_message.do_hard_reset = False
    reboot_message.cold_restart_gps = False

    log.debug(f"Rebooting DUT {dut_id} with message: {reboot_message}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    APIInterface().send_jumptrack_reboot_message(dut_id, reboot_message)


def send_jumptrack_reboot_52840(
    test_config: ValidationTestConfig,
    dut_id: int,
) -> None:
    """
    Reboot the 52840 device with the given DUT ID.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported
    """
    log = Logger.get_test_case_logger()

    reboot_message = JumpTrackRebootMessage()
    reboot_message.reboot_9160 = False
    reboot_message.reboot_52840 = True
    reboot_message.preserve_device_state = False
    reboot_message.do_hard_reset = False
    reboot_message.cold_restart_gps = False

    log.debug(f"Rebooting DUT {dut_id} with message: {reboot_message}")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    APIInterface().send_jumptrack_reboot_message(dut_id, reboot_message)


def send_jumptrack_reboot_9160_52840(
    test_config: ValidationTestConfig, dut_id: int, preserve_device_state=True
) -> None:
    """
    Reboot both the 9160 and 52840 devices with the given DUT ID.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        preserve_device_state (bool): Whether to preserve the device state after reboot.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported
    """
    log = Logger.get_test_case_logger()

    reboot_message = JumpTrackRebootMessage()
    reboot_message.reboot_9160 = True
    reboot_message.reboot_52840 = True
    reboot_message.preserve_device_state = preserve_device_state
    reboot_message.do_hard_reset = False
    reboot_message.cold_restart_gps = False

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    APIInterface().send_jumptrack_reboot_message(dut_id, reboot_message)


def send_jumptrack_hard_reset(test_config: ValidationTestConfig, dut_id: int) -> None:
    """
    Reboot the device with a hard reset.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported
    """
    log = Logger.get_test_case_logger()

    reboot_message = JumpTrackRebootMessage()
    reboot_message.reboot_9160 = False
    reboot_message.reboot_52840 = False
    reboot_message.preserve_device_state = False
    reboot_message.do_hard_reset = True
    reboot_message.cold_restart_gps = False

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    APIInterface().send_jumptrack_reboot_message(dut_id, reboot_message)


def send_jumptrack_cold_restart_gps(test_config: ValidationTestConfig, dut_id: int) -> None:
    """
    Restart the GPS module on the device.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported
    """
    log = Logger.get_test_case_logger()

    reboot_message = JumpTrackRebootMessage()
    reboot_message.reboot_9160 = False
    reboot_message.reboot_52840 = False
    reboot_message.preserve_device_state = False
    reboot_message.do_hard_reset = False
    reboot_message.cold_restart_gps = True

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from ._interface_v0p9 import APIInterface

        log.debug(f"Using API version 0.9")
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    APIInterface().send_jumptrack_reboot_message(dut_id, reboot_message)
