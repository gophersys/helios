"""Smoke — one quick check per subsystem the fixture exposes.

Stays under 5 minutes total. If a test belongs here it must answer
"does the board turn on and talk to us at all" — deeper checks go in
driver/integration/regression.
"""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.smoke
@pytest.mark.hw_mtib
@pytest.mark.timeout(120)
def test_placeholder(slot, report):
    """Replace me — the scaffold ships a single pass-by-default test so
    ``corectl validate`` sees a collectable suite immediately.
    """
    with report.step("placeholder smoke check") as step:
        # >>> INSERT YOUR CODE HERE
        #
        # Typical smoke pattern:
        #   slot.power_on()
        #   assert_and_record(step, "3v3_rail_v", slot.adc.read("3v3"), "V",
        #                     lambda v: 3.2 <= v <= 3.4)
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
