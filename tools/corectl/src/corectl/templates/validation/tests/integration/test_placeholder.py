"""Integration — exercises that touch 2+ subsystems together.

Example scope: "boot → join cellular → publish telemetry → receive ack".
Each test here should have one failure mode that is hard to attribute to
a single driver — that is the value integration tests provide.
"""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.integration
@pytest.mark.hw_mtib
@pytest.mark.timeout(900)
def test_placeholder(slot, report):
    """Replace me — good integration tests name the flow in their title."""
    with report.step("placeholder integration flow") as step:
        # >>> INSERT YOUR CODE HERE
        #
        # Example — boot-to-telemetry:
        #   slot.power_on()
        #   slot.wait_for_boot(timeout_s=30)
        #   msg = slot.cloud.wait_for_message("telemetry", timeout_s=60)
        #   assert_and_record(step, "first_telemetry_ms",
        #                     msg.arrival_ms, "ms",
        #                     lambda v: v < 60_000)
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
