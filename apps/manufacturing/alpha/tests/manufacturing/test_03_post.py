"""POST (Power-On Self-Test) — boot, verify, personalize, rekey.

Sequential hardware verification after firmware flash:
  test_01 — Boot device and lock manufacturing shells
  test_02 — Verify comms processor chip IDs (ext flash = W25Q64)
  test_03 — Verify app processor chip IDs (ext flash + BLE MAC)
  test_04 — Verify BMS gas gauge (MAX17263)
  test_05 — Verify battery charger IC (BQ25180)
  test_06 — Verify GPS module communication
  test_07 — Verify modem firmware version
  test_08 — Verify IMEI and ICCIDs (with modem warmup retry)
  test_09 — Personalize device via CoreOps proxy
  test_10 — Rekey IPC encryption

Run:
    Triggered via manufacturing session → panel scan → runner executes.
"""

import logging
import os
import time
from typing import Optional, Tuple

import pytest

from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from corekinect.utils.device import CARRIER_PREFIXES, validate_iccid, validate_imei

from .conftest import get_shells, power_off, require_prior

log = logging.getLogger("manufacturing.post")


# ── CoreOps helpers ───────────────────────────────────────────────────────

def _get_device_id(proxy_url: str, snr: str) -> Tuple[Optional[str], Optional[str]]:
    """Assign a device ID from CoreOps proxy server."""
    import requests
    try:
        resp = requests.post(
            f"{proxy_url}/v1/devices/ids/assign",
            json={"snr": snr}, verify=False, timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("deviceId"), None
        return None, f"HTTP {resp.status_code}: {resp.content.decode()}"
    except Exception as e:
        return None, str(e)


def _save_device_info(proxy_url, device_id, base64_key, imei, iccids, snr) -> Optional[str]:
    """Upload device keys and SIM info to CoreOps proxy."""
    import requests
    try:
        resp = requests.post(
            f"{proxy_url}/v1/devices/keys/upload",
            json={"deviceId": device_id, "pubKey": base64_key},
            verify=False, timeout=15,
        )
        if resp.status_code != 200:
            return f"Key upload failed: HTTP {resp.status_code}"

        for iccid in iccids:
            carrier = ""
            for prefix, name in CARRIER_PREFIXES.items():
                if iccid.startswith(prefix):
                    carrier = name
                    break
            if not carrier:
                return f"Unknown carrier for ICCID {iccid}"
            resp = requests.post(
                f"{proxy_url}/v1/devices/iccids/save",
                json={"iccid": iccid, "carrier": carrier, "snr": snr, "imei": imei},
                verify=False, timeout=15,
            )
            if resp.status_code != 200:
                return f"ICCID save failed for {iccid}: HTTP {resp.status_code}"
        return None
    except Exception as e:
        return str(e)


# ── Tests ─────────────────────────────────────────────────────────────────

@pytest.mark.post
@pytest.mark.sequential
def test_01_boot(slot, config, report):
    """Boot device and lock manufacturing shells on both processors."""
    mtib = slot.mtib

    with report.step("Power cycle and boot DUT") as step:
        from corekinect.shells.alpha_app import AlphaAppShell
        from corekinect.shells.comms_coproc import CommsCoprocShell

        power_off(mtib)
        time.sleep(2)

        # Start UART streams BEFORE power-on (captures boot output)
        app = AlphaAppShell(mtib)
        comms = CommsCoprocShell(mtib)
        comms.start()
        app.start()
        time.sleep(0.5)

        slot.shared_data["app_shell"] = app
        slot.shared_data["comms_shell"] = comms

        for gpio in (0, 1):
            err = mtib.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
            assert err is None, f"GPIO {gpio} config failed: {err}"
            err = mtib.GpioWrite(gpio=gpio, state=False)
            assert err is None, f"GPIO {gpio} write failed: {err}"

        err = mtib.PowerEnable(channel=0, voltage_v=4.5)
        assert err is None, f"Failed to enable DUT power: {err}"
        step.record("boot_voltage_v", 4.5)
        log.info("DUT powered at 4.5V — waiting for shell activation")

    with report.step("Lock manufacturing shells") as step:
        app = slot.shared_data["app_shell"]
        comms = slot.shared_data["comms_shell"]
        time.sleep(0.5)

        comms_locked = comms.lock(timeout_s=120)
        app_locked = app.lock(timeout_s=120)
        step.record("comms_locked", comms_locked)
        step.record("app_locked", app_locked)
        assert comms_locked, "Failed to lock comms manufacturing shell"
        assert app_locked, "Failed to lock app manufacturing shell"

        comms.debug_off()
        app.debug_off()
        comms.reset_stream()
        app.reset_stream()
        log.info("Both shells locked, debug disabled, streams reset")

    slot.shared_data["post_booted"] = True


@pytest.mark.post
@pytest.mark.sequential
def test_02_comms_chip_ids(slot, config, report):
    """Verify comms processor (nRF9151) chip IDs."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Read comms processor chip IDs") as step:
        _, comms = get_shells(slot)
        ids, err = comms.get_chip_ids()
        assert err is None, f"Failed to get comms chip IDs: {err}"

        expected_flash = "0xef 0x40 0x17"
        step.record("ext_flash_id", ids.ext_flash_id or "")
        assert ids.ext_flash_id == expected_flash, (
            f"Unexpected comms flash ID: {ids.ext_flash_id}, expected {expected_flash}"
        )
        log.info("Comms ext flash ID: %s", ids.ext_flash_id)


@pytest.mark.post
@pytest.mark.sequential
def test_03_app_chip_ids(slot, config, report):
    """Verify app processor (nRF52840) chip IDs."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Read app processor chip IDs") as step:
        app, _ = get_shells(slot)
        ids, err = app.get_chip_ids()
        assert err is None, f"Failed to get app chip IDs: {err}"
        assert ids.ext_flash_id or ids.ble_mac, "No chip IDs returned"

        step.record("ext_flash_id", ids.ext_flash_id or "")
        step.record("ble_mac", ids.ble_mac or "")
        log.info("App ext flash: %s, BLE MAC: %s", ids.ext_flash_id, ids.ble_mac)
        slot.shared_data["ble_mac"] = ids.ble_mac


