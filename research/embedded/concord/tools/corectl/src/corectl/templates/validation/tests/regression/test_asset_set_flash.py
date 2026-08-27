"""Regression — demonstrates the asset-set firmware flow.

The ``stage_assets`` fixture resolves the current stage's pinned asset
set (from the backend run manifest). ``.hex("app", "debug")`` returns a
local path to the downloaded artifact — the framework caches it per
run so repeated calls are free.
"""

import pytest

from corekinect.test.assertions import assert_and_record


@pytest.mark.regression
@pytest.mark.hw_mtib
@pytest.mark.timeout(1800)
def test_placeholder_flash_from_asset_set(slot, stage_assets, report):
    """Replace me — canonical pattern for asset-set-driven regression."""
    with report.step("resolve asset set") as step:
        hex_path = stage_assets.hex("app", "debug")
        # The file is pre-validated by the runner (sha256 matched the
        # backend's asset record) — you don't need to re-check here.
        assert_and_record(
            step, "app_hex_bytes", hex_path.stat().st_size, "B",
            lambda v: v > 0,
        )

    with report.step("flash and verify") as step:
        # >>> INSERT YOUR CODE HERE
        #
        # Example:
        #   slot.flash(hex_path)
        #   slot.wait_for_boot(timeout_s=30)
        #   version = slot.shell("fw_version").strip()
        #   assert_and_record(step, "boot_ok", 1.0, "bool",
        #                     lambda v: v == 1.0)
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
