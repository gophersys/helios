from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackHipsConfig
from ..util import check_required_fields


def send_jumptrack_hips_config(test_config: ValidationTestConfig, dut_id: int, hips_config: JumpTrackHipsConfig):
    """
    Apply the JumpTrack HIPS configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        hips_config (JumpTrackHipsConfig): The JumpTrack HIPS configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """

    # Ensure we use the correct configuration type
    if not isinstance(hips_config, JumpTrackHipsConfig):
        raise ValueError(f"JumpTrack HIPS configuration is missing or invalid. Received: {hips_config}")

    # Check required fields
    required_fields = {
        "report_period_seconds": hips_config.report_period_seconds,
        "force_checkin": hips_config.force_checkin,
        "scan_constantly": hips_config.scan_constantly,
        "mode": hips_config.mode,
        "group_code": hips_config.group_code,
        "source_user_id": hips_config.source_user_id,
    }
    check_required_fields(required_fields, "JumpTrack HIPS configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .._interface_v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_hips_config(dut_id, hips_config)


def get_jumptrack_hips_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackHipsConfig:
    """
    Get the latest JumpTrack HIPS configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackHipsConfig: The JumpTrack HIPS configuration.

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
    return APIInterface().get_jumptrack_hips_config(dut_id)
