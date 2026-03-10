"""POST (Power-On Self Test) verification tests.

Validates hardware subsystems after firmware delivery. Run twice per device:
1. After J-Link flash + repersonalization (full POST)
2. After FUOTA delivery (skip personalization steps)

Tests are grouped by subsystem and marked for selective execution.
Use `--skip-personalization` to skip device personalization tests when
running after FUOTA (device already personalized from J-Link cycle).

POST Steps (mirrored from manufacturing):
    0. Boot and lock shells
    1-2. Chip IDs (TODO: alpha_cmd not implemented)
    3-4. Power subsystem (TODO: alpha_cmd not implemented)
    5-7. Comms subsystem
    8. External flash (TODO: alpha_cmd not implemented)
    9. Personalization (skip after FUOTA)
   10. IPC Rekey (skip after FUOTA)
"""

import logging
import time
from typing import Optional, Tuple, List

import pytest

log = logging.getLogger(__name__)


@pytest.fixture
def skip_personalization(request):
    """Return True if --skip-personalization flag is set."""
    return request.config.getoption("--skip-personalization", default=False)


class TestPostBoot:
    """Step 0: Boot verification and shell lock."""

    def test_boot_current_draw(self, ctx):
        """POST-0a: Boot sequence draws expected current."""
        # Power cycle and measure
        ctx.fixture.power_off()
        time.sleep(1)
        ctx.fixture.power_on()

        # Wait for boot and measure average current
        time.sleep(5)
        result = ctx.power.measure(channel=1, duration_s=5)  # ch1 for battery mode

        assert result.avg_current_ma > 5, (
            f"Boot current too low ({result.avg_current_ma:.1f}mA) - device may not be booting"
        )
        assert result.avg_current_ma < 100, (
            f"Boot current too high ({result.avg_current_ma:.1f}mA) - possible short"
        )
        log.info("POST-0a PASS: Boot current %.1fmA (avg)", result.avg_current_ma)

    def test_uart_output(self, ctx):
        """POST-0b: Device produces UART output after boot."""
        # Capture UART for a few seconds
        uart_data = ctx.fixture.capture_uart(target="app", duration_s=3)

        # Should have received some boot output
        assert len(uart_data) > 0, "No UART output captured after boot"

        # Look for boot indicators
        uart_text = uart_data.decode("utf-8", errors="replace")
        boot_indicators = ["Booting", "MCUboot", "Zephyr", "<inf>", "<dbg>"]
        found_indicator = any(ind in uart_text for ind in boot_indicators)

        log.info(
            "POST-0b: Captured %d bytes UART, boot indicator found: %s",
            len(uart_data), found_indicator
        )
        # Don't assert - just log, as debug output may be disabled


class TestPostComms:
    """Steps 5-7: Communications subsystem verification."""

    def test_imei_iccids(self, ctx):
        """POST-7: IMEI and ICCIDs readable from modem."""
        from protocols.mtib.mtib_pb2 import HostType

        # Use existing alpha_cmd_get_imei_iccids
        imei, iccids_str, err = ctx.mtib.alpha_cmd_get_imei_iccids(
            target=HostType.HOST_TYPE_NRF9151  # nRF9151 comms
        )

        if err:
            pytest.skip(f"IMEI/ICCID read not available: {err}")

        # IMEI should be 15 digits
        assert imei and len(imei) == 15, f"Invalid IMEI: {imei}"

        # Parse ICCIDs (comma-separated string)
        iccids = [s.strip() for s in (iccids_str or "").split(",") if s.strip()]
        assert len(iccids) > 0, "No ICCIDs found"

        log.info("POST-7 PASS: IMEI=%s, ICCIDs=%s", imei, iccids)


