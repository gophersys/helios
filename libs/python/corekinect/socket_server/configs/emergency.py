from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackEmergencyConfig
from ..util import check_required_fields


def send_jumptrack_emergency_config(
    test_config: ValidationTestConfig, dut_id: int, emergency_config: JumpTrackEmergencyConfig
):
    """
    Apply the emergency configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        emergency_config (JumpTrackEmergencyConfig): The emergency configuration to apply.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(emergency_config, JumpTrackEmergencyConfig):
        raise ValueError(f"JumpTrack Emergency configuration is missing or invalid. Received: {emergency_config}")

    # Check required fields
    required_fields = {
        "button_activation_time_seconds": emergency_config.button_activation_time_seconds,
        "button_timeout_seconds": emergency_config.button_timeout_seconds,
    }
    check_required_fields(required_fields, "Emergency configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_emergency_config(dut_id, emergency_config)


def get_jumptrack_emergency_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackEmergencyConfig:
    """
    Get the latest emergency configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackEmergencyConfig: The emergency configuration.

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
    return APIInterface().get_jumptrack_emergency_config(dut_id)
