"""Manufacturing demo #1 — ADC settle pattern.

Shows how to gate a manufacturing step on a power rail reaching its
target voltage within a tolerance window, as opposed to reading a
single sample (which races the rail's rise time).
"""

import pytest

from corekinect.test.assertions import assert_adc_settles


@pytest.mark.mfg_stage("stage_01")
@pytest.mark.timeout(30)
def test_3v3_rail_settles(slot, report):
    """Replace me — real manufacturing tests have one measurement each."""
    with report.step("3V3 rail settle") as step:
        # >>> INSERT YOUR CODE HERE
        #
        # Typical pattern:
        #   slot.power_on()
        #   assert_adc_settles(step, slot.adc.stream("3v3"),
        #                      target_v=3.3, tolerance_v=0.05,
        #                      window_s=0.5, timeout_s=5.0)
        # ------------------------------------------------------------------
        assert_adc_settles(
            step,
            samples=[(0.0, 3.30), (0.1, 3.30), (0.2, 3.30)],
            target_v=3.30, tolerance_v=0.05,
            window_s=0.1, timeout_s=1.0,
        )
