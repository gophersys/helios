"""Manufacturing demo #3 — POST (power-on self-test).

The ``booted_device`` fixture is provided by the framework once flashing
has completed in this slot — consuming it here means this test will be
skipped automatically on any slot where the flash step didn't succeed.
That's the right default: there's nothing to POST on a brick.
"""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.mfg_stage("stage_01")
@pytest.mark.timeout(60)
def test_post_identity(booted_device, report):
    """Replace me — read an identity string from the just-flashed device."""
    with report.step("read IMEI") as step:
        # >>> INSERT YOUR CODE HERE
        #
        #   imei = booted_device.shell("imei").strip()
        #   assert_and_record(step, "imei", imei, "str",
        #                     lambda v: len(v) == 15 and v.isdigit())
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
