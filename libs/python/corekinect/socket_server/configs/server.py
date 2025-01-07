from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackServerConfig
from ..util import check_required_fields


def send_jumptrack_server_config(test_config: ValidationTestConfig, dut_id: int, server_config: JumpTrackServerConfig):
    """
    Apply the JumpTrack server configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        server_config (JumpTrackServerConfig): The JumpTrack server configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(server_config, JumpTrackServerConfig):
        raise ValueError(f"JumpTrack Server configuration is missing or invalid. Received: {server_config}")

    # Check required fields
    required_fields = {
        "server_type": server_config.server_type,
        "production_server": server_config.production_server,
        "write": server_config.write,
        "port": server_config.port,
        "url": server_config.url,
    }
    check_required_fields(required_fields, "JumpTrack Server configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_server_config(dut_id, server_config)


def get_jumptrack_server_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackServerConfig:
    """
    Get the latest JumpTrack server configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackServerConfig: The JumpTrack server configuration.

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
    return APIInterface().get_jumptrack_server_config(dut_id)