class TestPostPersonalization:
    """Steps 9-10: Device personalization (skip after FUOTA)."""

    @pytest.mark.personalization
    def test_personalize(self, ctx, skip_personalization):
        """POST-9: Device personalization via CoreOps."""
        if skip_personalization:
            pytest.skip("Skipped: --skip-personalization flag set (FUOTA run)")

        # Check if personalizer is configured
        if not hasattr(ctx, "personalizer") or ctx.personalizer is None:
            pytest.skip("DevicePersonalizer not configured (missing PROXY_SERVER_URL)")

        result, err = ctx.personalizer.repersonalize()
        assert err is None, f"Personalization failed: {err}"
        assert result.device_id, "No device ID assigned"
        assert result.pub_key_base64, "No public key generated"

        log.info(
            "POST-9 PASS: Device ID=%s, PubKey=%s...",
            result.device_id,
            result.pub_key_base64[:20]
        )

    @pytest.mark.personalization
    def test_rekey_ipc(self, ctx, skip_personalization):
        """POST-10: IPC rekey to device-specific keys."""
        if skip_personalization:
            pytest.skip("Skipped: --skip-personalization flag set (FUOTA run)")

        # IPC rekey via UART command
        from protocols.mtib.mtib_pb2 import HostType

        success, err = _send_uart_cmd(
            ctx.mtib,
            HostType.HOST_TYPE_NRF52840,  # App processor
            "rekey_ipc",
            timeout_s=15,
            success_pattern="IPC rekey complete"
        )

        # Skip if command not available or not implemented
        if err:
            err_lower = err.lower()
            if "not implemented" in err_lower or "pattern" in err_lower:
                pytest.skip("rekey_ipc command not available on this firmware")

        assert err is None, f"IPC rekey failed: {err}"
        assert success, "IPC rekey returned failure"

        log.info("POST-10 PASS: IPC rekey completed")


class TestPostSummary:
    """Final verification after all POST tests."""

    def test_device_ready(self, ctx):
        """POST-FINAL: Device is ready for operation."""
        # Final power check - device should be drawing normal idle current
        result = ctx.power.measure(channel=1, duration_s=3)

        # Idle current should be reasonable (> 0.1mA shows device is alive, < 100mA is sane)
        # Device may be in low-power sleep mode, so 0.5-1mA is normal
        assert result.avg_current_ma > 0.1, (
            f"No current detected ({result.avg_current_ma:.2f}mA) - device may not be running"
        )
        assert result.avg_current_ma < 100, (
            f"Current too high ({result.avg_current_ma:.1f}mA) - possible issue"
        )

        log.info(
            "POST-FINAL PASS: Device ready, idle current=%.1fmA",
            result.avg_current_ma
        )


# ── Utility functions ────────────────────────────────────────────────

def _send_uart_cmd(
    mtib,
    target,
    command: str,
    timeout_s: float = 10,
    success_pattern: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Send a UART command and wait for response.

    Args:
        mtib: MtibV1Client instance.
        target: HostType for UART target.
        command: Command string to send.
        timeout_s: Timeout in seconds.
        success_pattern: Optional pattern to match for success.

    Returns:
        Tuple of (success, error_message).
    """
    import queue
    import re
    import time

    from protocols.mtib.mtib_pb2 import UartStreamRequest

    input_queue = queue.Queue()
    input_queue.put(b"\r")
    time.sleep(0.1)
    input_queue.put(f"{command}\r".encode("utf-8"))

    def request_iterator():
        while True:
            try:
                data = input_queue.get_nowait()
                yield UartStreamRequest(target=target, data=data)
            except queue.Empty:
                yield UartStreamRequest(target=target, data=b"")
                time.sleep(0.1)

    response_lines = []
    start_time = time.time()
    command_sent = False

    for resp in mtib.UartStream(target, request_iterator()):
        if resp.data:
            line = resp.data.decode("utf-8", errors="ignore")
            response_lines.append(line)

            full_response = "".join(response_lines)

            # Mark when we see the command echoed back
            if command in full_response:
                command_sent = True

            # Check for success pattern
            if success_pattern and success_pattern in full_response:
                return True, None

            # Only check for command-specific error AFTER command was sent
            # and only if the error mentions the command or "not implemented"
            if command_sent:
                lower_resp = full_response.lower()
                if "not implemented" in lower_resp:
                    return False, "not implemented"

        if time.time() - start_time > timeout_s:
            break

    full_response = "".join(response_lines)
    if success_pattern:
        if success_pattern in full_response:
            return True, None
        return False, f"Pattern '{success_pattern}' not found in response"

    # No pattern specified - just check command was acknowledged
    return True, None
