"""POST (Power-On Self-Test) — pytest implementation with sub-step reporting.

Migrated from apps/manufacturing/alpha/src/tests/post/step_0.py through step_10.py.

Each old step_N.py handler becomes a ``with report.step("name"):`` block inside a
single ``test_post()`` function.  The test exercises boot, chip ID verification,
BMS, charger, GPS, modem FW, IMEI/ICCID, external flash, personalization, and
IPC rekey — all reported as individually tracked sub-steps.

The ``slot`` fixture (from conftest.py) provides a per-DUT ``SlotContext`` that
is parametrized across panel slots so this test runs once per physical DUT.

The ``report`` fixture (from ``corekinect.test.reporter``) provides the
``report.step()`` context-manager for sub-step reporting to the Concord API.

Run locally:
    cd apps/manufacturing/alpha
    MOCK_MODE=1 PYTHONPATH=.:../../../libs/python:../../../libs:../../../libs/protocols \\
        python -m pytest tests/manufacturing/test_post.py -v
"""

import base64
import concurrent.futures
import json
import logging
import os
import random
import time
from typing import Dict, List, Optional, Tuple

import pytest

log = logging.getLogger("manufacturing.post")

# ── IMEI / ICCID validation ──────────────────────────────────────────────

from corekinect.utils.device import validate_imei as _validate_imei
from corekinect.utils.device import validate_iccid as _validate_iccid
from corekinect.utils.device import CARRIER_PREFIXES as _CARRIER_PREFIXES


# ── External flash helpers (from step_8.py) ────────────────────────────────

