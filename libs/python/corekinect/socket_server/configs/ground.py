from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackGndConfigV1, JumpTrackGndConfigV2
from ..util import check_required_fields


def send_jumptrack_ground_config_v1(
    test_config: ValidationTestConfig, dut_id: int, ground_config: JumpTrackGndConfigV1
):
    """
    Apply the JumpTrack Ground configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        ground_config (JumpTrackGndConfigV1 | JumpTrackGndConfigV2): The JumpTrack Ground configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """

    # Ensure we use the correct configuration type
    if not isinstance(ground_config, JumpTrackGndConfigV1):
        raise ValueError(f"JumpTrack Ground V1 configuration is missing or invalid. Received: {ground_config}")

    # Check required fields
    required_fields = {
        "gps_heartbeat_period_minutes": ground_config.gps_heartbeat_period_minutes,
        "continuous_motion_period_seconds": ground_config.continuous_motion_period_seconds,
        "stop_motion_timeout_seconds": ground_config.stop_motion_timeout_seconds,
        "heartbeat_acquisition_timeout_seconds": ground_config.heartbeat_acquisition_timeout_seconds,
        "motion_acquisition_timeout_seconds": ground_config.motion_acquisition_timeout_seconds,
        "motion_acceleration_threshold": ground_config.motion_acceleration_threshold,
        "motion_acceleration_duration": ground_config.motion_acceleration_duration,
        "start_motion_window_start": ground_config.start_motion_window_start,
        "start_motion_window_end": ground_config.start_motion_window_end,
    }
    check_required_fields(required_fields, "JumpTrack Ground V1 configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_ground_config_v1(dut_id, ground_config)


def get_jumptrack_ground_config_v1(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackGndConfigV1:
    """
    Get the latest JumpTrack Ground configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackGndConfigV1: The JumpTrack Ground configuration.

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
    return APIInterface().get_jumptrack_ground_config_v1(dut_id)


def send_jumptrack_ground_config_v2(
    test_config: ValidationTestConfig, dut_id: int, ground_config: JumpTrackGndConfigV2
):
    """
    Apply the JumpTrack Ground configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        ground_config (JumpTrackGndConfigV1 | JumpTrackGndConfigV2): The JumpTrack Ground configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """

    # Ensure we use the correct configuration type
    if not isinstance(ground_config, JumpTrackGndConfigV2):
        raise ValueError(f"JumpTrack Ground V2 configuration is missing or invalid. Received: {ground_config}")

    # Check required fields
    required_fields = {
        "gps_heartbeat_period_minutes": ground_config.gps_heartbeat_period_minutes,
        "continuous_motion_period_seconds": ground_config.continuous_motion_period_seconds,
        "stop_motion_timeout_seconds": ground_config.stop_motion_timeout_seconds,
        "heartbeat_acquisition_timeout_seconds": ground_config.heartbeat_acquisition_timeout_seconds,
        "motion_acquisition_timeout_seconds": ground_config.motion_acquisition_timeout_seconds,
        "motion_acceleration_threshold": ground_config.motion_acceleration_threshold,
        "motion_acceleration_duration": ground_config.motion_acceleration_duration,
        "start_motion_window_start_seconds": ground_config.start_motion_window_start_seconds,
        "start_motion_window_end_seconds": ground_config.start_motion_window_end_seconds,
        "motion_acquisition_on_time_seconds": ground_config.motion_acquisition_on_time_seconds,
        "motion_initial_acquisition_on_time_seconds": ground_config.motion_initial_acquisition_on_time_seconds,
    }
    check_required_fields(required_fields, "JumpTrack Ground V2 configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_ground_config_v2(dut_id, ground_config)


def get_jumptrack_ground_config_v2(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackGndConfigV2:
    """
    Get the latest JumpTrack Ground configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackGndConfigV2: The JumpTrack Ground configuration.

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
    return APIInterface().get_jumptrack_ground_config_v2(dut_id)
