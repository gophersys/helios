from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackFallConfig
from ..util import check_required_fields


def send_jumptrack_fall_config(test_config: ValidationTestConfig, dut_id: int, fall_config: JumpTrackFallConfig):
    """
    Apply the fall configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        fall_config (JumpTrackFallConfig): The fall configuration to apply.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(fall_config, JumpTrackFallConfig):
        raise ValueError(f"JumpTrack Fall configuration is missing or invalid. Received: {fall_config}")

    # Check required fields
    required_fields = {
        "jump_mode_enabled": fall_config.jump_mode_enabled,
        "jump_state_gps_report_period_seconds": fall_config.jump_state_gps_report_period_seconds,
        "jump_state_state_duration_minutes": fall_config.jump_state_state_duration_minutes,
        "free_fall_acceleration_threshold": fall_config.free_fall_acceleration_threshold,
        "free_fall_acceleration_duration_centiseconds": fall_config.free_fall_acceleration_duration_centiseconds,
        "altitude_change_free_fall_trigger_ft_per_minute": fall_config.altitude_change_free_fall_trigger_ft_per_minute,
        "altitude_change_jump_trigger_ft_per_minute": fall_config.altitude_change_jump_trigger_ft_per_minute,
        "stable_altitude_num_samples": fall_config.stable_altitude_num_samples,
        "stable_altitude_threshold_ft": fall_config.stable_altitude_threshold_ft,
    }
    check_required_fields(required_fields, "JumpTrack Fall configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_fall_config(dut_id, fall_config)


def get_jumptrack_fall_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackFallConfig:
    """
    Get the latest fall configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackFallConfig: The fall configuration.

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
    return APIInterface().get_jumptrack_fall_config(dut_id)
