from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackSimConfig
from ..util import check_required_fields


def send_jumptrack_sim_config(test_config: ValidationTestConfig, dut_id: int, sim_config: JumpTrackSimConfig):
    """
    Apply the JumpTrack SIM configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        sim_config (JumpTrackSimConfig): The JumpTrack SIM configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(sim_config, JumpTrackSimConfig):
        raise ValueError(f"JumpTrack SIM configuration is missing or invalid. Received: {sim_config}")

    # Check required fields
    required_fields = {
        "default_sim_select": sim_config.default_sim_select,
        "prevent_sim_swapping": sim_config.prevent_sim_swapping,
    }
    check_required_fields(required_fields, "JumpTrack SIM configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_sim_config(dut_id, sim_config)


def get_jumptrack_sim_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackSimConfig:
    """
    Get the latest JumpTrack SIM configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackSimConfig: The JumpTrack SIM configuration.

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
    return APIInterface().get_jumptrack_sim_config(dut_id)
