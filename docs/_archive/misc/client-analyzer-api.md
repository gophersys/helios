# MTIB V2 Client - Analyzer API

This document describes the high-level analyzer (logic analyzer) API provided by the MTIB V2 client library.

## Overview

The analyzer API provides vendor-neutral access to logic analyzer functionality. It abstracts over multiple backends:

- **Saleae Logic 2** - High-end logic analyzer with protocol decoders
- **sigrok/libsigrok** - Open-source logic analyzer support (fx2lafw, DSLogic, etc.)
- **Simulation** - Mock data for testing without hardware

All methods follow the client's Go-style error return pattern:
- Action methods return `Optional[str]` (None = success, str = error message)
- Value methods return `(Optional[str], result)` tuples (error first)

## Quick Start

```python
from corekinect.mtib_client.v2 import MtibV2Client, ClientConfig, NetConfig

# Connect to MTIB server
config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
client = MtibV2Client(config)
client.connect()

# Start a capture
err, cap_id = client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=10_000_000,
    duration_s=5.0,
)

# Wait for completion
import time
while True:
    err, status = client.analyzer_capture_status(cap_id)
    if status["status"] == 2:  # COMPLETE
        break
    time.sleep(0.5)

# Export to CSV
err, path = client.analyzer_export(cap_id, format="csv")
print(f"Exported to: {path}")

client.disconnect()
```

## API Reference

### analyzer_list_providers()

List available logic analyzer providers and their capabilities.

**Returns:** `(error, providers)` tuple
- `error`: Error message string, or None on success
- `providers`: List of `AnalyzerProviderInfo` objects

**AnalyzerProviderInfo attributes:**
- `name`: Provider identifier ("saleae", "sigrok", "simulation")
- `display_name`: Human-readable name
- `available`: Whether provider is currently available
- `max_sample_rate_hz`: Maximum sample rate
- `max_channels`: Maximum number of channels
- `supported_protocols`: List of protocol decoder names
- `supports_streaming`: Whether real-time streaming is supported
- `supports_triggers`: Whether hardware triggers are supported
- `hardware_detected`: Detected hardware device
- `supported_export_formats`: Supported export formats

**Example:**

```python
err, providers = client.analyzer_list_providers()
if not err:
    for p in providers:
        print(f"{p.display_name}:")
        print(f"  Max rate: {p.max_sample_rate_hz / 1e6:.1f} MHz")
        print(f"  Channels: {p.max_channels}")
        print(f"  Hardware: {p.hardware_detected}")
```

**Note:** This method requires the updated protocol with `ListAnalyzerProviders` RPC. Returns error if server doesn't support it yet.

---

### analyzer_capture_start()

Start a logic analyzer capture.

**Parameters:**
- `channels`: List of channel numbers to capture (e.g., `[0, 1, 2, 3]`)
- `sample_rate_hz`: Sample rate in Hz (default: 10,000,000)
- `duration_s`: Capture duration in seconds (default: 1.0)
- `prefer_provider`: Preferred provider ("auto", "saleae", "sigrok", "simulation")
- `max_memory_mb`: Memory limit in MB (default: 512)
- `trigger_channel`: Optional channel for trigger (None = no trigger)
- `trigger_edge`: Trigger edge type ("rising", "falling", "either")
- `pre_trigger_s`: Pre-trigger capture duration in seconds

**Returns:** `(error, capture_id)` tuple
- `error`: Error message string, or None on success
- `capture_id`: Unique capture ID for status queries and data retrieval

**Example:**

```python
# Basic capture
err, cap_id = client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=10_000_000,
    duration_s=5.0,
)

# Triggered capture
err, cap_id = client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=20_000_000,
    duration_s=1.0,
    trigger_channel=0,
    trigger_edge="rising",
    pre_trigger_s=0.1,  # Capture 100ms before trigger
)
```

---

### analyzer_stream()

Stream samples in real-time from an active capture.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`
- `max_samples_per_chunk`: Maximum samples per yielded chunk (default: 1000)

**Yields:** Iterator of `AnalyzerStreamResponse` objects

**Example:**

```python
err, cap_id = client.analyzer_capture_start(...)
if not err:
    for chunk in client.analyzer_stream(cap_id):
        print(f"Received {len(chunk.samples)} samples")
        if chunk.capture_complete:
            break
```

**Note:** This method requires the updated protocol with `AnalyzerStream` RPC. Raises exception if server doesn't support it yet.

---

### analyzer_capture_status()

Get the status of an analyzer capture.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`

**Returns:** `(error, status_info)` tuple
- `error`: Error message string, or None on success
- `status_info`: Dictionary containing:
  - `status`: int (0=WAITING_TRIGGER, 1=CAPTURING, 2=COMPLETE, 3=ERROR)
  - `progress`: float (0.0 to 1.0)
  - `samples_captured`: int (total samples captured)
  - `samples_dropped`: int (samples dropped due to memory limit)
  - `memory_usage_mb`: float (current memory usage)

**Example:**

