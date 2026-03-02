#!/usr/bin/env python3
"""M10 Verification: Test all V2 RPCs against a live MTIB server.

Usage:
    python3 apps/edge/mtib-server/tests/verify_v2_rpcs.py <host:port> [--rev REV1.1|REV1.2]

Tests:
    1. HealthCheck (legacy) — backward compat
    2. HealthCheckExtended — hw_revision + capabilities
    3. PowerRead (DUT) — INA219 channel 0
    4. PowerRead (CHARGER) — INA219 channel 1
    5. PowerMeasure (DUT, 1s) — stats
    6. PowerStream (DUT, 2s sample) — streaming
    7. AdcReadAll — all 8 channels
    8. AdcStream (1s sample) — streaming
    9. GpioRead (GPIO 0) — existing RPC
    10. GetSnapshot — aggregated state
    11. GpioWatch (GPIO 0, 1s sample) — streaming edge detection
"""

import sys
import time

sys.path.insert(0, "libs/protocols")
sys.path.insert(0, "libs/python")

import grpc
from protocols.mtib.mtib_pb2 import (
    Empty,
    AdcReadRequest,
    GpioReadRequest,
    PowerChannel,
    PowerEnableRequest,
    PowerDisableRequest,
    PowerReadRequest,
    PowerMeasureRequest,
    PowerStreamRequest,
    GpioEdge,
    GpioWatchRequest,
    AdcStreamRequest,
)
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub


def test(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    return passed


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <host:port> [--rev REV1.1|REV1.2]")
        sys.exit(1)

    addr = sys.argv[1]
    expected_rev = None
    if "--rev" in sys.argv:
        idx = sys.argv.index("--rev")
        if idx + 1 < len(sys.argv):
            expected_rev = sys.argv[idx + 1]

    print(f"Connecting to {addr}...")
    channel = grpc.insecure_channel(addr)
    stub = MtibV1Stub(channel)

    passed = 0
    failed = 0
    total = 0

    def run(name, func):
        nonlocal passed, failed, total
        total += 1
        try:
            if func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            test(name, False, f"EXCEPTION: {e}")
            failed += 1

    # --- 1. HealthCheck (legacy) ---
    def t_health_legacy():
        resp = stub.HealthCheck(Empty(), timeout=5)
        return test("HealthCheck (legacy)", resp.ready, f"ready={resp.ready}")

    # --- 2. HealthCheckExtended ---
    def t_health_extended():
        resp = stub.HealthCheck(Empty(), timeout=5)
        hw = resp.hw_revision
        caps = list(resp.capabilities)
        ok = bool(hw) and len(caps) > 0
        if expected_rev:
            ok = ok and (hw == expected_rev)
        return test("HealthCheckExtended", ok, f"hw_revision={hw}, capabilities={caps}")

    # --- 3. PowerRead (DUT) ---
    def t_power_read_dut():
        resp = stub.PowerRead(PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_DUT), timeout=5)
        ok = resp.success
        return test("PowerRead (DUT)", ok, f"V={resp.voltage_v:.3f}, mA={resp.current_ma:.1f}, mW={resp.power_mw:.1f}")

    # --- 4. PowerRead (CHARGER) ---
    def t_power_read_chg():
        resp = stub.PowerRead(PowerReadRequest(channel=PowerChannel.POWER_CHANNEL_CHARGER), timeout=5)
        ok = resp.success
        return test("PowerRead (CHARGER)", ok, f"V={resp.voltage_v:.3f}, mA={resp.current_ma:.1f}")

    # --- 5. PowerMeasure ---
    def t_power_measure():
        resp = stub.PowerMeasure(PowerMeasureRequest(channel=PowerChannel.POWER_CHANNEL_DUT, duration_s=1.0), timeout=10)
        ok = resp.success and resp.sample_count > 0
        return test("PowerMeasure (DUT, 1s)", ok, f"avg={resp.average_ma:.1f}mA, samples={resp.sample_count}")

    # --- 6. PowerStream ---
    def t_power_stream():
        count = 0
        try:
            stream = stub.PowerStream(PowerStreamRequest(channel=PowerChannel.POWER_CHANNEL_DUT))
            start = time.time()
            for resp in stream:
                count += len(resp.samples)
                if time.time() - start > 2.0:
                    stream.cancel()
                    break
        except grpc.RpcError:
            pass  # Expected when we cancel
        return test("PowerStream (DUT, 2s)", count > 0, f"received {count} samples")

    # --- 7. AdcReadAll ---
    def t_adc_read_all():
        resp = stub.AdcReadAll(Empty(), timeout=5)
        ok = resp.success and len(resp.voltages_v) == 8
        voltages = [f"{v:.2f}" for v in resp.voltages_v] if resp.success else []
        return test("AdcReadAll", ok, f"voltages={voltages}")

    # --- 8. AdcStream ---
    def t_adc_stream():
        count = 0
        try:
            stream = stub.AdcStream(AdcStreamRequest(channels=[0, 1, 2, 3], interval_ms=100))
            start = time.time()
            for resp in stream:
                count += len(resp.samples)
                if time.time() - start > 1.0:
                    stream.cancel()
                    break
        except grpc.RpcError:
            pass
        return test("AdcStream (ch0-3, 1s)", count > 0, f"received {count} samples")

    # --- 9. GpioRead ---
    def t_gpio_read():
        resp = stub.GpioRead(GpioReadRequest(gpio=0), timeout=5)
        ok = resp.success
        return test("GpioRead (GPIO 0)", ok, f"state={resp.state}")

    # --- 10. GetSnapshot ---
    def t_get_snapshot():
        resp = stub.GetSnapshot(Empty(), timeout=5)
        ok = resp.success
        detail = f"ts={resp.timestamp_ms}, hw={resp.hw_revision}, power={len(resp.power)}, gpio={len(resp.gpio)}, adc={len(resp.adc)}"
        return test("GetSnapshot", ok, detail)

    # --- 11. GpioWatch ---
    def t_gpio_watch():
        # GpioWatch may not produce events if no edges happen, so we just test it doesn't crash
        ok = True
        try:
            stream = stub.GpioWatch(GpioWatchRequest(gpio=0, edge=GpioEdge.GPIO_EDGE_BOTH))
            start = time.time()
            event_count = 0
            for event in stream:
                event_count += 1
                if time.time() - start > 1.0:
                    stream.cancel()
                    break
            # No events is OK — just means no edges happened
            return test("GpioWatch (GPIO 0, 1s)", True, f"events={event_count} (0 is OK if no edges)")
        except grpc.RpcError as e:
            if "CANCELLED" in str(e):
                return test("GpioWatch (GPIO 0, 1s)", True, "stream opened OK (cancelled after timeout)")
            return test("GpioWatch (GPIO 0, 1s)", False, str(e))

    # Run all tests
    print(f"\n--- M10 Verification: {addr} ---\n")

    run("HealthCheck (legacy)", t_health_legacy)
    run("HealthCheckExtended", t_health_extended)
    run("PowerRead (DUT)", t_power_read_dut)
    run("PowerRead (CHARGER)", t_power_read_chg)
    run("PowerMeasure", t_power_measure)
    run("PowerStream", t_power_stream)
    run("AdcReadAll", t_adc_read_all)
    run("AdcStream", t_adc_stream)
    run("GpioRead", t_gpio_read)
    run("GetSnapshot", t_get_snapshot)
    run("GpioWatch", t_gpio_watch)

    print(f"\n--- Results: {passed}/{total} passed, {failed} failed ---")

    channel.close()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
