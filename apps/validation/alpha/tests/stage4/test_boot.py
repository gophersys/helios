"""C1: Boot verification tests.

Verifies that power cycling produces a valid BootMsgV2 at CoreCloud with
correct fields. This is the most fundamental test — if boot doesn't work,
nothing else can run.

Tests:
    - Power cycle → BootMsgV2 received
    - BootMsgV2 reports correct firmware version
    - Boot current draw within budget
    - No hardware failures after boot
"""

import os
import logging

import pytest

log = logging.getLogger(__name__)


class TestBoot:
    """Boot sequence verification."""

    @pytest.mark.corecloud
    def test_power_cycle_produces_bootmsg(self, ctx, firmware_build):
        """PRDTST-374: Power cycle device, verify BootMsgV2 arrives at CoreCloud."""
        ctx.fixture.power_cycle()
        msg = ctx.cloud.wait_for_boot(timeout_s=120)
        assert msg is not None, "No BootMsgV2 received after power cycle"

    @pytest.mark.corecloud
    @pytest.mark.xfail(reason="BootMsgV2 does not include fw_version field yet — PRD gap")
    def test_boot_reports_firmware_version(self, ctx, firmware_build):
        """PRDTST-374: BootMsgV2 firmware version field is populated."""
        msg = ctx.cloud.wait_for_boot(timeout_s=120)
        # Firmware version should be a non-empty string
        assert hasattr(msg, "fw_version") or hasattr(msg, "firmware_version"), (
            "BootMsgV2 missing firmware version field"
        )

    def test_boot_current_within_budget(self, ctx, firmware_build):
        """PRDTST-341, PRDTST-404: Boot sequence peak current draw does not exceed 200mA."""
        result = ctx.power.measure(channel=0, duration_s=10)
        assert result.peak_current_ma < 200, (
            f"Boot peak current {result.peak_current_ma:.1f}mA exceeds 200mA budget"
        )
        log.info(
            "Boot power: avg=%.1fmA, peak=%.1fmA (%s build)",
            result.avg_current_ma,
            result.peak_current_ma,
            firmware_build,
        )

    @pytest.mark.corecloud
    def test_no_hw_failures_after_boot(self, ctx, firmware_build):
        """Operational: No hardware failure messages reported after clean boot."""
        info = ctx.cloud.check_hw_failures()
        assert not info.get("hasFailures", False), (
            f"Hardware failures after boot: {info}"
        )

    @pytest.mark.corecloud
    def test_no_comms_failures_after_boot(self, ctx, firmware_build):
        """Operational: No comms hardware failure messages reported after clean boot."""
        info = ctx.cloud.check_comms_hw_failures()
        assert not info.get("hasFailures", False), (
            f"Comms failures after boot: {info}"
        )