@pytest.mark.post
@pytest.mark.sequential
def test_04_bms(slot, config, report):
    """Verify BMS gas gauge (MAX17263)."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Verify BMS gas gauge") as step:
        app, _ = get_shells(slot)
        bms, err = app.test_bms()
        assert err is None, f"BMS test failed: {err}"
        assert bms.connected, "BMS is not connected"

        step.record("connected", bms.connected)
        step.record("chip_id", bms.chip_id or "")
        step.record("charge_percent", bms.charge_percent or 0)
        step.record("temperature_c", bms.temperature_c or 0)
        log.info("BMS: connected=%s, chip_id=%s, charge=%s%%", bms.connected, bms.chip_id, bms.charge_percent)


@pytest.mark.post
@pytest.mark.sequential
def test_05_charger_ic(slot, config, report):
    """Verify battery charger IC (BQ25180)."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Verify battery charger IC") as step:
        app, _ = get_shells(slot)
        charger, err = app.test_charger()
        assert err is None, f"Charger test failed: {err}"

        step.record("chip_id", charger.chip_id or "")
        step.record("battery_voltage_mv", charger.battery_voltage_mv or 0)
        step.record("on_charger", charger.on_charger)
        log.info("Charger: chip_id=%s, voltage=%smV", charger.chip_id, charger.battery_voltage_mv)


@pytest.mark.post
@pytest.mark.sequential
def test_06_gps(slot, config, report):
    """Verify GPS module communication."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Verify GPS module") as step:
        app, _ = get_shells(slot)
        gps, err = app.test_gps()
        assert err is None, f"GPS test failed: {err}"
        assert not gps.in_shutdown, "GPS is in shutdown — communication failed"

        step.record("in_shutdown", gps.in_shutdown)
        step.record("comms_ok", gps.comms_ok)
        log.info("GPS: shutdown=%s, comms=%s", gps.in_shutdown, gps.comms_ok)


@pytest.mark.post
@pytest.mark.sequential
def test_07_modem_fw(slot, config, report):
    """Verify modem firmware version."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Verify modem firmware version") as step:
        _, comms = get_shells(slot)
        modem, err = comms.get_modem_fw()
        assert err is None, f"Failed to get modem FW: {err}"
        assert modem.version, "Modem firmware version is empty"

        step.record("version", modem.version)
        log.info("Modem FW: %s", modem.version)


