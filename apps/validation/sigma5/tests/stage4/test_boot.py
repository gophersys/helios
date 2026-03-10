"""C1: Boot verification tests for Sigma5.

Verifies that power cycling produces valid boot behavior.
Tests apply to both nRF52840 app processor and nRF9160 comms.

Tests:
    - Power cycle produces BootMsgV2 at CoreCloud
    - Boot current draw within budget
    - No hardware failures after boot
"""

import logging

import pytest

log = logging.getLogger(__name__)


class TestBoot:
    """Boot sequence verification for Sigma5."""

    @pytest.mark.corecloud
    def test_power_cycle_produces_bootmsg(self, ctx, firmware_build):
        """PRDTST-S5-001: Power cycle device, verify BootMsgV2 arrives at CoreCloud."""
        ctx.fixture.power_cycle()
        msg = ctx.cloud.wait_for_boot(timeout_s=120)
        assert msg is not None, "No BootMsgV2 received after power cycle"

    @pytest.mark.corecloud
    @pytest.mark.xfail(reason="BootMsgV2 may not include fw_version field")
    def test_boot_reports_firmware_version(self, ctx, firmware_build):
        """PRDTST-S5-002: BootMsgV2 firmware version field is populated."""
        msg = ctx.cloud.wait_for_boot(timeout_s=120)
        assert hasattr(msg, "fw_version") or hasattr(msg, "firmware_version"), (
            "BootMsgV2 missing firmware version field"
        )

    def test_boot_current_within_budget(self, ctx, firmware_build):
        """PRDTST-S5-003: Boot peak current does not exceed 150mA."""
        result = ctx.power.measure(channel=0, duration_s=10)
        assert result.peak_current_ma < 150, (
            f"Boot peak current {result.peak_current_ma:.1f}mA exceeds 150mA budget"
        )
        log.info(
            "Boot power: avg=%.1fmA, peak=%.1fmA (%s build)",
            result.avg_current_ma,
            result.peak_current_ma,
            firmware_build,
        )

    @pytest.mark.corecloud
    def test_no_hw_failures_after_boot(self, ctx, firmware_build):
        """PRDTST-S5-004: No hardware failure messages after clean boot."""
        info = ctx.cloud.check_hw_failures()
        assert not info.get("hasFailures", False), (
            f"Hardware failures after boot: {info}"
        )

    @pytest.mark.corecloud
    def test_no_comms_failures_after_boot(self, ctx, firmware_build):
        """PRDTST-S5-005: No comms failures after clean boot."""
        info = ctx.cloud.check_comms_hw_failures()
        assert not info.get("hasFailures", False), (
            f"Comms failures after boot: {info}"
        )
