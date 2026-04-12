"""POST (Power-On Self-Test) — boot, verify, personalize, rekey.

11 sub-steps matching the manufacturing test plan:
  0. Boot device, lock manufacturing shells on both processors
  1. Verify comms processor chip IDs (external flash = W25Q64)
  2. Verify app processor chip IDs (ext flash + BLE MAC)
  3. Verify BMS (MAX17263 gas gauge)
  4. Verify battery charger (BQ25180)
  5. Verify GPS module communication
  6. Verify modem firmware version
  7. Verify IMEI and ICCIDs (with modem warmup retry)
  8. Verify external flash on both processors (write/read/verify)
  9. Personalize device via CoreOps proxy
 10. Rekey IPC encryption

Uses AlphaAppShell (nRF52840) and CommsCoprocShell (nRF9151) for all
UART-based hardware commands. In mock mode, shell operations are skipped
and mock data is used instead.

Run locally:
    cd apps/manufacturing/alpha
    MOCK_MODE=1 PYTHONPATH=.:../../../libs/python:../../../libs:../../../libs/protocols \\
        python -m pytest tests/manufacturing/test_post.py -v
"""

import base64
import concurrent.futures
import logging
import os
import random
import time
from typing import Optional, Tuple

import pytest

from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from corekinect.utils.device import CARRIER_PREFIXES, validate_iccid, validate_imei

log = logging.getLogger("manufacturing.post")


# ── External flash helpers ────────────────────────────────────────────────

def _verify_ext_flash(
    write_fn,
    read_fn,
    erase_fn,
    test_pattern: str,
    start_addr: str,
    end_addr: str,
    middle_addr: str,
) -> Optional[str]:
    """Write/read/verify test pattern at three flash addresses.

    Returns None on success, error string on failure.
    """
    test_data_b64 = base64.b64encode(test_pattern.encode("utf-8")).decode("utf-8")
    addresses = [("start", start_addr), ("end", end_addr), ("middle", middle_addr)]

    # Write to all three addresses
    for label, addr in addresses:
        ok, err = write_fn(addr, test_data_b64)
        if err or not ok:
            return f"Write failed at {label} ({addr}): {err}"

    # Read back and verify
    for label, addr in addresses:
        hex_data, err = read_fn(addr, len(test_pattern))
        if err or not hex_data:
            return f"Read failed at {label} ({addr}): {err}"
        try:
            read_string = bytes.fromhex(hex_data).decode("utf-8", errors="ignore")
            if read_string != test_pattern:
                return f"Data mismatch at {label}: expected '{test_pattern}', got '{read_string}'"
        except (ValueError, UnicodeDecodeError) as e:
            return f"Parse error at {label}: {e}"

    # Clean up
    erase_fn()
    return None


# ── CoreOps helpers ───────────────────────────────────────────────────────

def _get_device_id(proxy_url: str, snr: str) -> Tuple[Optional[str], Optional[str]]:
    """Assign a device ID from CoreOps proxy server."""
    import requests

    try:
        resp = requests.post(
            f"{proxy_url}/v1/devices/ids/assign",
            json={"snr": snr},
            verify=False,
            timeout=15,
        )
        if resp.status_code == 200:
            device_id = resp.json().get("deviceId")
            return device_id, None
        return None, f"HTTP {resp.status_code}: {resp.content.decode()}"
    except Exception as e:
        return None, str(e)


def _save_device_info(
    proxy_url: str,
    device_id: str,
    base64_key: str,
    imei: str,
    iccids: list,
    snr: str,
) -> Optional[str]:
    """Upload device keys and SIM info to CoreOps proxy."""
    import requests

    try:
        # Upload public key
        resp = requests.post(
            f"{proxy_url}/v1/devices/keys/upload",
            json={"deviceId": device_id, "pubKey": base64_key},
            verify=False,
            timeout=15,
        )
        if resp.status_code != 200:
            return f"Key upload failed: HTTP {resp.status_code}"

        # Save each ICCID with carrier lookup
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
                verify=False,
                timeout=15,
            )
            if resp.status_code != 200:
                return f"ICCID save failed for {iccid}: HTTP {resp.status_code}"

        return None
    except Exception as e:
        return str(e)


# ── Test ──────────────────────────────────────────────────────────────────

