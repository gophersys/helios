#!/usr/bin/env python3
"""Capture full nRF52840 APP boot log by opening UART BEFORE power-on.

The manufacturing shell activates ~0.4s after boot and auto-deactivates ~7.4s.
We MUST have UART streams open before power to catch everything.
"""

import sys
import time

sys.path.insert(0, "libs/python")
sys.path.insert(0, "libs/protocols")
sys.path.insert(0, "libs")

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from corekinect.test.validation.uart_demuxer import UartDemuxer

MTIB_HOST = "10.4.45.33"
MTIB_PORT = 50053
CAPTURE_DURATION_S = 30  # Capture for 30s to get full boot + shell window


def main():
    print("=== nRF52840 APP Full Boot Capture ===")
    print(f"MTIB: {MTIB_HOST}:{MTIB_PORT}")

    # Connect
    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_HOST, port=MTIB_PORT))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        print(f"[ERROR] Connection failed: {err}")
        return 1
    print("Connected to MTIB")

    # Create UartDemuxer for both targets
    demuxer = UartDemuxer(client, log_dir="/tmp/uart_boot_capture")

    try:
        # === STEP 1: Power down first ===
        print("\n[1] Powering down DUT...")
        client.PowerDisable(channel=0)
        client.PowerDisable(channel=1)
        time.sleep(2)
        print("    Power off, waiting 2s for discharge")

        # === STEP 2: Configure GPIOs (required for boot) ===
        print("[2] Configuring GPIOs...")
        for gpio in [0, 1]:
            client.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
            client.GpioWrite(gpio=gpio, state=False)
        # Button released
        client.GpioConfig(gpio=2, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        client.GpioWrite(gpio=2, state=True)

        # === STEP 3: START UART STREAMS *BEFORE* POWER ON ===
        print("[3] Starting UART capture (BEFORE power-on)...")
        demuxer.start()
        time.sleep(0.5)  # Let streams establish
        print("    Both APP + COMMS streams active")

        # === STEP 4: Power on ===
        print("[4] Powering on ch0=4.5V...")
        t_power_on = time.monotonic()
        err = client.PowerEnable(channel=0, voltage_v=4.5)
        if err:
            print(f"    [ERROR] PowerEnable failed: {err}")
            return 1

        # === STEP 5: Spam lock_shell on BOTH targets immediately ===
        print("[5] Spamming lock_shell on both APP + COMMS...")
        for i in range(10):
            demuxer.send("app", "lock_shell")
            demuxer.send("comms", "lock_shell")
            time.sleep(0.5)
        print(f"    Sent 10 lock_shell commands to each target over 5s")

        # === STEP 6: Try debug_enable to get more output ===
        print("[6] Sending debug_enable 1 to APP...")
        demuxer.send("app", "debug_enable 1")
        time.sleep(0.5)
        demuxer.send("app", "help")
        time.sleep(0.5)

        # === STEP 7: Wait and collect ===
        elapsed = time.monotonic() - t_power_on
        remaining = CAPTURE_DURATION_S - elapsed
        if remaining > 0:
            print(f"[7] Waiting {remaining:.0f}s more for UART data to arrive...")
            # Print progress every 5s
            wait_start = time.monotonic()
            while time.monotonic() - wait_start < remaining:
                time.sleep(5)
                app_lines = demuxer.get_logs("app")
                comms_lines = demuxer.get_logs("comms")
                t = time.monotonic() - t_power_on
                print(f"    t={t:.0f}s: APP={len(app_lines)} lines, COMMS={len(comms_lines)} lines")

        # === STEP 8: Print all captured output ===
        print(f"\n{'='*60}")
        print("=== APP (nRF52840) FULL BOOT LOG ===")
        print(f"{'='*60}")
        app_logs = demuxer.get_logs("app")
        if app_logs:
            for line in app_logs:
                print(f"  {line}")
        else:
            print("  (NO OUTPUT CAPTURED)")

        print(f"\n{'='*60}")
        print("=== COMMS (nRF9151) FULL BOOT LOG ===")
        print(f"{'='*60}")
        comms_logs = demuxer.get_logs("comms")
        if comms_logs:
            for line in comms_logs:
                print(f"  {line}")
        else:
            print("  (NO OUTPUT CAPTURED)")

        # === Timeline view ===
        print(f"\n{'='*60}")
        print("=== MERGED TIMELINE ===")
        print(f"{'='*60}")
        timeline = demuxer.get_timeline()
        if timeline:
            t0 = timeline[0][0]
            for ts, target, line in timeline:
                print(f"  [{ts - t0:8.3f}s] [{target:5s}] {line}")
        else:
            print("  (NO DATA)")

        print(f"\nTotal: APP={len(app_logs)} lines, COMMS={len(comms_logs)} lines")
        print(f"Logs saved to /tmp/uart_boot_capture/")

        return 0

    finally:
        print("\n=== Cleanup ===")
        demuxer.stop()
        client.PowerDisable(channel=0)
        client.PowerDisable(channel=1)
        print("Power off, done.")


if __name__ == "__main__":
    sys.exit(main())
