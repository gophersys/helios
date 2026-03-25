#!/usr/bin/env python3
"""Quick UART test to verify streaming works."""

import sys
import time

sys.path.insert(0, "libs/python")
sys.path.insert(0, "libs/protocols")
sys.path.insert(0, "libs")

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig

MTIB_HOST = "10.4.45.33"
MTIB_PORT = 50053


def test_uart_stream():
    """Open a stream, send a command, and see what comes back."""
    cfg = MtibV1Client.Config(net=NetConfig(addr=MTIB_HOST, port=MTIB_PORT))
    client = MtibV1Client(cfg)
    err = client.connect()
    if err:
        print(f"Connect failed: {err}")
        return

    print("Connected to MTIB")

    # Power cycle the DUT first
    print("\n=== Power Setup ===")
    print("Disabling power...")
    client.PowerDisable(channel=0)
    client.PowerDisable(channel=1)
    time.sleep(2)

    print("Configuring GPIOs (required for DUT boot)...")
    for gpio in [0, 1]:
        client.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        client.GpioWrite(gpio=gpio, state=False)
    client.GpioConfig(gpio=2, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
    client.GpioWrite(gpio=2, state=True)  # Button released

    print("Enabling power ch0=4.5V...")
    err = client.PowerEnable(channel=0, voltage_v=4.5)
    if err:
        print(f"PowerEnable failed: {err}")
        return

    # Wait for boot
    print("Waiting 5s for boot...")
    time.sleep(5)

    result, err = client.PowerRead(channel=0)
    if result:
        print(f"DUT: {result.current_ma:.1f}mA @ {result.voltage_v:.2f}V")
    else:
        print(f"PowerRead error: {err}")

    # Now test UART streaming
    print("\n=== UART Stream Test (App processor nRF52840) ===")
    target = HostType.HOST_TYPE_NRF52840

    chunks = []
    chunk_count = 0
    start_time = time.time()

    def req_gen():
        nonlocal chunk_count
        # First: spam lock_shell for 3 seconds
        print("  Spamming lock_shell...")
        lock_start = time.time()
        while time.time() - lock_start < 3:
            yield UartStreamRequest(target=target, data=b"\rlock_shell\r")
            time.sleep(0.1)

        # Now send a test command
        print("  Sending get_chip_ids...")
        yield UartStreamRequest(target=target, data=b"\rget_chip_ids\r")

        # Pump for 5 seconds
        print("  Pumping for 5s...")
        pump_start = time.time()
        while time.time() - pump_start < 5:
            yield UartStreamRequest(target=target, data=b"")
            time.sleep(0.05)

    try:
        for resp in client.UartStream(target, req_gen()):
            if resp.data:
                chunks.append(resp.data)
                chunk_count += 1
                print(f"    Chunk {chunk_count} ({len(resp.data)}b): {resp.data[:60]}...")
    except Exception as e:
        print(f"Stream error: {e}")

    elapsed = time.time() - start_time
    total_bytes = sum(len(c) for c in chunks)
    print(f"\n=== Results ===")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Chunks: {chunk_count}")
    print(f"Total bytes: {total_bytes}")

    if chunks:
        full = b"".join(chunks).decode("utf-8", errors="replace")
        print(f"\nFull output ({len(full)} chars):")
        print(full[:2000])  # Limit output
    else:
        print("\nNo data received!")

    # Cleanup
    print("\n=== Power Down ===")
    client.PowerDisable(channel=0)
    client.PowerDisable(channel=1)
    print("Done")


if __name__ == "__main__":
    test_uart_stream()
