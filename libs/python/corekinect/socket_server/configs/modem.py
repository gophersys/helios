from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackModemConfig
from ..util import check_required_fields


def send_jumptrack_modem_config(test_config: ValidationTestConfig, dut_id: int, modem_config: JumpTrackModemConfig):
    """
    Apply the JumpTrack Modem configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        modem_config (JumpTrackModemConfig): The JumpTrack Modem configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """

    # Ensure that the provided config is of the correct type
    if not isinstance(modem_config, JumpTrackModemConfig):
        raise ValueError(f"JumpTrack Modem configuration is missing or invalid. Received: {modem_config}")

    # Check required fields
    required_fields = {
        "short_backoff_time_seconds": modem_config.short_backoff_time_seconds,
        "normal_backoff_time_seconds": modem_config.normal_backoff_time_seconds,
        "long_backoff_time_minutes": modem_config.long_backoff_time_minutes,
        "registration_timeout_period_minutes": modem_config.registration_timeout_period_minutes,
        "socket_connection_timeout_period_minutes": modem_config.socket_connection_timeout_period_minutes,
        "connection_failure_threshold": modem_config.connection_failure_threshold,
        "socket_timeout_period_seconds": modem_config.socket_timeout_period_seconds,
    }
    check_required_fields(required_fields, "JumpTrack Modem configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_modem_config(dut_id, modem_config)


def get_jumptrack_modem_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackModemConfig:
    """
    Get the latest JumpTrack Modem configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackModemConfig: The JumpTrack Modem configuration.

    Raises:
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Get the configuration
    return APIInterface().get_jumptrack_modem_config(dut_id)