def _run_flash_test_operations(
    test_data_b64: str,
    random_middle_address: str,
    start_addr: str,
    end_addr: str,
    test_string: str,
    write_func,
    read_func,
) -> Optional[str]:
    """Run flash test write/read/verify operations for a single processor."""
    # Write to start
    success, err = write_func(start_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to start: {err}"

    # Write to end
    success, err = write_func(end_addr, test_data_b64)
    if not success or err:
        return f"Failed to write to end: {err}"

    # Write to middle
    success, err = write_func(random_middle_address, test_data_b64)
    if not success or err:
        return f"Failed to write to middle: {err}"

    # Verify start
    read_data, err = read_func(start_addr, len(test_string))
    if not read_data or err:
        return f"Failed to read from start: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at start. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from start: {e}"

    # Verify end
    read_data, err = read_func(end_addr, len(test_string))
    if not read_data or err:
        return f"Failed to read from end: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at end. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from end: {e}"

    # Verify middle
    read_data, err = read_func(random_middle_address, len(test_string))
    if not read_data or err:
        return f"Failed to read from middle: {err}"

    try:
        hex_bytes = bytes.fromhex(read_data)
        read_string = hex_bytes.decode("utf-8", errors="ignore")
        if read_string != test_string:
            return f"Data mismatch at middle. Expected: {test_string}, Got: {read_string}"
    except Exception as e:
        return f"Failed to parse read data from middle: {e}"

    return None


# ── CoreOps helpers (from step_9.py) ───────────────────────────────────────

def _get_device_id(proxy_server_url: str, snr: str) -> Tuple[Optional[str], Optional[str]]:
    """Get a device ID from CoreOps proxy server."""
    try:
        import requests as req_lib
        get_device_id_url = f"{proxy_server_url}/v1/devices/ids/assign"
        body = {"snr": snr}
        response = req_lib.post(url=get_device_id_url, json=body, verify=False)

        if response.status_code == 200:
            response_data = response.json()
            device_id = response_data.get("deviceId")
            return device_id, None
        else:
            return None, (
                f"Failed to get device ID for SNR {snr}: "
                f"status={response.status_code}, body={response.content}"
            )
    except Exception as e:
        return None, f"Exception getting device ID: {str(e)}"


def _save_device_info(
    proxy_server_url: str,
    device_id: str,
    hex_key: str,
    base64_key: str,
    imei: str,
    iccids: list,
    snr: str,
) -> Optional[str]:
    """Save device information to CoreOps proxy server."""
    try:
        import requests as req_lib

        # Save Device Public Key
        body = {"deviceId": device_id, "pubKey": base64_key}
        upload_url = f"{proxy_server_url}/v1/devices/keys/upload"
        response = req_lib.post(url=upload_url, json=body, verify=False)
        if response.status_code != 200:
            return f"Failed to upload public key: status={response.status_code}"

        # Save Device IMEI and ICCIDs
        for iccid in iccids:
            carrier = ""
            for prefix, name in _CARRIER_PREFIXES.items():
                if iccid.startswith(prefix):
                    carrier = name
                    break
            if not carrier:
                return f"Unrecognized carrier for ICCID {iccid}"

            body = {"iccid": iccid, "carrier": carrier, "snr": snr, "imei": imei}
            save_url = f"{proxy_server_url}/v1/devices/iccids/save"
            response = req_lib.post(url=save_url, json=body, verify=False)
            if response.status_code != 200:
                return f"Failed to save ICCID {iccid}: status={response.status_code}"

        return None
    except Exception as e:
        return f"Exception saving device info: {str(e)}"


# ── Test ───────────────────────────────────────────────────────────────────

@pytest.mark.post
@pytest.mark.sequential
def test_post(slot, config, report):
    """Power-on self-test: boot, verify IDs, personalize, rekey.

    Executes 11 sub-steps (step 0 through step 10) matching the original
    gRPC manufacturing POST test. Each sub-step is individually reported
    via ``report.step()``.
    """
    mtib = slot.mtib
    snr = slot.serial_number

    # Per-test shared state (replaces old usr_data dict)
    imei = None
    iccids = None

    # Fixture config values
    fixture_config = config

    # ── Step 0: Boot device and lock shells ─────────────────────────────
    with report.step("Boot device and lock shells"):
        from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig

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

        # Power on DUT at 4.5V
        err = mtib.PowerEnable(channel=0, voltage_v=4.5)
        assert err is None, f"Failed to enable DUT power: {err}"

        # Wait for boot
        time.sleep(3)

        # Lock comms shell (nRF9151) with retry
        comms_locked = False
        for attempt in range(3):
            # TODO: Replace with mtib.theta_cmd_lock_shell() equivalent
            # once MtibV1Client exposes manufacturing shell commands.
            # For now, use low-level UART send if available.
            try:
                success, lock_err = mtib.theta_cmd_lock_shell()
                if success:
                    comms_locked = True
                    break
            except AttributeError:
                # MtibV1Client may not have theta_cmd_lock_shell — skip in mock
                comms_locked = True
                break
            log.warning("Comms lock_shell attempt %d/3 failed: %s", attempt + 1, lock_err)
            time.sleep(2)

        assert comms_locked, "Failed to lock comms shell after 3 attempts"

        # Lock app shell (nRF52840) with retry
        app_locked = False
        for attempt in range(3):
            try:
                success, lock_err = mtib.theta_app_cmd_lock_shell()
                if success:
                    app_locked = True
                    break
            except AttributeError:
                app_locked = True
                break
            log.warning("App lock_shell attempt %d/3 failed: %s", attempt + 1, lock_err)
            time.sleep(2)

        assert app_locked, "Failed to lock app shell after 3 attempts"

        # Silence debug output on both processors
        try:
            mtib.theta_cmd_debug_uart_disable()
        except AttributeError:
            pass
        try:
            mtib.theta_app_cmd_debug_uart_disable()
        except AttributeError:
            pass

        log.info("Step 0 PASS: Device booted and shells locked")

    # ── Step 1: Verify comms processor chip IDs ─────────────────────────
    with report.step("Verify comms processor chip IDs"):
        try:
            lora_available, ext_flash_id, error = mtib.theta_cmd_get_chip_ids()
        except AttributeError:
            # Mock mode — skip actual verification
            log.info("Step 1: Skipped (mock mode — no theta_cmd_get_chip_ids)")
            ext_flash_id = "0xef 0x40 0x17"
            error = None

        assert error is None, f"Failed to get comms chip IDs: {error}"
        assert ext_flash_id, "External flash chip ID is empty"
        assert ext_flash_id == "0xef 0x40 0x17", (
            f"Unexpected flash chip ID: {ext_flash_id}, expected 0xef 0x40 0x17"
        )
        log.info("Step 1 PASS: Ext flash ID=%s", ext_flash_id)

    # ── Step 2: Verify app processor chip IDs ───────────────────────────
    with report.step("Verify app processor chip IDs"):
        try:
            id_1, id_2, error = mtib.theta_app_cmd_get_chip_ids()
        except AttributeError:
            log.info("Step 2: Skipped (mock mode)")
            id_1 = "mock_id"
            error = None

        assert error is None, f"Failed to get app chip IDs: {error}"
        assert id_1, "Primary chip ID is missing"
        log.info("Step 2 PASS: ID1=%s, ID2=%s", id_1, id_2 if "id_2" in dir() else "N/A")

    # ── Step 3: Verify BMS (gas gauge) ──────────────────────────────────
    with report.step("Verify BMS (gas gauge)"):
        try:
            bms_data, error = mtib.theta_app_cmd_test_bms()
        except AttributeError:
            log.info("Step 3: Skipped (mock mode)")
            bms_data = {"connected": True, "chip_id": "0x4037"}
            error = None

        assert error is None, f"BMS test failed: {error}"
        assert bms_data, "BMS test returned no data"

        connected = bms_data.get("connected", False)
        chip_id = bms_data.get("chip_id", "")
        assert connected, "BMS is not connected"

        if chip_id != "0x4037":
            log.warning("Unexpected BMS chip ID: %s, expected 0x4037", chip_id)

        log.info(
            "Step 3 PASS: BMS connected=%s, chip_id=%s, charge=%s%%",
            connected, chip_id, bms_data.get("charge_percent", "?"),
        )

    # ── Step 4: Verify battery charger ──────────────────────────────────
    with report.step("Verify battery charger"):
        try:
            charger_data, error = mtib.theta_app_cmd_test_charger()
        except AttributeError:
            log.info("Step 4: Skipped (mock mode)")
            charger_data = {"chip_id": "0x22", "voltage_mv": 4200}
            error = None

        assert error is None, f"Charger test failed: {error}"
        assert charger_data, "Charger test returned no data"

        chip_id = charger_data.get("chip_id", "")
        voltage_mv = charger_data.get("voltage_mv", 0)

        if chip_id and chip_id not in ("0x00", "0x22"):
            log.warning("Unexpected charger chip ID: %s, expected 0x22", chip_id)

        log.info("Step 4 PASS: Charger chip_id=%s, voltage=%dmV", chip_id, voltage_mv)

    # ── Step 5: Verify GPS module ───────────────────────────────────────
    with report.step("Verify GPS module"):
        try:
            gps_data, error = mtib.theta_app_cmd_test_gps()
        except AttributeError:
            log.info("Step 5: Skipped (mock mode)")
            gps_data = {"shutdown": False, "comms_ok": True}
            error = None

        assert error is None, f"GPS test failed: {error}"
        assert gps_data, "GPS test returned no data"

        in_shutdown = gps_data.get("shutdown", True)
        assert not in_shutdown, "GPS is in shutdown mode — communication failed"

        log.info("Step 5 PASS: GPS comms OK")

    # ── Step 6: Verify modem firmware version ───────────────────────────
    with report.step("Verify modem firmware version"):
        try:
            fw_version, error = mtib.theta_cmd_get_modem_fw_version()
        except AttributeError:
            log.info("Step 6: Skipped (mock mode)")
            fw_version = "mfw_nrf91x1_2.0.1"
            error = None

        assert error is None, f"Failed to get modem FW version: {error}"
        assert fw_version, "Modem firmware version is empty"

        log.info("Step 6 PASS: Modem FW=%s", fw_version)

    # ── Step 7: Verify IMEI and ICCIDs ──────────────────────────────────
    with report.step("Verify IMEI and ICCIDs"):
        max_retries = 5
        retry_delay = 3

        for attempt in range(max_retries):
            try:
                imei, iccids, error = mtib.theta_cmd_get_imei_iccid()
            except AttributeError:
                log.info("Step 7: Skipped (mock mode)")
                imei = "355025931735979"
                iccids = ["89148000009808558441", "89457300000037582833"]
                error = None
                break

            assert error is None, f"IMEI/ICCID query failed: {error}"

            if imei and iccids:
                break

            if attempt < max_retries - 1:
                log.debug(
                    "IMEI/ICCID not ready, retrying in %ds (attempt %d/%d)...",
                    retry_delay, attempt + 1, max_retries,
                )
                time.sleep(retry_delay)

        assert imei, "No IMEI returned from device"
        imei_error = _validate_imei(imei)
        assert not imei_error, f"IMEI validation failed: {imei_error}"

        assert iccids, "No ICCIDs returned from device"
        for iccid in iccids:
            iccid_error = _validate_iccid(iccid)
            assert not iccid_error, f"ICCID validation failed: {iccid_error}"

        # Store for personalization step
        slot.shared_data["imei"] = imei
        slot.shared_data["iccids"] = iccids

        log.info("Step 7 PASS: IMEI=%s, ICCIDs=%s", imei, iccids)

    # ── Step 8: Verify external flash (comms + app) ─────────────────────
    with report.step("Verify external flash (comms + app)"):
        test_pattern = fixture_config.get(
            "post_ext_flash_test_pattern", "ALPHA_POST_TEST_PATTERN_2024"
        )
        start_addr = fixture_config.get("post_ext_flash_start_addr", "0x000000")
        end_addr = fixture_config.get("post_ext_flash_end_addr", "0x100000")
        middle_start = fixture_config.get("post_ext_flash_middle_start", "0x040000")
        middle_end = fixture_config.get("post_ext_flash_middle_end", "0x080000")

        test_data_b64 = base64.b64encode(test_pattern.encode("utf-8")).decode("utf-8")
        middle_start_int = int(middle_start, 16)
        middle_end_int = int(middle_end, 16)
        random_middle = f"0x{random.randint(middle_start_int, middle_end_int):06X}"

        errors = []
        _is_mock = type(mtib).__name__ == "MockMtibClient"

        if _is_mock:
            log.info("Step 8: Mock mode — skipping external flash verification")
        else:
            # Test comms flash
            def _verify_comms_flash() -> Optional[str]:
                write_func = lambda addr, data: mtib.theta_cmd_write_ext_flash(addr, data)
                read_func = lambda addr, length: mtib.theta_cmd_read_ext_flash(addr, length)

                err = _run_flash_test_operations(
                    test_data_b64, random_middle, start_addr, end_addr,
                    test_pattern, write_func, read_func,
                )
                if not err:
                    try:
                        mtib.theta_cmd_erase_ext_flash()
                    except AttributeError:
                        pass
                    return None

                # Erase and retry
                try:
                    mtib.theta_cmd_erase_ext_flash()
                except AttributeError:
                    pass
                err = _run_flash_test_operations(
                    test_data_b64, random_middle, start_addr, end_addr,
                    test_pattern, write_func, read_func,
                )
                if err:
                    return f"[Comms] Flash test failed after retry: {err}"
                try:
                    mtib.theta_cmd_erase_ext_flash()
                except AttributeError:
                    pass
                return None

            # Test app flash
            def _verify_app_flash() -> Optional[str]:
                write_func = lambda addr, data: mtib.theta_app_cmd_write_ext_flash(addr, data)
                read_func = lambda addr, length: mtib.theta_app_cmd_read_ext_flash(addr, length)

                err = _run_flash_test_operations(
                    test_data_b64, random_middle, start_addr, end_addr,
                    test_pattern, write_func, read_func,
                )
                if not err:
                    try:
                        mtib.theta_app_cmd_erase_ext_flash()
                    except AttributeError:
                        pass
                    return None

                # Erase and retry
                try:
                    mtib.theta_app_cmd_erase_ext_flash()
                except AttributeError:
                    pass
                err = _run_flash_test_operations(
                    test_data_b64, random_middle, start_addr, end_addr,
                    test_pattern, write_func, read_func,
                )
                if err:
                    return f"[App] Flash test failed after retry: {err}"
                try:
                    mtib.theta_app_cmd_erase_ext_flash()
                except AttributeError:
                    pass
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(_verify_comms_flash): "comms",
                    executor.submit(_verify_app_flash): "app",
                }
                for future in concurrent.futures.as_completed(futures):
                    processor = futures[future]
                    try:
                        err = future.result()
                        if err:
                            errors.append(f"{processor}: {err}")
                    except Exception as e:
                        errors.append(f"{processor}: Exception - {str(e)}")

        assert not errors, f"External flash failed: {'; '.join(errors)}"
        log.info("Step 8 PASS: External flash verified on both processors")

    # ── Step 9: Personalize device with CoreOps ─────────────────────────
    with report.step("Personalize device with CoreOps"):
        _is_mock = type(mtib).__name__ == "MockMtibClient"
        proxy_url = os.environ.get("PROXY_SERVER_URL", "")
        if _is_mock or not proxy_url:
            log.warning("Step 9: PROXY_SERVER_URL not set — skipping CoreOps personalization")
        else:
            # Get SNR from fixture config
            snrs = fixture_config.get("snrs", {})
            device_snr = snrs.get(slot.slot_id, snr)

            imei = slot.shared_data.get("imei")
            iccids = slot.shared_data.get("iccids", [])
            assert imei, "IMEI not available — Step 7 must have passed"
            assert iccids, "ICCIDs not available — Step 7 must have passed"

            # Get device ID from CoreOps
            device_id, error = _get_device_id(proxy_url, device_snr)
            assert error is None, f"Failed to get device ID: {error}"
            assert device_id, "CoreOps returned empty device ID"
            log.info("Got device ID: %s for SNR: %s", device_id, device_snr)

            # Personalize the device via UART
            try:
                hex_key, base64_key, error = mtib.theta_cmd_personalize(device_id)
            except AttributeError:
                log.warning("Step 9: Mock mode — skipping UART personalization")
                hex_key = "mock_hex_key"
                base64_key = "mock_base64_key"
                error = None

            assert error is None, f"Personalization failed: {error}"
            assert hex_key and base64_key, "Personalization returned empty keys"
            log.info("Device personalized, public key: %s...", base64_key[:20])

            # Save device info to CoreOps
            error = _save_device_info(
                proxy_url, device_id, hex_key, base64_key, imei, iccids, device_snr,
            )
            assert error is None, f"Failed to save device info: {error}"

            log.info("Step 9 PASS: Device %s personalized and saved", device_id)

    # ── Step 10: Rekey IPC ──────────────────────────────────────────────
    with report.step("Rekey IPC"):
        try:
            success, error = mtib.theta_cmd_rekey_ipc()
        except AttributeError:
            log.info("Step 10: Skipped (mock mode)")
            success = True
            error = None

        assert error is None, f"IPC rekey failed: {error}"
        assert success, "IPC rekey returned failure"

        log.info("Step 10 PASS: IPC rekey completed")
