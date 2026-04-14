"""Firmware flash test — J-Link programming + AP protect.

Flashes firmware onto both microcontrollers via the MTIB V1 server:
  test_01 — Power up DUT with correct GPIO + voltage sequence
  test_02 — Flash nRF52840 (app processor) with recover + retry
  test_03 — Flash nRF9151 (comms processor) with recover + retry
  test_04 — Flash modem firmware (if available in asset set)
  test_05 — Set AP protect on both processors

Firmware source: AssetSet from ASSET_SET_ID (Concord AssetSet API).
Manufacturing always flashes debug firmware.

Run:
    Triggered via manufacturing session → panel scan → runner executes.
"""

import logging
import os
import time

import pytest

from protocols.mtib.mtib_pb2 import FwFileInfo, HostType

from .conftest import power_on_for_flashing

log = logging.getLogger("manufacturing.fw_flash")


def _upload_and_flash(mtib, hex_path: str, host_type, recover: bool = True, max_attempts: int = 2):
    """Upload firmware to MTIB server and flash via J-Link.

    Returns (flash_time_ms, error) — error is None on success.
    """
    name = os.path.basename(hex_path)

    err = mtib.UploadFwFile(hex_path, host_type)
    if err:
        return None, f"Upload failed for {name}: {err}"

    files_list, err = mtib.ListFwFiles()
    if err:
        return None, f"ListFwFiles failed: {err}"
    fw_file = next((f for f in (files_list or []) if f.name == name), None)
    if fw_file is None:
        return None, f"Uploaded file not found on MTIB server: {name}"

    log.info("Firmware uploaded to MTIB: %s (%s)", name, host_type)

    flash_ms = None
    last_err = None
    for attempt in range(1, max_attempts + 1):
        flash_ms, err = mtib.FlashFwFile(fw_file, sector_erase=False, recover=recover)
        if not err:
            last_err = None
            break
        last_err = err
        if attempt < max_attempts:
            log.warning("%s flash attempt %d failed: %s — retrying...", name, attempt, err)
            time.sleep(2)

    try:
        mtib.DeleteFwFile(FwFileInfo(name=name, target=host_type))
    except Exception:
        pass

    if last_err:
        return None, f"Flash failed after {max_attempts} attempts: {last_err}"
    return flash_ms, None


@pytest.mark.fw_flash
@pytest.mark.sequential
def test_01_power_on(slot, config, report):
    """Power up DUT for J-Link access."""
    battery_installed = config.get("battery_installed", False)

    with report.step("Configure GPIO and power rails for J-Link") as step:
        power_on_for_flashing(slot.mtib, battery_installed)
        step.record("boot_voltage_v", 4.5)
        step.record("battery_installed", battery_installed)
        log.info("DUT powered for J-Link: 4.5V, battery_installed=%s", battery_installed)

    slot.shared_data["flash_powered"] = True


@pytest.mark.fw_flash
@pytest.mark.sequential
def test_02_flash_app(slot, config, report, mfg_assets):
    """Flash nRF52840 (app processor) via J-Link."""
    with report.step("Flash nRF52840 app firmware") as step:
        if mfg_assets:
            if not mfg_assets.has_variant("debug"):
                pytest.skip("No debug firmware in asset set")
            try:
                nrf52840_fw, _ = mfg_assets.hex_pair("debug")
            except KeyError:
                pytest.skip("No debug app firmware in asset set")
        else:
            nrf52840_fw = config.get("fw_flash_nrf52840_debug_fw", "alpha_debug_nrf52840.hex")

        time_ms, err = _upload_and_flash(
            slot.mtib, nrf52840_fw, HostType.HOST_TYPE_NRF52840, recover=True,
        )
        assert err is None, f"nRF52840 flash failed: {err}"

        firmware_name = os.path.basename(nrf52840_fw)
        step.record("flash_time_ms", time_ms or 0)
        step.record("firmware", firmware_name)
        log.info("nRF52840 flashed: %s (%dms)", firmware_name, time_ms or 0)


@pytest.mark.fw_flash
@pytest.mark.sequential
def test_03_flash_comms(slot, config, report, mfg_assets):
    """Flash nRF9151 (comms processor) via J-Link."""
    step2_recover = config.get("fw_flash_step2_recover", True)

    with report.step("Flash nRF9151 comms firmware") as step:
        if mfg_assets:
            if not mfg_assets.has_variant("debug"):
                pytest.skip("No debug firmware in asset set")
            try:
                _, nrf9151_fw = mfg_assets.hex_pair("debug")
            except KeyError:
                pytest.skip("No debug comms firmware in asset set")
        else:
            nrf9151_fw = config.get("fw_flash_nrf9151_debug_fw", "alpha_debug_nrf9151.hex")

        time_ms, err = _upload_and_flash(
            slot.mtib, nrf9151_fw, HostType.HOST_TYPE_NRF9151, recover=step2_recover,
        )
        assert err is None, f"nRF9151 flash failed: {err}"

        firmware_name = os.path.basename(nrf9151_fw)
        step.record("flash_time_ms", time_ms or 0)
        step.record("firmware", firmware_name)
        log.info("nRF9151 flashed: %s (%dms)", firmware_name, time_ms or 0)


@pytest.mark.fw_flash
@pytest.mark.sequential
def test_04_flash_modem(slot, config, report, mfg_assets):
    """Flash modem firmware via DFU (if available in asset set)."""
    with report.step("Flash nRF9151 modem firmware") as step:
        if not mfg_assets or not mfg_assets.has_modem_fw():
            step.record("skipped", True)
            log.info("No modem firmware in asset set — skipping")
            pytest.skip("No modem firmware in asset set")

        modem_fw = mfg_assets.modem_fw()
        time_ms, err = _upload_and_flash(
            slot.mtib, modem_fw, HostType.HOST_TYPE_NRF9151_MODEM, recover=False,
        )
        assert err is None, f"Modem firmware flash failed: {err}"

        firmware_name = os.path.basename(modem_fw)
        step.record("flash_time_ms", time_ms or 0)
        step.record("firmware", firmware_name)
        log.info("Modem flashed: %s (%dms)", firmware_name, time_ms or 0)


@pytest.mark.fw_flash
@pytest.mark.sequential
def test_05_ap_protect(slot, config, report):
    """Set AP protect on both processors."""
    with report.step("Set AP protect on nRF52840") as step:
        success, err = slot.mtib.EnableAppProtect(target=HostType.HOST_TYPE_NRF52840)
        assert err is None, f"nRF52840 AP protect failed: {err}"
        step.record("nrf52840_protected", True)
        log.info("nRF52840 AP protect enabled")

    with report.step("Set AP protect on nRF9151") as step:
        success, err = slot.mtib.EnableAppProtect(target=HostType.HOST_TYPE_NRF9151)
        assert err is None, f"nRF9151 AP protect failed: {err}"
        step.record("nrf9151_protected", True)
        log.info("nRF9151 AP protect enabled")
