#!/usr/bin/env python3
"""UART concurrent stream benchmark — measures data rates on both targets simultaneously.

Tests:
  1. Single stream (APP only) — baseline throughput
  2. Single stream (COMMS only) — baseline throughput
  3. Concurrent streams (APP + COMMS) — concurrent handling
  4. Sequential after concurrent — verify no residual issues

For each test, powers on the DUT, captures UART boot output for 15s,
and reports bytes received per stream.
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
from corekinect.shells.base import BufferedUartStream
from protocols.mtib.mtib_pb2 import HostType


MTIB_HOST = "10.4.45.33"
MTIB_PORT = 50053
CAPTURE_SECONDS = 15


def power_cycle(client, settle_s=3.0):
    """Power cycle DUT with GPIO setup."""
    client.PowerDisable(channel=0)
    client.PowerDisable(channel=1)
    time.sleep(settle_s)
    for gpio in [0, 1]:
        client.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        client.GpioWrite(gpio=gpio, state=False)
    client.PowerEnable(channel=0, voltage_v=4.5)


def measure_stream(client, targets, duration_s, label):
    """Open streams on targets, power cycle, capture for duration_s, report."""
    streams = {}
    for name, target in targets.items():
        s = BufferedUartStream(client, target, label=name)
        streams[name] = s

    # Open streams BEFORE power-on
    for s in streams.values():
        s.start()
    time.sleep(0.2)

    # Power cycle
    power_cycle(client)
    t0 = time.time()

    # Sample data rates every second
    samples = {name: [] for name in streams}
    while (time.time() - t0) < duration_s:
        time.sleep(1.0)
        elapsed = time.time() - t0
        for name, s in streams.items():
            samples[name].append((elapsed, s.rx_bytes, s.is_alive))

    # Final readings
    results = {}
    for name, s in streams.items():
        results[name] = {
            "rx_bytes": s.rx_bytes,
            "alive": s.is_alive,
            "error": s.last_error,
            "samples": samples[name],
        }
        s.stop()

    # Power off
    client.PowerDisable(channel=0)
    client.PowerDisable(channel=1)
    time.sleep(2)

    return results


def print_table(label, results):
    """Print results table for a test."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  {'Stream':<10} {'Bytes':>8} {'Alive':>8} {'B/s':>8}  Error")
    print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8}  {'-'*20}")
    for name, r in results.items():
        bps = r["rx_bytes"] / CAPTURE_SECONDS if r["rx_bytes"] > 0 else 0
        err = r["error"] or ""
        print(f"  {name:<10} {r['rx_bytes']:>8} {'yes' if r['alive'] else 'NO':>8} {bps:>8.1f}  {err}")

    # Per-second breakdown
    print(f"\n  Per-second breakdown:")
    print(f"  {'Time':>6}", end="")
    for name in results:
        print(f"  {name:>10}", end="")
    print()
    # Get max sample count
    max_len = max(len(r["samples"]) for r in results.values())
    prev = {name: 0 for name in results}
    for i in range(max_len):
        t_str = ""
        vals = {}
        for name, r in results.items():
            if i < len(r["samples"]):
                elapsed, total, alive = r["samples"][i]
                delta = total - prev[name]
                prev[name] = total
                t_str = f"{elapsed:>5.0f}s"
                vals[name] = f"{delta:>8}B {'*' if not alive else ''}"
            else:
                vals[name] = f"{'?':>8}"
        print(f"  {t_str}", end="")
        for name in results:
            print(f"  {vals.get(name, '?'):>10}", end="")
        print()


def main():
    print("=== UART Concurrent Stream Benchmark ===")
    print(f"MTIB: {MTIB_HOST}:{MTIB_PORT}")
    print(f"Capture duration: {CAPTURE_SECONDS}s per test")

    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_HOST, port=MTIB_PORT))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        print(f"[ERROR] Connection failed: {err}")
        return 1
    print("Connected.\n")

    all_results = {}

    # Test 1: APP only
    print(">>> Test 1: APP stream only...")
    r = measure_stream(client, {"APP": HostType.HOST_TYPE_NRF52840}, CAPTURE_SECONDS, "APP only")
    print_table("Test 1: APP only", r)
    all_results["APP_only"] = r

    # Test 2: COMMS only
    print("\n>>> Test 2: COMMS stream only...")
    r = measure_stream(client, {"COMMS": HostType.HOST_TYPE_NRF9151}, CAPTURE_SECONDS, "COMMS only")
    print_table("Test 2: COMMS only", r)
    all_results["COMMS_only"] = r

    # Test 3: Concurrent (the critical test)
    print("\n>>> Test 3: APP + COMMS concurrent...")
    r = measure_stream(client, {
        "APP": HostType.HOST_TYPE_NRF52840,
        "COMMS": HostType.HOST_TYPE_NRF9151,
    }, CAPTURE_SECONDS, "Concurrent")
    print_table("Test 3: APP + COMMS concurrent", r)
    all_results["concurrent"] = r

    # Test 4: Sequential after concurrent (verify no residual issues)
    print("\n>>> Test 4: APP only (post-concurrent)...")
    r = measure_stream(client, {"APP": HostType.HOST_TYPE_NRF52840}, CAPTURE_SECONDS, "APP post-concurrent")
    print_table("Test 4: APP only (post-concurrent)", r)
    all_results["APP_post"] = r

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Test':<25} {'APP bytes':>12} {'COMMS bytes':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12}")
    for test_name, r in all_results.items():
        app_b = r.get("APP", {}).get("rx_bytes", "-")
        comms_b = r.get("COMMS", {}).get("rx_bytes", "-")
        print(f"  {test_name:<25} {str(app_b):>12} {str(comms_b):>12}")

    # Verdict
    concurrent = all_results.get("concurrent", {})
    app_conc = concurrent.get("APP", {}).get("rx_bytes", 0)
    comms_conc = concurrent.get("COMMS", {}).get("rx_bytes", 0)
    if app_conc > 0 and comms_conc > 0:
        print(f"\n  VERDICT: PASS — both streams received data concurrently")
        return 0
    else:
        print(f"\n  VERDICT: FAIL — concurrent stream starvation detected")
        if comms_conc == 0:
            print(f"           COMMS received 0 bytes during concurrent test")
        if app_conc == 0:
            print(f"           APP received 0 bytes during concurrent test")
        return 1


if __name__ == "__main__":
    sys.exit(main())