```python
err, status = client.analyzer_capture_status(cap_id)
if not err:
    if status["status"] == 0:
        print("Waiting for trigger...")
    elif status["status"] == 1:
        print(f"Capturing... {status['progress']:.1%}")
    elif status["status"] == 2:
        print("Capture complete!")
    elif status["status"] == 3:
        print("Capture error!")
```

---

### analyzer_capture_stop()

Stop an analyzer capture before it completes naturally.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`

**Returns:** Error message string, or None on success

**Example:**

```python
err = client.analyzer_capture_stop(cap_id)
if not err:
    print("Capture stopped")
```

---

### analyzer_export()

Export analyzer capture to file.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`
- `format`: Export format ("csv", "vcd", "native_saleae", "native_sigrok")
- `output_path`: Filename (relative to server export directory)

**Returns:** `(error, file_path)` tuple
- `error`: Error message string, or None on success
- `file_path`: Full path to the exported file

**Export formats:**
- `csv`: Raw digital CSV (timestamp, CH0, CH1, ...)
- `vcd`: Value Change Dump (waveform viewer format - GTKWave, PulseView)
- `native_saleae`: .sal file (Saleae Logic 2 native format)
- `native_sigrok`: .sr file (sigrok/PulseView native format)

**Example:**

```python
# Export to CSV
err, csv_path = client.analyzer_export(cap_id, format="csv")
if not err:
    print(f"CSV exported to: {csv_path}")

# Export to VCD for waveform viewer
err, vcd_path = client.analyzer_export(cap_id, format="vcd", output_path="capture.vcd")
if not err:
    print(f"Open in GTKWave: {vcd_path}")
```

**Note:** This method requires the updated protocol with `AnalyzerExport` RPC. Returns error if server doesn't support it yet.

---

### analyzer_add_i2c_decoder()

Add an I2C protocol decoder to a capture.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`
- `sda_channel`: Channel number for SDA (data)
- `scl_channel`: Channel number for SCL (clock)
- `decoder_name`: Human-readable name (default: "I2C")

**Returns:** `(error, decoder_id)` tuple
- `error`: Error message string, or None on success
- `decoder_id`: Decoder ID for retrieving decoded data

**Example:**

```python
# Capture I2C signals on channels 0 (SDA) and 1 (SCL)
err, cap_id = client.analyzer_capture_start(
    channels=[0, 1],
    sample_rate_hz=10_000_000,
    duration_s=2.0,
)

# Add I2C decoder
err, dec_id = client.analyzer_add_i2c_decoder(
    capture_id=cap_id,
    sda_channel=0,
    scl_channel=1,
)

# Get decoded transactions
err, data = client.analyzer_get_decoded_data(cap_id, dec_id)
for item in data:
    if item.HasField("i2c"):
        i2c = item.i2c
        rw = "R" if i2c.read else "W"
        print(f"{rw} 0x{i2c.address:02x}: {i2c.data.hex()}")
```

---

### analyzer_add_spi_decoder()

Add an SPI protocol decoder to a capture.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`
- `clk_channel`: Channel number for CLK (clock)
- `mosi_channel`: Channel number for MOSI (master out, slave in)
- `miso_channel`: Channel number for MISO (master in, slave out)
- `cs_channel`: Channel number for CS (chip select)
- `cpol`: Clock polarity (default: False)
- `cpha`: Clock phase (default: False)
- `bits_per_word`: Bits per word (default: 8)
- `msb_first`: MSB first (default: True)
- `decoder_name`: Human-readable name (default: "SPI")

**Returns:** `(error, decoder_id)` tuple
- `error`: Error message string, or None on success
- `decoder_id`: Decoder ID for retrieving decoded data

**Example:**

```python
# Capture SPI signals
err, cap_id = client.analyzer_capture_start(
    channels=[0, 1, 2, 3],  # CLK, MOSI, MISO, CS
    sample_rate_hz=20_000_000,
    duration_s=1.0,
)

# Add SPI decoder
err, dec_id = client.analyzer_add_spi_decoder(
    capture_id=cap_id,
    clk_channel=0,
    mosi_channel=1,
    miso_channel=2,
    cs_channel=3,
)

# Get decoded transactions
err, data = client.analyzer_get_decoded_data(cap_id, dec_id)
for item in data:
    if item.HasField("spi"):
        spi = item.spi
        print(f"MOSI: {spi.mosi_data.hex()}, MISO: {spi.miso_data.hex()}")
```

---

### analyzer_get_decoded_data()

Get decoded protocol data from a capture.

**Parameters:**
- `capture_id`: Capture ID from `analyzer_capture_start()`
- `decoder_id`: Decoder ID (empty string = all decoders)

**Returns:** `(error, decoded_data)` tuple
- `error`: Error message string, or None on success
- `decoded_data`: List of `DecodedData` protobuf messages

**DecodedData structure:**
Each `DecodedData` message contains one of:
- `i2c`: I2C transaction (address, read/write, data, ack)
- `spi`: SPI transaction (MOSI data, MISO data)
- `uart`: UART frame (TX/RX, data, parity/framing errors)
- `can`: CAN frame (ID, extended ID, RTR, data)

