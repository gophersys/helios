from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackGpsConfig
from ..util import check_required_fields


def send_jumptrack_gps_config(test_config: ValidationTestConfig, dut_id: int, gps_config: JumpTrackGpsConfig):
    """
    Apply the GPS aiding configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        gps_config (JumpTrackGpsConfig): The GPS aiding configuration

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(gps_config, JumpTrackGpsConfig):
        raise ValueError(f"JumpTrack GPS configuration is missing or invalid. Received: {gps_config}")

    # Check required fields
    required_fields = {
        "aiding_enabled": gps_config.aiding_enabled,
        "gnss_update_frequency": gps_config.gnss_update_frequency,
        "low_power_enabled": gps_config.low_power_enabled,
        "target_accuracy": gps_config.target_accuracy,
        "target_pdop": gps_config.target_pdop,
    }
    check_required_fields(required_fields, "JumpTrack GPS configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .._interface_v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_gps_config(dut_id, gps_config)


def get_jumptrack_gps_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackGpsConfig:
    """
    Get the latest GPS configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

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
    return APIInterface().get_jumptrack_gps_config(dut_id)
