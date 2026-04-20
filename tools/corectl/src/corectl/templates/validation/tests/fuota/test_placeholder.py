"""FUOTA — firmware update over cellular.

FUOTA tests are long-running and interact with CoreCloud. Keep a short
preflight at the top of the file so a CoreCloud outage fails fast
instead of timing out 30 minutes in.
"""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.fuota
@pytest.mark.hw_mtib
@pytest.mark.timeout(3600)
def test_placeholder_fuota_cycle(slot, stage_assets, report):
    """Replace me — the real test flashes baseline, triggers FUOTA to a
    target image, waits for reboot, confirms the new app version."""
    with report.step("preflight") as step:
        # >>> INSERT YOUR CODE HERE — CoreCloud ping / baseline flash
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