**Example:**

```python
err, data = client.analyzer_get_decoded_data(cap_id, dec_id)
if not err:
    for item in data:
        if item.HasField("i2c"):
            i2c = item.i2c
            ts = item.i2c.timestamp
            print(f"[{ts.seconds}.{ts.nanos:09d}] I2C: 0x{i2c.address:02x}")
        elif item.HasField("spi"):
            spi = item.spi
            print(f"SPI TX: {spi.mosi_data.hex()}, RX: {spi.miso_data.hex()}")
```

---

## Complete Example: I2C EEPROM Read

```python
from corekinect.mtib_client.v2 import MtibV2Client, ClientConfig, NetConfig
import time

# Connect to MTIB
config = ClientConfig(net=NetConfig(addr="10.4.45.33", port=50052))
client = MtibV2Client(config)
client.connect()

# Start capture on I2C pins
err, cap_id = client.analyzer_capture_start(
    channels=[0, 1],  # SDA=CH0, SCL=CH1
    sample_rate_hz=10_000_000,
    duration_s=2.0,
)

if err:
    print(f"Capture failed: {err}")
    exit(1)

print(f"Capturing I2C traffic: {cap_id}")

# Wait for capture to complete
while True:
    err, status = client.analyzer_capture_status(cap_id)
    if status["status"] == 2:  # COMPLETE
        break
    time.sleep(0.5)

# Add I2C decoder
err, dec_id = client.analyzer_add_i2c_decoder(
    capture_id=cap_id,
    sda_channel=0,
    scl_channel=1,
)

if err:
    print(f"Decoder failed: {err}")
    exit(1)

# Get decoded transactions
err, transactions = client.analyzer_get_decoded_data(cap_id, dec_id)
if err:
    print(f"Failed to get data: {err}")
    exit(1)

# Parse EEPROM read (address 0x50)
print(f"\nFound {len(transactions)} I2C transactions:")
for item in transactions:
    if item.HasField("i2c"):
        i2c = item.i2c
        rw = "READ" if i2c.read else "WRITE"
        ack = "ACK" if i2c.ack else "NACK"
        print(f"  {rw} 0x{i2c.address:02x}: {i2c.data.hex()} [{ack}]")

# Export to CSV for offline analysis
err, csv_path = client.analyzer_export(cap_id, format="csv")
if not err:
    print(f"\nCSV exported to: {csv_path}")

client.disconnect()
```

## Status Codes

The `status` field in `analyzer_capture_status()` returns:

| Code | Name | Description |
|------|------|-------------|
| 0 | WAITING_TRIGGER | Capture armed, waiting for trigger |
| 1 | CAPTURING | Actively capturing samples |
| 2 | COMPLETE | Capture finished successfully |
| 3 | ERROR | Capture failed (check `message` field) |

## Protocol Support

Protocol decoders currently supported:

| Protocol | Method | Notes |
|----------|--------|-------|
| I2C | `analyzer_add_i2c_decoder()` | Standard 7-bit addressing |
| SPI | `analyzer_add_spi_decoder()` | All modes (CPOL/CPHA) |
| UART | (TBD) | Async serial |
| CAN | (TBD) | 2.0A/2.0B |
| 1-Wire | (TBD) | Dallas 1-Wire |
| JTAG | (TBD) | IEEE 1149.1 |
| SWD | (TBD) | ARM Serial Wire Debug |

Additional protocol decoders will be added via the `AddDecoder` RPC.

## Migration from Logic* Methods

The analyzer API is the new vendor-neutral replacement for the Logic* methods:

| Old Method | New Method |
|------------|------------|
| `logic_capture_start()` | `analyzer_capture_start()` |
| `logic_capture_status()` | `analyzer_capture_status()` |
| `logic_capture_stop()` | `analyzer_capture_stop()` |
| `add_decoder()` | `analyzer_add_i2c_decoder()`, `analyzer_add_spi_decoder()` |
| `get_decoded_data()` | `analyzer_get_decoded_data()` |

The new methods provide:
- Better parameter validation
- Clearer naming
- Richer status information
- Export capabilities
- Provider discovery

## Future Enhancements

Planned features (requires protocol updates):

1. **Real-time streaming** - `analyzer_stream()` for live signal monitoring
2. **Export formats** - VCD, native Saleae/sigrok formats
3. **Provider selection** - Choose specific backend (Saleae, sigrok, etc.)
4. **Resource limits** - Memory limits, circular buffers
5. **Advanced triggers** - Pattern matching, complex conditions
6. **More decoders** - UART, CAN, 1-Wire, JTAG, SWD, I2S, PWM

## See Also

- Protocol spec: `/workspaces/concord/docs/v2/protocol-changes-analyzer.md`
- Example code: `/workspaces/concord/libs/python/corekinect/mtib_client/v2/examples/analyzer_example.py`
- MTIB hardware: `/workspaces/concord/.claude/rules/mtib-hardware.md`
