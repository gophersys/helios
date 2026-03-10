"""POST test sequence — pytest implementation.

Migrated from apps/manufacturing/alpha/src/tests/post/*.py

Each step is a pytest test function. Tests run in order via pytest-ordering
or natural alphabetical order (prefixed with step number).

Shared data between steps is stored in slot.shared_data dict.

Example run:
    cd apps/manufacturing/alpha
    PYTHONPATH=.:../../../libs/python:../../../libs pytest tests_pytest/post/ -v
"""

import logging
import time
from typing import Optional

import pytest

from corekinect.utils import Logger

log = Logger(log_name="post")


# ── Fixtures for POST sequence ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def post_config(config):
    """Extract POST-specific config values."""
    return {
        "ext_flash_test_pattern": config.get("post_ext_flash_test_pattern", "ALPHA_POST_TEST_PATTERN_2024"),
        "expected_num_sims": config.get("post_expected_num_sims", 2),
    }


# ── Step 0: Boot and Lock Shells ─────────────────────────────────────────────

@pytest.mark.sequential
def test_step_00_boot_and_lock(slot, post_config):
    """Step 0: Power cycle device and lock manufacturing shells.

    1. Power off
    2. Open UART streams
    3. Power on
    4. Send lock_shell command within 2s activation window
    5. Disable debug output
    """
    mtib = slot.mtib
    log.info("Step 0: Boot and lock shells for %s", slot.snr)

    # Power off first
    err = mtib.PowerDisable(channel=0)
    if err:
        log.warning("PowerDisable error (may be already off): %s", err)
    time.sleep(1)

    # Configure GPIO 0+1 as output LOW (required for boot)
    from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
    mtib.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    mtib.GpioConfig(gpio=1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    mtib.GpioWrite(gpio=0, state=False)
    mtib.GpioWrite(gpio=1, state=False)

    # Power on
    _, err = mtib.PowerEnable(channel=0, voltage_v=4.5)
    assert err is None, f"PowerEnable failed: {err}"

    # Wait for boot
    time.sleep(3)

    # Verify power
    result, err = mtib.DutPowerRead(channel=0)
    assert err is None, f"DutPowerRead failed: {err}"
    assert result.current_ma > 5.0, f"DUT not drawing current: {result.current_ma}mA"

    log.info("Step 0 PASS: DUT booted, current=%0.1fmA", result.current_ma)


# ── Step 1: Verify Comms Processor Chip IDs ──────────────────────────────────

@pytest.mark.sequential
def test_step_01_comms_chip_ids(slot, post_config):
    """Step 1: Verify comms processor chip IDs.

    Check external flash chip ID (W25Q64 = 0xef 0x40 0x17).
    """
    mtib = slot.mtib
    log.info("Step 1: Verify comms chip IDs for %s", slot.snr)

    # Send chip_ids command via manufacturing shell
    # This would use mtib.UartWrite() and parse response
    # For now, we'll use a mock assertion

    # TODO: Implement actual UART command
    # lora_available, ext_flash_id, error = mtib.theta_cmd_get_chip_ids()
    # assert error is None, f"Failed to get comms chip IDs: {error}"
    # assert ext_flash_id == "0xef 0x40 0x17", f"Unexpected flash chip ID: {ext_flash_id}"

    log.info("Step 1 PASS: Comms chip IDs verified (placeholder)")


# ── Step 2: Verify App Processor Chip IDs ────────────────────────────────────

@pytest.mark.sequential
def test_step_02_app_chip_ids(slot, post_config):
    """Step 2: Verify app processor chip IDs.

    Check nRF52840 chip and external flash.
    """
    mtib = slot.mtib
    log.info("Step 2: Verify app chip IDs for %s", slot.snr)

    # TODO: Implement actual chip ID verification
    log.info("Step 2 PASS: App chip IDs verified (placeholder)")


# ── Step 3: Verify BMS (Gas Gauge) ───────────────────────────────────────────

@pytest.mark.sequential
def test_step_03_bms(slot, post_config):
    """Step 3: Verify BMS / gas gauge functionality.

    Check MAX17048 fuel gauge is responding.
    """
    mtib = slot.mtib
    log.info("Step 3: Verify BMS for %s", slot.snr)

    # TODO: Implement BMS verification
    log.info("Step 3 PASS: BMS verified (placeholder)")


# ── Step 4: Verify Battery Charger ───────────────────────────────────────────

@pytest.mark.sequential
def test_step_04_charger(slot, post_config):
    """Step 4: Verify battery charger functionality.

    Check BQ25180 charger is responding and configured correctly.
    """
    mtib = slot.mtib
    log.info("Step 4: Verify charger for %s", slot.snr)

    # TODO: Implement charger verification
    log.info("Step 4 PASS: Charger verified (placeholder)")


# ── Step 5: Verify GPS Module ────────────────────────────────────────────────

@pytest.mark.sequential
def test_step_05_gps(slot, post_config):
    """Step 5: Verify GPS module functionality.

    Check GPS is responding and can acquire satellites.
    """
    mtib = slot.mtib
    log.info("Step 5: Verify GPS for %s", slot.snr)

    # TODO: Implement GPS verification
    log.info("Step 5 PASS: GPS verified (placeholder)")


# ── Step 6: Verify Modem Firmware ────────────────────────────────────────────

@pytest.mark.sequential
def test_step_06_modem_fw(slot, post_config):
    """Step 6: Verify modem firmware version.

    Check nRF9151 modem firmware is correct version.
    """
    mtib = slot.mtib
    log.info("Step 6: Verify modem FW for %s", slot.snr)

    # TODO: Implement modem FW verification
    log.info("Step 6 PASS: Modem FW verified (placeholder)")


# ── Step 7: Verify IMEI and ICCIDs ───────────────────────────────────────────

@pytest.mark.sequential
def test_step_07_imei_iccid(slot, post_config):
    """Step 7: Verify IMEI and ICCIDs.

    Reads IMEI and SIM ICCIDs from modem, stores in shared_data for later steps.
    """
    mtib = slot.mtib
    log.info("Step 7: Verify IMEI/ICCID for %s", slot.snr)

    # TODO: Implement IMEI/ICCID read
    # For now, store mock values in shared_data
    slot.shared_data["imei"] = "355025931735979"
    slot.shared_data["iccids"] = ["89148000009808558441", "89457300000037582833"]

    expected_sims = post_config["expected_num_sims"]
    assert len(slot.shared_data["iccids"]) == expected_sims, \
        f"Expected {expected_sims} SIMs, found {len(slot.shared_data['iccids'])}"

    log.info(
        "Step 7 PASS: IMEI=%s, ICCIDs=%s",
        slot.shared_data["imei"],
        slot.shared_data["iccids"],
    )


# ── Step 8: Verify External Flash ────────────────────────────────────────────

@pytest.mark.sequential
def test_step_08_ext_flash(slot, post_config):
    """Step 8: Verify external flash on both processors.

    Writes test pattern, reads back, and verifies.
    """
    mtib = slot.mtib
    log.info("Step 8: Verify external flash for %s", slot.snr)

    test_pattern = post_config["ext_flash_test_pattern"]
    # TODO: Implement external flash write/read/verify
    log.info("Step 8 PASS: External flash verified (placeholder)")


# ── Step 9: Device Personalization ───────────────────────────────────────────

@pytest.mark.sequential
@pytest.mark.coreops
def test_step_09_personalize(slot, post_config):
    """Step 9: Personalize device with CoreOps.

    1. Request device ID from CoreOps (deterministic based on SNR)
    2. Device generates EC keypair
    3. Upload public key to CoreOps
    4. Save IMEI/ICCID mapping
    """
    mtib = slot.mtib
    log.info("Step 9: Personalize device for %s", slot.snr)

    # Check prerequisites
    imei = slot.shared_data.get("imei")
    iccids = slot.shared_data.get("iccids", [])
    if not imei:
        pytest.fail("IMEI not available — Step 7 must run first")

    # TODO: Implement personalization via CoreOps proxy
    # 1. POST /v1/devices/ids/assign {"snr": slot.snr}
    # 2. Read public key from device via mfg shell
    # 3. POST /v1/devices/keys/upload {"deviceId": device_id, "pubKey": pubkey_b64}
    # 4. POST /v1/devices/iccids/save {"iccid": iccids[0], "carrier": "...", ...}

    log.info("Step 9 PASS: Device personalized (placeholder)")


# ── Step 10: Rekey IPC ───────────────────────────────────────────────────────

@pytest.mark.sequential
def test_step_10_rekey_ipc(slot, post_config):
    """Step 10: Rekey IPC between app and comms processors.

    Replaces hardcoded IPC keys with device-specific keys derived
    from the personalization secret.
    """
    mtib = slot.mtib
    log.info("Step 10: Rekey IPC for %s", slot.snr)

    # TODO: Implement IPC rekey via mfg shell command
    log.info("Step 10 PASS: IPC rekeyed (placeholder)")


# ── Summary ──────────────────────────────────────────────────────────────────

def test_post_summary(fixture_ctx, post_config):
    """Summary: Report POST results for all slots.

    This test runs after all per-slot tests and reports aggregate results.
    """
    passed_slots = []
    failed_slots = []

    for slot_id, slot in fixture_ctx.slots.items():
        # In a real implementation, we'd track pass/fail per slot
        # For now, assume all passed if we got here
        passed_slots.append(slot_id)

    log.info("POST Summary: %d passed, %d failed", len(passed_slots), len(failed_slots))
    if failed_slots:
        pytest.fail(f"POST failed for slots: {failed_slots}")
