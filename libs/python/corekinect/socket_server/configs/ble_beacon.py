from corekinect.test.config import ValidationTestConfig

from ..data_types import JumpTrackBleBeaconConfig
from ..util import check_required_fields


def send_jumptrack_ble_beacon_config(
    test_config: ValidationTestConfig, dut_id: int, ble_config: JumpTrackBleBeaconConfig
):
    """
    Apply the BLE beacon configuration to the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.
        ble_config (JumpTrackBleBeaconConfig): The BLE beacon configuration to apply.

    Raises:
        ValueError: If the configuration is not of the correct type or is missing required fields.
        NotImplementedError: If the Socket Server API version is not supported.
    """
    # Ensure that the provided config is of the correct type
    if not isinstance(ble_config, JumpTrackBleBeaconConfig):
        raise ValueError(f"JumpTrack BLE Beacon configuration is missing or invalid. Received: {ble_config}")

    # Check required fields
    required_fields = {
        "is_beacon_enabled": ble_config.is_beacon_enabled,
        "is_ble_beacon_scan_advertising_enabled": ble_config.is_ble_beacon_scan_advertising_enabled,
        "beacon_period_seconds": ble_config.beacon_period_seconds,
        "beacon_duration_milliseconds": ble_config.beacon_duration_milliseconds,
        "beacon_power": ble_config.beacon_power,
    }
    check_required_fields(required_fields, "JumpTrack BLE beacon configuration")

    # TODO: This version checking logic will change once ValidationTestConfig is fully implemented
    # Get the correct API interface based on the Socket Server version
    if "0.9" in test_config.socket_server_version:
        from .v0p9 import APIInterface
    else:
        raise NotImplementedError(f"Unsupported Socket Server API version: {test_config.socket_server_version}")

    # Apply the configuration
    APIInterface().send_jumptrack_ble_beacon_config(dut_id, ble_config)


def get_jumptrack_ble_beacon_config(test_config: ValidationTestConfig, dut_id: int) -> JumpTrackBleBeaconConfig:
    """
    Get the latest BLE beacon configuration for the DUT.

    Parameters:
        test_config (ValidationTestConfig): The test configuration.
        dut_id (int): ID of the device under test.

    Returns:
        JumpTrackBleBeaconConfig: The BLE beacon configuration.

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
    return APIInterface().get_jumptrack_ble_beacon_config(dut_id)
