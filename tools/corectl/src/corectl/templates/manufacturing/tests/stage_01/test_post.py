"""Manufacturing demo #3 — POST (power-on self-test).

Runs after the firmware has been flashed in an earlier stage. The
``slot`` fixture is the canonical accessor for the DUT — use
``slot.uart``, ``slot.fixture``, etc. to talk to the just-flashed
device.
"""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.mfg_stage("stage_01")
@pytest.mark.timeout(60)
def test_post_identity(slot, report):
    """Replace me — read an identity string from the just-flashed device."""
    with report.step("read IMEI") as step:
        # >>> INSERT YOUR CODE HERE
        #
        #   slot.uart.send("comms", b"imei\n")
        #   imei = slot.uart.expect("comms", b"\r\n", timeout_s=2).decode().strip()
        #   assert_and_record(step, "imei", imei, "str",
        #                     lambda v: len(v) == 15 and v.isdigit())
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