@pytest.mark.post
@pytest.mark.sequential
def test_post(slot, config, report, is_mock):
    """Power-on self-test: boot, verify all hardware, personalize, rekey."""
    mtib = slot.mtib
    snr = slot.serial_number

    # Shell interfaces — only created for real hardware
    comms = None
    app = None

    if not is_mock:
        from corekinect.shells.alpha_app import AlphaAppShell
        from corekinect.shells.comms_coproc import CommsCoprocShell

        app = AlphaAppShell(mtib)
        comms = CommsCoprocShell(mtib)

    try:
        # ── Step 0: Boot device and lock shells ────────────────────────
        with report.step("Boot device and lock shells") as step:
            if is_mock:
                log.info("Mock mode — skipping boot and shell lock")
            else:
                # Power off both channels to ensure clean state
                mtib.PowerDisable(channel=0)
                mtib.PowerDisable(channel=1)
                time.sleep(2)

                # Start UART streams BEFORE power-on (MTIB hardware rule)
                comms.start()
                app.start()
                time.sleep(0.5)

                # Configure GPIO 0+1 as output LOW (required for DUT boot)
                for gpio in (0, 1):
                    err = mtib.GpioConfig(
                        gpio=gpio,
                        direction=GpioDirection.OUTPUT,
                        resistor=GpioResistorConfig.NONE,
                    )
                    assert err is None, f"GPIO {gpio} config failed: {err}"
                    err = mtib.GpioWrite(gpio=gpio, state=False)
                    assert err is None, f"GPIO {gpio} write failed: {err}"

                # Power on at 4.5V (NOT 4.0V — BQ25180 won't enable system rail at 4.0V)
                err = mtib.PowerEnable(channel=0, voltage_v=4.5)
                assert err is None, f"Failed to enable DUT power: {err}"
                step.record("boot_voltage", 4.5, unit="V")

                time.sleep(0.5)  # Brief settle, then lock immediately

                # Lock manufacturing shells (window is ~2-8s after boot)
                comms_locked = comms.lock(timeout_s=120)
                app_locked = app.lock(timeout_s=120)

                assert comms_locked, "Failed to lock comms manufacturing shell"
                assert app_locked, "Failed to lock app manufacturing shell"

                # Silence debug output and reset streams
                comms.debug_off()
                app.debug_off()
                comms.reset_stream()
                app.reset_stream()

                log.info("Both shells locked, debug disabled, streams reset")

        # ── Step 1: Comms processor chip IDs ───────────────────────────
        with report.step("Verify comms processor chip IDs") as step:
            if is_mock:
                step.record("ext_flash_id", "0xef 0x40 0x17")
                log.info("Mock: comms chip IDs OK")
            else:
                ids, err = comms.get_chip_ids()
                assert err is None, f"Failed to get comms chip IDs: {err}"

                expected_flash = "0xef 0x40 0x17"
                step.record("ext_flash_id", ids.ext_flash_id or "")
                assert ids.ext_flash_id == expected_flash, (
                    f"Unexpected flash ID: {ids.ext_flash_id}, expected {expected_flash}"
                )
                log.info("Comms ext flash ID: %s", ids.ext_flash_id)

        # ── Step 2: App processor chip IDs ─────────────────────────────
        with report.step("Verify app processor chip IDs") as step:
            if is_mock:
                step.record("ext_flash_id", "mock")
                step.record("ble_mac", "AA:BB:CC:DD:EE:FF")
                log.info("Mock: app chip IDs OK")
            else:
                ids, err = app.get_chip_ids()
                assert err is None, f"Failed to get app chip IDs: {err}"
                assert ids.ext_flash_id or ids.ble_mac, "No chip IDs returned"

                step.record("ext_flash_id", ids.ext_flash_id or "")
                step.record("ble_mac", ids.ble_mac or "")
                log.info("App ext flash: %s, BLE MAC: %s", ids.ext_flash_id, ids.ble_mac)

        # ── Step 3: BMS (gas gauge) ────────────────────────────────────
        with report.step("Verify BMS (gas gauge)") as step:
            if is_mock:
                step.record("connected", True)
                step.record("chip_id", "0x4037")
                log.info("Mock: BMS OK")
            else:
                bms, err = app.test_bms()
                assert err is None, f"BMS test failed: {err}"
                assert bms.connected, "BMS is not connected"

                step.record("connected", bms.connected)
                step.record("chip_id", bms.chip_id or "")
                step.record("charge_percent", bms.charge_percent or 0)
                step.record("temperature_c", bms.temperature_c or 0)

                if bms.chip_id and bms.chip_id != "0x4037":
                    log.warning("Unexpected BMS chip ID: %s (expected 0x4037)", bms.chip_id)
                log.info(
                    "BMS: connected=%s, chip_id=%s, charge=%s%%",
                    bms.connected, bms.chip_id, bms.charge_percent,
                )

        # ── Step 4: Battery charger ────────────────────────────────────
        with report.step("Verify battery charger") as step:
            if is_mock:
                step.record("chip_id", "0x22")
                step.record("battery_voltage_mv", 4200)
                log.info("Mock: charger OK")
            else:
                charger, err = app.test_charger()
                assert err is None, f"Charger test failed: {err}"

                step.record("chip_id", charger.chip_id or "")
                step.record("battery_voltage_mv", charger.battery_voltage_mv or 0)
                step.record("on_charger", charger.on_charger)

                if charger.chip_id and charger.chip_id not in ("0x00", "0x22"):
                    log.warning("Unexpected charger chip ID: %s (expected 0x22)", charger.chip_id)
                log.info(
                    "Charger: chip_id=%s, voltage=%smV",
                    charger.chip_id, charger.battery_voltage_mv,
                )

        # ── Step 5: GPS module ─────────────────────────────────────────
        with report.step("Verify GPS module") as step:
            if is_mock:
                step.record("comms_ok", True)
                log.info("Mock: GPS OK")
            else:
                gps, err = app.test_gps()
                assert err is None, f"GPS test failed: {err}"
                assert not gps.in_shutdown, "GPS is in shutdown — communication failed"

                step.record("in_shutdown", gps.in_shutdown)
                step.record("comms_ok", gps.comms_ok)
                log.info("GPS: shutdown=%s, comms=%s", gps.in_shutdown, gps.comms_ok)

        # ── Step 6: Modem firmware version ─────────────────────────────
        with report.step("Verify modem firmware version") as step:
            if is_mock:
                step.record("version", "mfw_nrf91x1_2.0.2")
                log.info("Mock: modem FW OK")
            else:
                modem, err = comms.get_modem_fw()
                assert err is None, f"Failed to get modem FW: {err}"
                assert modem.version, "Modem firmware version is empty"

                step.record("version", modem.version)
                log.info("Modem FW: %s", modem.version)

        # ── Step 7: IMEI and ICCIDs ────────────────────────────────────
        with report.step("Verify IMEI and ICCIDs") as step:
            if is_mock:
                imei = "355025931735979"
                iccids = ["89148000009808558441", "89457300000037582833"]
                step.record("imei", imei)
                step.record("iccid_count", len(iccids))
                log.info("Mock: IMEI=%s, ICCIDs=%s", imei, iccids)
            else:
                # Modem needs warmup — retry up to 5 times with 3s delay
                imei = None
                iccids = []
                for attempt in range(5):
                    sim, err = comms.get_sim_info(timeout_s=15)
                    if err is None and sim.imei and sim.iccids:
                        imei = sim.imei
                        iccids = sim.iccids
                        break
                    if attempt < 4:
                        log.info("IMEI/ICCID retry %d/5 (modem warming up)...", attempt + 1)
                        time.sleep(3)

                assert imei, "No IMEI returned from device after 5 attempts"
                imei_err = validate_imei(imei)
                assert not imei_err, f"IMEI validation failed: {imei_err}"

                assert iccids, "No ICCIDs returned from device"
                for iccid in iccids:
                    iccid_err = validate_iccid(iccid)
                    assert not iccid_err, f"ICCID validation failed for {iccid}: {iccid_err}"

                step.record("imei", imei)
                step.record("iccid_count", len(iccids))
                log.info("IMEI=%s, ICCIDs=%s", imei, iccids)

            # Store for personalization step
            slot.shared_data["imei"] = imei
            slot.shared_data["iccids"] = iccids

        # ── Step 8: External flash (comms + app) ───────────────────────
        with report.step("Verify external flash (comms + app)") as step:
            if is_mock:
                step.record("comms_flash", "mock_pass")
                step.record("app_flash", "mock_pass")
                log.info("Mock: ext flash OK")
            else:
                test_pattern = config.get(
                    "post_ext_flash_test_pattern", "ALPHA_POST_TEST_PATTERN_2024"
                )
                start_addr = config.get("post_ext_flash_start_addr", "0x000000")
                end_addr = config.get("post_ext_flash_end_addr", "0x100000")
                middle_start = int(config.get("post_ext_flash_middle_start", "0x040000"), 16)
                middle_end = int(config.get("post_ext_flash_middle_end", "0x080000"), 16)
                middle_addr = f"0x{random.randint(middle_start, middle_end):06X}"

                errors = []

                def _test_comms():
                    return _verify_ext_flash(
                        comms.write_ext_flash, comms.read_ext_flash, comms.erase_ext_flash,
                        test_pattern, start_addr, end_addr, middle_addr,
                    )

                def _test_app():
                    # App shell uses its own ext flash methods
                    def _app_write(addr, data_b64):
                        # AlphaAppShell.test_ext_flash is a single-shot test.
                        # For multi-address verification, use the comms shell pattern
                        # with the app shell's send() directly.
                        lines, err = app._cmd.send(
                            f"write_ext_flash {addr} {data_b64}",
                            success_patterns=["Writing", "Mfg shell:"],
                            timeout_s=15,
                        )
                        return (not err), err

                    def _app_read(addr, num_bytes):
                        lines, err = app._cmd.send(
                            f"read_ext_flash {addr} {num_bytes}",
                            success_patterns=["Reading", "Mfg shell:"],
                            timeout_s=15,
                        )
                        if err:
                            return None, err
                        hex_data = ""
                        for line in lines:
                            if ":" in line and "|" in line:
                                hex_part = line.split("|")[0].strip()
                                if ":" in hex_part:
                                    hex_values = hex_part.split(":", 1)[1].strip()
                                    hex_data += hex_values.replace(" ", "")
                        return hex_data or None, None if hex_data else "no data"

                    def _app_erase():
                        app._cmd.send(
                            "erase_ext_flash",
                            success_patterns=["Erasing flash"],
                            timeout_s=30,
                        )

                    return _verify_ext_flash(
                        _app_write, _app_read, _app_erase,
                        test_pattern, start_addr, end_addr, middle_addr,
                    )

                # Run both in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_comms = executor.submit(_test_comms)
                    future_app = executor.submit(_test_app)

                    comms_err = future_comms.result()
                    app_err = future_app.result()

                if comms_err:
                    errors.append(f"comms: {comms_err}")
                if app_err:
                    errors.append(f"app: {app_err}")

                step.record("comms_flash", "fail" if comms_err else "pass")
                step.record("app_flash", "fail" if app_err else "pass")

                assert not errors, f"External flash failed: {'; '.join(errors)}"
                log.info("External flash verified on both processors")

        # ── Step 9: Personalize device ─────────────────────────────────
        with report.step("Personalize device with CoreOps") as step:
            proxy_url = os.environ.get("PROXY_SERVER_URL", "")

            if is_mock or not proxy_url:
                log.info("Skipping personalization (mock=%s, proxy=%s)", is_mock, bool(proxy_url))
                step.record("status", "skipped")
            else:
                imei = slot.shared_data.get("imei")
                iccids = slot.shared_data.get("iccids", [])
                assert imei, "IMEI not available — step 7 must pass first"
                assert iccids, "ICCIDs not available — step 7 must pass first"

                # Get device ID from CoreOps (deterministic — same SNR always returns same ID)
                device_snr = config.get("snrs", {}).get(slot.slot_id, snr)
                device_id, err = _get_device_id(proxy_url, device_snr)
                assert err is None, f"Failed to get device ID: {err}"
                assert device_id, "CoreOps returned empty device ID"

                step.record("device_id", device_id)
                log.info("Device ID: %s (SNR: %s)", device_id, device_snr)

                # Personalize via UART — generates EC keypair on device
                keys, err = comms.personalize(device_id)
                assert err is None, f"Personalization failed: {err}"
                assert keys.base64_key, "Personalization returned empty public key"

                log.info("Device personalized, public key: %s...", keys.base64_key[:20])

                # Upload keys + SIM info to CoreOps
                err = _save_device_info(
                    proxy_url, device_id, keys.base64_key, imei, iccids, device_snr,
                )
                assert err is None, f"Failed to save device info: {err}"
                log.info("Device info saved to CoreOps")

        # ── Step 10: Rekey IPC ─────────────────────────────────────────
        with report.step("Rekey IPC") as step:
            if is_mock:
                step.record("status", "skipped")
                log.info("Mock mode — skipping IPC rekey")
            else:
                success, err = comms.rekey_ipc()
                assert err is None, f"IPC rekey failed: {err}"
                assert success, "IPC rekey returned failure"
                step.record("status", "success")
                log.info("IPC rekey completed")

    finally:
        # Always stop UART streams
        if comms:
            try:
                comms.stop()
            except Exception as e:
                log.warning("Failed to stop comms stream: %s", e)
        if app:
            try:
                app.stop()
            except Exception as e:
                log.warning("Failed to stop app stream: %s", e)
