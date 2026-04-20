"""Driver — one driver per module. Power/clocks/UARTs/BLE/sensors."""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.driver
@pytest.mark.hw_mtib
@pytest.mark.timeout(300)
def test_placeholder(slot, report):
    """Replace me — add one file per driver (test_gpio.py, test_i2c.py, …)."""
    with report.step("placeholder driver check") as step:
        # >>> INSERT YOUR CODE HERE
        #
        # Example — verify the I2C bus settles to idle-high when unused:
        #   slot.i2c.quiesce()
        #   assert_adc_settles(step, slot.adc.stream("sda"), target_v=3.3,
        #                      tolerance_v=0.1, window_s=0.5)
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
