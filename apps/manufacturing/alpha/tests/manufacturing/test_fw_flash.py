"""Firmware flash test — J-Link programming + AP protect.

Flashes firmware onto both microcontrollers via the MTIB V1 server:
  1. Flash nRF52840 (app processor) with recover + retry
  2. Flash nRF9151 (comms processor) with recover + retry
  3. Set AP protect on both processors

Firmware source priority:
  1. Asset set from build run (via StageAssets / BUILD_RUN_ID)
  2. Config fallback filenames (local development)

Parametrized by firmware variant (debug/release) — both run if available
in the asset set. Skips if a variant is missing.

Run locally:
    cd apps/manufacturing/alpha
    MOCK_MODE=1 PYTHONPATH=.:../../../libs/python:../../../libs:../../../libs/protocols \\
        python -m pytest tests/manufacturing/test_fw_flash.py -v
"""

import logging
import time

import pytest

from protocols.mtib.mtib_pb2 import FwFileInfo, HostType

log = logging.getLogger("manufacturing.fw_flash")


def _flash_with_retry(mtib, fw_info, recover=True, max_attempts=2):
    """Flash firmware with one retry on failure.

    Returns:
        (time_ms, error) — time_ms is flash duration, error is None on success.
    """
    for attempt in range(1, max_attempts + 1):
        time_ms, err = mtib.FlashFwFile(fw_info, sector_erase=False, recover=recover)
        if not err:
            return time_ms, None
        if attempt < max_attempts:
            log.warning(
                "%s flash attempt %d failed: %s — retrying...",
                fw_info.name, attempt, err,
            )
            time.sleep(2)
    return None, err


@pytest.mark.fw_flash
@pytest.mark.sequential
@pytest.mark.parametrize("firmware_variant", ["debug", "release"])
def test_fw_flash(slot, config, report, mfg_assets, is_mock, firmware_variant):
    """Flash firmware and set AP protect on both processors."""
    mtib = slot.mtib

    # ── Resolve firmware files ─────────────────────────────────────────
    if mfg_assets:
        try:
            nrf52840_fw, nrf9151_fw = mfg_assets.hex_pair(firmware_variant)
            log.info(
                "Firmware from asset set (%s): app=%s, comms=%s",
                firmware_variant, nrf52840_fw, nrf9151_fw,
            )
        except KeyError:
            pytest.skip(f"Firmware variant '{firmware_variant}' not in asset set")
    else:
        suffix = firmware_variant
        nrf52840_fw = config.get(f"fw_flash_nrf52840_{suffix}_fw", f"alpha_{suffix}_nrf52840.hex")
        nrf9151_fw = config.get(f"fw_flash_nrf9151_{suffix}_fw", f"alpha_{suffix}_nrf9151.hex")

    step2_recover = config.get("fw_flash_step2_recover", True)

    # ── Step 1: Flash nRF52840 ─────────────────────────────────────────
    with report.step("Flash nRF52840 app firmware") as step:
        time.sleep(5)  # Power settling

        if is_mock:
            step.record("flash_time_ms", 0)
            log.info("Mock mode — skipping nRF52840 flash")
        else:
            fw_info = FwFileInfo(name=nrf52840_fw, target=HostType.HOST_TYPE_NRF52840)
            time_ms, err = _flash_with_retry(mtib, fw_info, recover=True)
            assert err is None, f"nRF52840 flash failed: {err}"
            step.record("flash_time_ms", time_ms or 0)
            log.info("nRF52840 flashed: %s (%dms)", nrf52840_fw, time_ms or 0)

    # ── Step 2: Flash nRF9151 ──────────────────────────────────────────
    with report.step("Flash nRF9151 comms firmware") as step:
        if is_mock:
            step.record("flash_time_ms", 0)
            log.info("Mock mode — skipping nRF9151 flash")
        else:
            fw_info = FwFileInfo(name=nrf9151_fw, target=HostType.HOST_TYPE_NRF9151)
            time_ms, err = _flash_with_retry(mtib, fw_info, recover=step2_recover)
            assert err is None, f"nRF9151 flash failed: {err}"
            step.record("flash_time_ms", time_ms or 0)
            log.info("nRF9151 flashed: %s (%dms)", nrf9151_fw, time_ms or 0)

    # ── Step 3: AP protect ─────────────────────────────────────────────
    with report.step("Set AP protect on both processors") as step:
        if is_mock:
            log.info("Mock mode — skipping AP protect")
        else:
            success, err = mtib.EnableAppProtect(target=HostType.HOST_TYPE_NRF52840)
            assert err is None, f"nRF52840 AP protect failed: {err}"
            log.info("nRF52840 AP protect enabled")

            success, err = mtib.EnableAppProtect(target=HostType.HOST_TYPE_NRF9151)
            assert err is None, f"nRF9151 AP protect failed: {err}"
            log.info("nRF9151 AP protect enabled")
