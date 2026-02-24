#!/usr/bin/env python3
"""Example usage of MTIB V2 Client analyzer methods.

This demonstrates the high-level analyzer API for logic analyzer operations.
"""

from corekinect.mtib_client.v2 import MtibV2Client, ClientConfig, NetConfig


def example_basic_capture():
    """Example: Basic logic analyzer capture."""
    # Connect to MTIB server
    config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
    client = MtibV2Client(config)

    error = client.connect()
    if error:
        print(f"Connection failed: {error}")
        return

    print("Connected to MTIB V2 server")

    # Start a capture on channels 0-3
    err, capture_id = client.analyzer_capture_start(
        channels=[0, 1, 2, 3],
        sample_rate_hz=10_000_000,  # 10 MHz
        duration_s=5.0,
    )

    if err:
        print(f"Failed to start capture: {err}")
        client.disconnect()
        return

    print(f"Capture started: {capture_id}")

    # Poll status until complete
    import time
    while True:
        err, status = client.analyzer_capture_status(capture_id)
        if err:
            print(f"Status check failed: {err}")
            break

        status_code = status["status"]
        progress = status["progress"]

        if status_code == 0:
            print(f"Waiting for trigger... {progress:.1%}")
        elif status_code == 1:
            print(f"Capturing... {progress:.1%}")
        elif status_code == 2:
            print("Capture complete!")
            break
        elif status_code == 3:
            print("Capture error!")
            break

        time.sleep(0.5)

    # Export to CSV
    err, file_path = client.analyzer_export(capture_id, format="csv")
    if err:
        print(f"Export failed: {err}")
    else:
        print(f"Exported to: {file_path}")

    client.disconnect()


def example_i2c_decode():
    """Example: Capture and decode I2C traffic."""
    config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
    client = MtibV2Client(config)

    error = client.connect()
    if error:
        print(f"Connection failed: {error}")
        return

    # Capture I2C signals on channels 0 (SDA) and 1 (SCL)
    err, capture_id = client.analyzer_capture_start(
        channels=[0, 1],
        sample_rate_hz=10_000_000,
        duration_s=2.0,
    )

    if err:
        print(f"Failed to start capture: {err}")
        client.disconnect()
        return

    print(f"Capturing I2C signals: {capture_id}")

    # Wait for capture to complete
    import time
    time.sleep(2.5)

    # Add I2C decoder
    err, decoder_id = client.analyzer_add_i2c_decoder(
        capture_id=capture_id,
        sda_channel=0,
        scl_channel=1,
    )

    if err:
        print(f"Failed to add I2C decoder: {err}")
        client.disconnect()
        return

    print(f"I2C decoder added: {decoder_id}")

    # Get decoded data
    err, decoded = client.analyzer_get_decoded_data(capture_id, decoder_id)
    if err:
        print(f"Failed to get decoded data: {err}")
    else:
        print(f"Found {len(decoded)} I2C transactions")
        for item in decoded:
            if item.HasField("i2c"):
                i2c = item.i2c
                rw = "R" if i2c.read else "W"
                print(f"  {rw} 0x{i2c.address:02x}: {i2c.data.hex()}")

    client.disconnect()


def example_spi_decode():
    """Example: Capture and decode SPI traffic."""
    config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
    client = MtibV2Client(config)

    error = client.connect()
    if error:
        print(f"Connection failed: {error}")
        return

    # Capture SPI signals on channels 0-3 (CLK, MOSI, MISO, CS)
    err, capture_id = client.analyzer_capture_start(
        channels=[0, 1, 2, 3],
        sample_rate_hz=20_000_000,  # 20 MHz
        duration_s=1.0,
    )

    if err:
        print(f"Failed to start capture: {err}")
        client.disconnect()
        return

    print(f"Capturing SPI signals: {capture_id}")

    # Wait for capture to complete
    import time
    time.sleep(1.5)

    # Add SPI decoder
    err, decoder_id = client.analyzer_add_spi_decoder(
        capture_id=capture_id,
        clk_channel=0,
        mosi_channel=1,
        miso_channel=2,
        cs_channel=3,
        cpol=False,
        cpha=False,
        bits_per_word=8,
        msb_first=True,
    )

    if err:
        print(f"Failed to add SPI decoder: {err}")
        client.disconnect()
        return

    print(f"SPI decoder added: {decoder_id}")

    # Get decoded data
    err, decoded = client.analyzer_get_decoded_data(capture_id, decoder_id)
    if err:
        print(f"Failed to get decoded data: {err}")
    else:
        print(f"Found {len(decoded)} SPI transactions")
        for item in decoded:
            if item.HasField("spi"):
                spi = item.spi
                print(f"  MOSI: {spi.mosi_data.hex()}, MISO: {spi.miso_data.hex()}")

    client.disconnect()


def example_triggered_capture():
    """Example: Capture with trigger on rising edge."""
    config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
    client = MtibV2Client(config)

    error = client.connect()
    if error:
        print(f"Connection failed: {error}")
        return

    # Start capture with trigger on channel 0
    err, capture_id = client.analyzer_capture_start(
        channels=[0, 1, 2, 3],
        sample_rate_hz=10_000_000,
        duration_s=1.0,
        trigger_channel=0,
        trigger_edge="rising",
        pre_trigger_s=0.1,  # Capture 100ms before trigger
    )

    if err:
        print(f"Failed to start capture: {err}")
        client.disconnect()
        return

    print(f"Waiting for trigger on channel 0: {capture_id}")

    # Monitor status
    import time
    for _ in range(60):  # Wait up to 30 seconds
        err, status = client.analyzer_capture_status(capture_id)
        if err:
            print(f"Status check failed: {err}")
            break

        if status["status"] == 0:
            print("Waiting for trigger...")
        elif status["status"] == 1:
            print(f"Triggered! Capturing... {status['progress']:.1%}")
        elif status["status"] == 2:
            print("Capture complete!")
            break

        time.sleep(0.5)

    client.disconnect()


def example_list_providers():
    """Example: List available analyzer providers."""
    config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
    client = MtibV2Client(config)

    error = client.connect()
    if error:
        print(f"Connection failed: {error}")
        return

    # List available providers
    err, providers = client.analyzer_list_providers()
    if err:
        print(f"Failed to list providers: {err}")
    else:
        print(f"Found {len(providers)} analyzer providers:")
        for p in providers:
            status = "available" if p.available else "unavailable"
            print(f"  {p.display_name} ({status})")
            print(f"    Max rate: {p.max_sample_rate_hz / 1e6:.1f} MHz")
            print(f"    Channels: {p.max_channels}")
            print(f"    Hardware: {p.hardware_detected}")
            print(f"    Protocols: {', '.join(p.supported_protocols)}")

    client.disconnect()


if __name__ == "__main__":
    print("MTIB V2 Analyzer Examples")
    print("=" * 50)
    print()

    # Uncomment to run examples:
    # example_basic_capture()
    # example_i2c_decode()
    # example_spi_decode()
    # example_triggered_capture()
    # example_list_providers()

    print("Edit this file to uncomment and run specific examples.")