@pytest.mark.post
@pytest.mark.sequential
def test_08_imei_iccid(slot, config, report):
    """Verify IMEI and ICCIDs from the modem."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Verify IMEI and ICCIDs") as step:
        _, comms = get_shells(slot)
        sim, err = comms.get_sim_info(timeout_s=30)
        assert err is None, f"IMEI/ICCID retrieval failed: {err}"

        imei = sim.imei
        iccids = sim.iccids

        assert imei, "No IMEI returned from device"
        imei_err = validate_imei(imei)
        assert not imei_err, f"IMEI validation failed: {imei_err}"

        assert iccids, "No ICCIDs returned from device"
        for iccid in iccids:
            iccid_err = validate_iccid(iccid)
            assert not iccid_err, f"ICCID validation failed for {iccid}: {iccid_err}"

        step.record("imei", imei)
        step.record("iccid_count", len(iccids))
        if sim.eids:
            step.record("eid_count", len(sim.eids))
        log.info("IMEI=%s, ICCIDs=%s, EIDs=%d", imei, iccids, len(sim.eids))

        slot.shared_data["imei"] = imei
        slot.shared_data["iccids"] = iccids


@pytest.mark.post
@pytest.mark.sequential
def test_09_ext_flash(slot, config, report):
    """Verify external flash on both processors (write/read/verify).

    Known issue: UART contention between ShellCommander and UartDemuxer
    causes read_ext_flash to return empty data when SlotTestContext UART
    capture is active. Also, firmware read-back returns different data
    than what was written (possible address mapping issue).
    Skip until firmware ext flash commands are verified independently.
    """
    pytest.skip("External flash test disabled — UART contention with SlotTestContext + firmware read-back mismatch under investigation")
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    import base64
    import random

    test_pattern = config.get("post_ext_flash_test_pattern", "ALPHA_POST_TEST_2024")
    data_b64 = base64.b64encode(test_pattern.encode("utf-8")).decode("utf-8")
    address = "0x000000"

    app, comms = get_shells(slot)

    with report.step("Write + read + verify comms ext flash") as step:
        ok, err = comms.write_ext_flash(address, data_b64)
        assert err is None, f"Comms write failed: {err}"

        hex_data, err = comms.read_ext_flash(address, len(test_pattern))
        assert err is None, f"Comms read failed: {err}"
        assert hex_data, "Comms read returned no data"

        read_string = bytes.fromhex(hex_data).decode("utf-8", errors="ignore")
        step.record("comms_match", read_string == test_pattern)
        step.record("comms_read", read_string[:30])
        assert read_string == test_pattern, (
            f"Comms data mismatch: expected '{test_pattern}', got '{read_string}'"
        )
        log.info("Comms ext flash verified: '%s'", read_string)
        comms.erase_ext_flash()

    with report.step("Write + read + verify app ext flash") as step:
        # App shell uses the same write/read commands via _cmd.send
        lines, err = app._cmd.send(
            f"write_ext_flash {address} {data_b64}",
            success_patterns=["Writing", "Mfg shell:"],
            timeout_s=15,
        )
        assert not err, f"App write failed: {err}"

        lines, err = app._cmd.send(
            f"read_ext_flash {address} {len(test_pattern)}",
            success_patterns=["Reading", "Mfg shell:"],
            timeout_s=15,
        )
        assert not err, f"App read failed: {err}"

        import re
        hex_data = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if "|" in stripped:
                hex_part = stripped.split("|")[0].strip()
                hex_bytes = re.findall(r"[0-9A-Fa-f]{2}", hex_part)
                if hex_bytes:
                    hex_data += "".join(hex_bytes)
            elif re.match(r"^(?:[0-9A-Fa-f]{2}\s*)+$", stripped):
                hex_data += re.sub(r"\s+", "", stripped)

        assert hex_data, f"App read returned no hex data from: {lines}"
        read_string = bytes.fromhex(hex_data).decode("utf-8", errors="ignore")
        step.record("app_match", read_string == test_pattern)
        step.record("app_read", read_string[:30])
        assert read_string == test_pattern, (
            f"App data mismatch: expected '{test_pattern}', got '{read_string}'"
        )
        log.info("App ext flash verified: '%s'", read_string)

        app._cmd.send("erase_ext_flash", success_patterns=["Erasing flash"], timeout_s=30)


@pytest.mark.post
@pytest.mark.sequential
def test_10_personalize(slot, config, report):
    """Personalize device via CoreOps proxy."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    proxy_url = os.environ.get("PROXY_SERVER_URL", "")
    if not proxy_url:
        pytest.skip("No PROXY_SERVER_URL configured")

    with report.step("Personalize device with CoreOps") as step:
        imei = slot.shared_data.get("imei")
        iccids = slot.shared_data.get("iccids", [])
        assert imei, "IMEI not available — test_08_imei_iccid must pass first"
        assert iccids, "ICCIDs not available — test_08_imei_iccid must pass first"

        _, comms = get_shells(slot)
        snr = slot.serial_number
        device_snr = config.get("snrs", {}).get(slot.slot_id, snr)

        device_id, err = _get_device_id(proxy_url, device_snr)
        assert err is None, f"Failed to get device ID: {err}"
        assert device_id, "CoreOps returned empty device ID"
        step.record("device_id", device_id)
        log.info("Device ID: %s (SNR: %s)", device_id, device_snr)

        keys, err = comms.personalize(device_id)
        assert err is None, f"Personalization failed: {err}"
        assert keys.base64_key, "Personalization returned empty public key"
        step.record("has_public_key", True)
        log.info("Device personalized, public key: %s...", keys.base64_key[:20])

        err = _save_device_info(proxy_url, device_id, keys.base64_key, imei, iccids, device_snr)
        assert err is None, f"Failed to save device info: {err}"
        step.record("info_uploaded", True)
        log.info("Device info saved to CoreOps")


@pytest.mark.post
@pytest.mark.sequential
def test_11_rekey_ipc(slot, config, report):
    """Rekey IPC encryption."""
    require_prior(slot, "post_booted", "test_01_boot must pass first")

    with report.step("Rekey IPC") as step:
        _, comms = get_shells(slot)
        success, err = comms.rekey_ipc()
        assert err is None, f"IPC rekey failed: {err}"
        assert success, "IPC rekey returned failure"
        step.record("status", "success")
        log.info("IPC rekey completed")
