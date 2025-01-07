from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackLoRaConfig
from ..util import check_required_fields


def send_jumptrack_lora_config(test_config: ValidationTestConfig, dut_id: int, lora_config: JumpTrackLoRaConfig):
    """
    Apply the JumpTrack LoRa configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        lora_config (JumpTrackLoRaConfig): The JumpTrack LoRa configuration.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(lora_config, JumpTrackLoRaConfig):
        raise ValueError(f"JumpTrack LoRa configuration is missing or invalid. Received: {lora_config}")

    # Check required fields
    required_fields = {
        "lora_enabled": lora_config.lora_enabled,
    }
    check_required_fields(required_fields, "JumpTrack LoRa configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_lora_config(dut_id, lora_config)


def get_jumptrack_lora_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackLoRaConfig:
    """
    Get the latest JumpTrack LoRa configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackLoRaConfig: The JumpTrack LoRa configuration.

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
    return APIInterface().get_jumptrack_lora_config(dut_id)
