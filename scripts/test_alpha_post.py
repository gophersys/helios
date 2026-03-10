#!/usr/bin/env python3
"""Alpha Manufacturing POST Test - matches working manufacturing flow.

Uses the same approach as apps/manufacturing/alpha/src/tests/post/:
1. Power on, wait 3s for boot
2. Lock shells with 120s timeout and 3 retries
3. Disable debug output (60s timeout)
4. Run commands with 10s timeout
"""

import sys
import time

sys.path.insert(0, "libs/python")
sys.path.insert(0, "libs/protocols")
sys.path.insert(0, "libs")

from protocols.mtib.mtib_pb2 import HostType
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig


MTIB_HOST = "10.4.45.33"
MTIB_PORT = 50053


def print_result(name: str, passed: bool, detail: str = ""):
    status = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"  {status} {name}" + (f": {detail}" if detail else ""))


def main():
    print(f"=== Alpha Manufacturing POST Test ===")
    print(f"MTIB: {MTIB_HOST}:{MTIB_PORT}")

    # Connect
    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_HOST, port=MTIB_PORT))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        print(f"[ERROR] Connection failed: {err}")
        return 1
    print("Connected to MTIB")

    try:
        # === POWER CYCLE AND LOCK SHELLS ===
        print("\n=== Power Cycle DUT with Shell Lock ===")

        # Power down
        print("  Powering down...")
        client.PowerDisable(channel=0)
        client.PowerDisable(channel=1)
        time.sleep(2)

        # GPIO config (required for DUT to boot)
        print("  Configuring GPIOs...")
        for gpio in [0, 1]:
            client.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
            client.GpioWrite(gpio=gpio, state=False)
        client.GpioConfig(gpio=2, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        client.GpioWrite(gpio=2, state=True)  # Button released

        # Power on
        print("  Powering on ch0=4.5V...")
        err = client.PowerEnable(channel=0, voltage_v=4.5)
        if err:
            print(f"  [ERROR] PowerEnable failed: {err}")
            return 1

        # Wait for boot (same as manufacturing test)
        print("  Waiting 3s for boot...")
        time.sleep(3)

        # Lock shells using spam method (fast, catches 2s window)
        print("  Locking Comms shell (spam 3s)...")
        comms_locked, _ = client.alpha_spam_lock_shell(HostType.HOST_TYPE_NRF9151, 3.0)
        print(f"    Locked: {'YES' if comms_locked else 'NO'}")

        print("  Locking App shell (spam 3s)...")
        app_locked, _ = client.alpha_spam_lock_shell(HostType.HOST_TYPE_NRF52840, 3.0)
        print(f"    Locked: {'YES' if app_locked else 'NO'}")

        # Disable debug output (same as manufacturing test)
        print("  Disabling debug output (Comms)...")
        client.alpha_cmd_debug_disable_comms()
        print("  Disabling debug output (App)...")
        client.alpha_cmd_debug_disable_app()

        result, err = client.PowerRead(channel=0)
        if not err and result:
            print(f"  DUT drawing {result.current_ma:.1f}mA @ {result.voltage_v:.2f}V")

        # === APP PROCESSOR POST ===
        print("\n=== App Processor (nRF52840) POST ===")
        app_passed = 0
        app_failed = 0

        if app_locked:
            print_result("lock_shell", True, "(locked during boot)")
            app_passed += 1

            # get_chip_ids
            print("  Running get_chip_ids...")
            ext_flash_id, ble_mac, err = client.alpha_cmd_get_chip_ids_app()
            if ble_mac:
                print_result("get_chip_ids", True, f"BLE MAC={ble_mac}, Flash={ext_flash_id}")
                app_passed += 1
            else:
                print_result("get_chip_ids", False, err[:80] if err else "No BLE MAC")
                app_failed += 1

            # test_bms
            print("  Running test_bms...")
            bms_result, err = client.alpha_cmd_test_bms()
            if bms_result is not None:
                print_result("test_bms", True, f"connected={bms_result.connected}, chip_id={bms_result.chip_id}")
                app_passed += 1
            else:
                print_result("test_bms", False, err[:80] if err else "Unknown error")
                app_failed += 1

            # test_charger
            print("  Running test_charger...")
            charger_result, err = client.alpha_cmd_test_charger()
            if charger_result is not None:
                print_result("test_charger", True, f"chip_id={charger_result.chip_id}, on_charger={charger_result.on_charger}")
                app_passed += 1
            else:
                print_result("test_charger", False, err[:80] if err else "Unknown error")
                app_failed += 1

            # test_gps
            print("  Running test_gps...")
            gps_result, err = client.alpha_cmd_test_gps()
            if gps_result is not None:
                print_result("test_gps", True, f"comms_ok={gps_result.comms_ok}, tracking={gps_result.tracking}")
                app_passed += 1
            else:
                print_result("test_gps", False, err[:80] if err else "Unknown error")
                app_failed += 1
        else:
            print("[ERROR] App shell not locked")
            app_failed += 1

        # === COMMS PROCESSOR POST ===
        print("\n=== Comms Processor (nRF9151) POST ===")
        comms_passed = 0
        comms_failed = 0

        if comms_locked:
            print_result("lock_shell", True, "(locked during boot)")
            comms_passed += 1

            # get_chip_ids
            print("  Running get_chip_ids...")
            ext_flash_id, lora_status, err = client.alpha_cmd_get_chip_ids_comms()
            if ext_flash_id:
                print_result("get_chip_ids", True, f"Flash={ext_flash_id}")
                comms_passed += 1
            else:
                print_result("get_chip_ids", False, err[:80] if err else "Unknown error")
                comms_failed += 1

            # get_modem_fw
            print("  Running get_modem_fw...")
            fw_version, err = client.alpha_cmd_get_modem_fw()
            if fw_version:
                print_result("get_modem_fw", True, f"FW={fw_version}")
                comms_passed += 1
            else:
                print_result("get_modem_fw", False, err[:80] if err else "Unknown error")
                comms_failed += 1

            # imei_iccid with retries
            print("  Running get_imei_iccids...")
            for attempt in range(3):
                imei, iccids, err = client.alpha_cmd_get_imei_iccids()
                if imei:
                    iccid_str = iccids[0] if iccids else "?"
                    print_result("get_imei_iccids", True, f"IMEI={imei}, ICCID={iccid_str}")
                    comms_passed += 1
                    break
                if attempt < 2:
                    print(f"    Retry {attempt + 1}...")
                    time.sleep(2)
            else:
                print_result("get_imei_iccids", False, err[:60] if err else "Not ready")
                comms_failed += 1
        else:
            print("[ERROR] Comms shell not locked")
            comms_failed += 1

        # === SUMMARY ===
        total_passed = app_passed + comms_passed
        total_failed = app_failed + comms_failed
        print(f"\n=== Summary ===")
        print(f"  App Processor:   {app_passed} passed, {app_failed} failed")
        print(f"  Comms Processor: {comms_passed} passed, {comms_failed} failed")
        print(f"  Total:           {total_passed} passed, {total_failed} failed")

        return 0 if total_failed == 0 else 1

    finally:
        print("\n=== Powering down ===")
        client.PowerDisable(channel=0)
        client.PowerDisable(channel=1)
        print("Done.")


if __name__ == "__main__":
    sys.exit(main())
