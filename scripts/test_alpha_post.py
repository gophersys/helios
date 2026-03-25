#!/usr/bin/env python3
"""Alpha Manufacturing POST Test — concurrent lock strategy.

Opens BOTH UART streams before power-on to capture boot output, locks
both shells concurrently (required: MTIB byte-by-byte latency means
sequential locking misses the ~7s activation window), silences output,
then runs commands.
"""

import sys
import time
import threading

sys.path.insert(0, "libs/python")
sys.path.insert(0, "libs/protocols")
sys.path.insert(0, "libs")

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from corekinect.shells.alpha_app import AlphaAppShell
from corekinect.shells.comms_coproc import CommsCoprocShell


MTIB_HOST = "10.4.45.33"
MTIB_PORT = 50053


def print_result(name: str, passed: bool, detail: str = ""):
    status = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    print(f"  {status} {name}" + (f": {detail}" if detail else ""))


def main():
    t0 = time.time()
    print("=== Alpha Manufacturing POST Test ===")
    print(f"MTIB: {MTIB_HOST}:{MTIB_PORT}")
    print(f"Strategy: boot, concurrent lock, silence+clear, commands")

    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_HOST, port=MTIB_PORT))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        print(f"[ERROR] Connection failed: {err}")
        return 1
    print("Connected to MTIB")

    app = AlphaAppShell(client)
    comms = CommsCoprocShell(client)

    try:
        # ============================================================
        # PHASE 0: POWER CYCLE + BOOT + CONCURRENT LOCK
        # ============================================================
        print(f"\n--- Power Cycle DUT [{time.time()-t0:.0f}s] ---")
        client.PowerDisable(channel=0)
        client.PowerDisable(channel=1)
        time.sleep(3)

        for gpio in [0, 1]:
            client.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
            client.GpioWrite(gpio=gpio, state=False)
        client.GpioConfig(gpio=2, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        client.GpioWrite(gpio=2, state=True)

        print("  Opening UART streams...")
        app.start()
        comms.start()

        print("  Powering on ch0=4.5V...")
        err = client.PowerEnable(channel=0, voltage_v=4.5)
        if err:
            print(f"  [ERROR] PowerEnable failed: {err}")
            return 1

        print("  Waiting 1s for boot...")
        time.sleep(1)

        # Lock BOTH shells concurrently — required because MTIB
        # byte-by-byte UART latency makes sequential locking too
        # slow to fit within the ~7s mfg shell activation window.
        print(f"\n--- Locking Shells (concurrent) [{time.time()-t0:.0f}s] ---")
        lock_results = {}

        def _lock(shell, name):
            lock_results[name] = shell.lock(timeout_s=120)

        t_app = threading.Thread(target=_lock, args=(app, "APP"))
        t_comms = threading.Thread(target=_lock, args=(comms, "COMMS"))
        t_app.start()
        t_comms.start()
        t_app.join()
        t_comms.join()

        app_locked = lock_results.get("APP", False)
        comms_locked = lock_results.get("COMMS", False)
        print(f"  APP: {'locked' if app_locked else 'FAILED'}")
        print(f"  COMMS: {'locked' if comms_locked else 'FAILED'}")

        result, err = client.PowerRead(channel=0)
        if not err and result:
            print(f"  DUT: {result.current_ma:.1f}mA @ {result.voltage_v:.2f}V")

        # ============================================================
        # SILENCE + DRAIN BACKLOG
        # ============================================================
        if app_locked:
            app._cmd._stream.write(b"\rdebug_enable 0\r")
        if comms_locked:
            comms._cmd._stream.write(b"\rdebug_enable 0\r")

        # Drain UART TX backlog. MTIB delivers ~400 B/s byte-by-byte;
        # the APP processor queues 10-15 KB of debug output during boot.
        # Keep clearing until rate drops below 100 B/s (backlog drained).
        print(f"  Draining UART backlog [{time.time()-t0:.0f}s]...")
        for _ in range(60):  # max 30s
            app._cmd._stream.clear()
            comms._cmd._stream.clear()
            time.sleep(0.5)
            app_bytes = len(app._cmd._stream._buffer)
            if app_bytes < 50:  # <100 B/s = backlog drained
                break
        app._cmd._stream.clear()
        comms._cmd._stream.clear()
        print(f"  Backlog drained [{time.time()-t0:.0f}s]")

        # ============================================================
        # PHASE 1: APP commands
        # ============================================================
        app_passed = 0
        app_failed = 0

        print(f"\n--- Phase 1: APP Commands [{time.time()-t0:.0f}s] ---")

        if app_locked:
            print_result("lock_shell", True, "(locked during boot)")
            app_passed += 1

            t1 = time.time()
            ids, err = app.get_chip_ids()
            dt = time.time() - t1
            if ids.ble_mac:
                print_result("get_chip_ids", True, f"BLE MAC={ids.ble_mac}, Flash={ids.ext_flash_id} ({dt:.1f}s)")
                app_passed += 1
            else:
                print_result("get_chip_ids", False, (err or "No BLE MAC")[:200])
                app_failed += 1

            t1 = time.time()
            bms, err = app.test_bms()
            dt = time.time() - t1
            if err is None:
                print_result("test_bms", True, f"connected={bms.connected}, chip_id={bms.chip_id} ({dt:.1f}s)")
                app_passed += 1
            else:
                print_result("test_bms", False, err[:200])
                app_failed += 1

            t1 = time.time()
            charger, err = app.test_charger()
            dt = time.time() - t1
            if err is None:
                print_result("test_charger", True, f"chip_id={charger.chip_id}, on_charger={charger.on_charger} ({dt:.1f}s)")
                app_passed += 1
            else:
                print_result("test_charger", False, err[:200])
                app_failed += 1

            t1 = time.time()
            gps, err = app.test_gps()
            dt = time.time() - t1
            if err is None:
                print_result("test_gps", True, f"comms_ok={gps.comms_ok}, tracking={gps.tracking} ({dt:.1f}s)")
                app_passed += 1
            else:
                print_result("test_gps", False, err[:200])
                app_failed += 1
        else:
            print("[ERROR] App shell not locked")
            app_failed += 5

        # ============================================================
        # PHASE 2: COMMS commands
        # ============================================================
        comms_passed = 0
        comms_failed = 0

        print(f"\n--- Phase 2: COMMS Commands [{time.time()-t0:.0f}s] ---")

        if comms_locked:
            print_result("lock_shell", True, "(locked during boot)")
            comms_passed += 1

            t1 = time.time()
            ids, err = comms.get_chip_ids()
            dt = time.time() - t1
            if ids.ext_flash_id:
                print_result("get_chip_ids", True, f"Flash={ids.ext_flash_id} ({dt:.1f}s)")
                comms_passed += 1
            else:
                print_result("get_chip_ids", False, (err or "Unknown error")[:200])
                comms_failed += 1

            t1 = time.time()
            fw, err = comms.get_modem_fw()
            dt = time.time() - t1
            if fw.version:
                print_result("get_modem_fw", True, f"FW={fw.version} ({dt:.1f}s)")
                comms_passed += 1
            else:
                print_result("get_modem_fw", False, (err or "Unknown error")[:200])
                comms_failed += 1

            t1 = time.time()
            sim, err = comms.get_sim_info()
            dt = time.time() - t1
            if sim.imei:
                iccid_str = sim.iccids[0] if sim.iccids else "?"
                print_result("get_sim_info", True, f"IMEI={sim.imei}, ICCID={iccid_str} ({dt:.1f}s)")
                comms_passed += 1
            else:
                print_result("get_sim_info", False, (err or "Not ready")[:200])
                comms_failed += 1
        else:
            print("[ERROR] Comms shell not locked")
            comms_failed += 4

        # === SUMMARY ===
        total_passed = app_passed + comms_passed
        total_failed = app_failed + comms_failed
        elapsed = time.time() - t0
        print(f"\n=== Summary ({elapsed:.0f}s) ===")
        print(f"  App Processor:   {app_passed} passed, {app_failed} failed")
        print(f"  Comms Processor: {comms_passed} passed, {comms_failed} failed")
        print(f"  Total:           {total_passed} passed, {total_failed} failed")

        return 0 if total_failed == 0 else 1

    finally:
        print("\n--- Cleanup ---")
        app.stop()
        comms.stop()
        client.PowerDisable(channel=0)
        client.PowerDisable(channel=1)
        print("Done.")


if __name__ == "__main__":
    sys.exit(main())
