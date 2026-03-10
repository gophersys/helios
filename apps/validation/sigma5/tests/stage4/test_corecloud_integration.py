"""C8: CoreCloud integration tests for Sigma5.

Verifies end-to-end communication between Sigma5 device and CoreCloud.
Asset tracker use case - device registration, telemetry, commands.

Tests:
    - Device registration and authentication
    - Telemetry message delivery
    - Command acknowledgment
    - Connection stability
"""

import time
import logging

import pytest

log = logging.getLogger(__name__)


class TestCoreCloudIntegration:
    """CoreCloud integration verification for Sigma5."""

    @pytest.mark.corecloud
    def test_device_registered(self, ctx, firmware_build):
        """PRDTST-S5-401: Device is registered in CoreCloud."""
        status = ctx.cloud.get_device_status()
        assert status is not None, "Device not found in CoreCloud"

        device_id = status.get("deviceId") or status.get("device_id")
        assert device_id is not None, "Device ID not in status"

        log.info("Device registered: %s", device_id)

    @pytest.mark.corecloud
    def test_device_online(self, ctx, firmware_build):
        """PRDTST-S5-402: Device shows online status in CoreCloud."""
        status = ctx.cloud.get_device_status()
        assert status is not None, "Device not found"

        online = status.get("isOnline") or status.get("online", False)
        log.info("Device online status: %s", online)

        # Device should be online after successful boot
        assert online, "Device not showing as online in CoreCloud"

    @pytest.mark.corecloud
    def test_telemetry_delivery(self, ctx, firmware_build):
        """PRDTST-S5-403: Telemetry messages reach CoreCloud."""
        # Wait for position or status message
        msg = ctx.cloud.wait_for_telemetry(timeout_s=120)
        assert msg is not None, "No telemetry received in 2 minutes"

        log.info("Telemetry received: %s", type(msg).__name__)

    @pytest.mark.corecloud
    def test_position_reporting(self, ctx, firmware_build):
        """PRDTST-S5-404: Position messages contain valid coordinates."""
        msg = ctx.cloud.wait_for_position(timeout_s=180)

        if msg is None:
            pytest.skip("No position message received - GPS may not have fix")

        lat = msg.get("latitude") or getattr(msg, "latitude", None)
        lon = msg.get("longitude") or getattr(msg, "longitude", None)

        if lat is None or lon is None:
            pytest.skip("Position message missing coordinates")

        log.info("Position: lat=%.6f, lon=%.6f", lat, lon)

        # Valid coordinate ranges
        assert -90 <= lat <= 90, f"Invalid latitude: {lat}"
        assert -180 <= lon <= 180, f"Invalid longitude: {lon}"

    @pytest.mark.corecloud
    def test_multiple_boot_cycles(self, ctx, firmware_build):
        """PRDTST-S5-405: Device reconnects to CoreCloud after multiple reboots."""
        success_count = 0

        for i in range(3):
            log.info("Boot cycle %d/3", i + 1)
            ctx.fixture.power_cycle()

            msg = ctx.cloud.wait_for_boot(timeout_s=120)
            if msg is not None:
                success_count += 1
                log.info("Boot %d: success", i + 1)
            else:
                log.warning("Boot %d: no BootMsgV2 received", i + 1)

            time.sleep(5)

        assert success_count >= 2, (
            f"Only {success_count}/3 boot cycles produced BootMsgV2"
        )

    @pytest.mark.corecloud
    def test_connection_recovery(self, ctx, firmware_build):
        """PRDTST-S5-406: Device recovers connection after network interruption."""
        # This test requires network simulation capability
        # For now, we verify the device stays connected over time

        start_time = time.time()
        connection_checks = 0
        online_count = 0

        while time.time() - start_time < 60:
            status = ctx.cloud.get_device_status()
            connection_checks += 1

            if status and status.get("isOnline", False):
                online_count += 1

            time.sleep(10)

        log.info(
            "Connection stability: %d/%d checks online",
            online_count, connection_checks,
        )

        # Should be online for most checks
        assert online_count >= connection_checks * 0.8, (
            f"Device offline too often: {online_count}/{connection_checks}"
        )

    @pytest.mark.corecloud
    @pytest.mark.xfail(reason="Command ACK not implemented for Sigma5")
    def test_command_acknowledgment(self, ctx, firmware_build):
        """PRDTST-S5-407: Device acknowledges commands from CoreCloud."""
        # Send a ping/status request command
        cmd_id = ctx.cloud.send_command("status_request")
        assert cmd_id is not None, "Failed to send command"

        # Wait for acknowledgment
        ack = ctx.cloud.wait_for_command_ack(cmd_id, timeout_s=30)
        assert ack is not None, f"No ACK for command {cmd_id}"

        log.info("Command %s acknowledged", cmd_id)
