"""Manufacturing demo #2 — flash firmware from the pinned asset set.

The manufacturing runner pins an asset set (firmware bundle + metadata)
per production run. Reading through ``stage_assets`` — never hard-coded
paths — is what lets ops ship a new build without editing test code.
"""

import pytest

from corekinect.test.assertions import assert_and_record, assert_flash_success


@pytest.mark.mfg_stage("stage_01")
@pytest.mark.timeout(120)
def test_flash_application_firmware(slot, stage_assets, report):
    """Replace me — resolve → flash → read back version."""
    with report.step("flash app firmware") as step:
        hex_path = stage_assets.hex("app", "release")
        assert_and_record(
            step, "fw_bytes", hex_path.stat().st_size, "B",
            lambda v: v > 0,
        )

        # >>> INSERT YOUR CODE HERE
        #
        #   result = slot.flash(hex_path)
        #   assert_flash_success(step, result)
        #   version = slot.shell("fw_version").strip()
        #   assert_and_record(step, "fw_version", version, "str",
        #                     lambda v: v == stage_assets.manifest["version"])
        # ------------------------------------------------------------------
        assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
