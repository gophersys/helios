# MTIB Hardware Rules

## DUT Power — Alpha B0

Power behavior depends on whether the DUT has a battery installed. The fixture profile (`alpha_b0.json`) controls this via the `battery_installed` field.

### Without Battery (validation fixture, `battery_installed: false`)

Only ch0 (VBAT) should be enabled at 4.5V. **Ch1 (charger) must NEVER be enabled** — the variable PSU would attempt to sink current and risk damaging the supply.

All DUT current flows through ch0. After boot, ch0 carries the full load (~17-33mA).

```python
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig

# Step 1: Configure GPIO 0+1 as output LOW — REQUIRED for DUT to boot
client.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
client.GpioConfig(gpio=1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
client.GpioWrite(gpio=0, state=False)
client.GpioWrite(gpio=1, state=False)

# Step 2: Enable ch0 ONLY
client.PowerEnable(channel=0, voltage_v=4.5)  # Battery sim rail
time.sleep(3)                                  # Wait for boot
```

**Verification:** Check ch0 alone after 3s — should be >5mA. ADC ch7 (3.3V ref) >3.0V also confirms DUT regulators are active.

### With Battery (`battery_installed: true`)

Both rails required — ch0 (battery sim) at 4.5V + ch1 (charger) at 5.0V.

```python
# Step 1: GPIO 0+1 LOW (same as above)
# Step 2: Enable BOTH power rails
client.PowerEnable(channel=0, voltage_v=4.5)  # Battery sim rail
client.PowerEnable(channel=1, voltage_v=5.0)  # Charger rail
time.sleep(5)                                  # Wait for boot + charger takeover
```

**Boot power timeline (both rails enabled):**
- t=0-3s: DUT boots, draws 65-100mA from ch0 (battery), ch1 draws 2-6mA
- t=4s: BQ25180 charger takes over — ch0 drops to ~0mA, ch1 increases to 17-33mA
- t=5s+: Steady state — ch0 ~0mA, ch1 ~17-33mA (charger supplies DUT)

**Verification:** Use `read_total_current()` (ch0 + ch1) after 5s. Total should be >5mA. Do NOT check ch0 alone — after charger takeover, ch0 is ~0mA even when DUT is running.

### Common Mistakes (both modes)

**Common mistake 1:** Using 4.0V on ch0. At 4.0V the voltage regulator outputs voltage but the BQ25180 does NOT enable the system rail → 0mA current.

**Common mistake 2:** Not configuring GPIO 0+1 before power-on. Without GPIO 0+1 as output LOW, the INA219 reads 4.5V but 0mA — the DUT does not boot despite correct voltage.

**Common mistake 3 (batteryless):** Enabling ch1 without a battery. The PSU will attempt to sink current — hardware risk.

**INA219 residual voltage:** After PowerDisable, the INA219 still shows ~4.5V (capacitor residual). This is normal — the voltage decays slowly with no load.

## UART Port Mapping

| Port Name | Device Path | Alpha B0 Target |
|-----------|------------|-----------------|
| `uart0` | `/dev/verdin-uart1` | nRF9151 comms coprocessor |
| `uart1` | `/dev/verdin-uart2` | nRF52840 app processor |

- REV 1.1: Firmware needed DTS overlay to swap UART TX/RX pins (hardware had them reversed)
- REV 1.2: Fixed in hardware — firmware uses board default pins, no overlay needed

## UART Session — MUST Open Before Boot

**MANDATORY**: A UART stream session MUST be established BEFORE powering on the DUT. These microcontrollers boot in milliseconds and emit critical startup messages (MCUboot, init logs, mfg shell prompt) immediately. If the UART stream is opened after boot, you WILL miss boot output and may miss the manufacturing shell activation window entirely.

**Correct sequence:**
1. Open UART streams (both APP nRF52840 target=3 + COMMS nRF9151 target=1)
2. THEN enable power (PowerEnable)
3. Capture boot output from the very first byte

**Wrong sequence (will miss boot output):**
1. Enable power
2. Open UART streams ← TOO LATE, boot messages already gone

This applies to ALL operations that involve a power cycle or reset: initial boot, re-personalization, post-flash verification, FUOTA reboot confirmation.

### UART Stream Speed Issue

The MTIB server currently delivers UART data byte-by-byte rather than in buffered chunks at 115200 baud. This means UART output appears very slowly on the client side even though the device has already finished transmitting. This is a known MTIB server limitation — do not assume the device is still producing output just because bytes are still arriving. The actual device activity may be 30-60 seconds ahead of what the UART stream shows.

## Manufacturing Shell

- Shell activation window: **~2 seconds after boot** (auto-deactivates at ~8 seconds with "Shell commands ignored going forward")
- Open UARTs BEFORE power-on, then immediately spam `lock_shell`
- After locking, send `debug_enable 0` to reduce UART noise
- TX backlog drain can take 1-5 minutes at 115200 baud due to byte-by-byte MTIB streaming

## Hardware Revisions

| Feature | REV 1.1 | REV 1.2 |
|---------|---------|---------|
| MCP4017 potentiometer | 100kΩ | 10kΩ |
| TCA9534A GPIO expander | No | Yes (0x38) |
| EEPROM | No | Yes (0x50) |
| J-Link mux | No | Yes (TCA9534A P0) |
| Motor power switch | No | Yes (TCA9534A P2) |
| UART pin swap needed | Yes (DTS overlay) | No (fixed in HW) |

## J-Link Flashing Rules

- **Always use clockspeed 4000** (4 MHz) for nrfjprog operations. The default speed can be too fast for the SWD connection through the MTIB mux. Note: nrfjprog 10.x uses `--clockspeed`, not `--speed`.
- **Always power the DUT at 4.5V** before any J-Link/SWD operation (see power rules above).
- **Always run `--recover` before flashing** to clear APPROTECT and reset the debug port.
- nrfjprog is only available inside the K8s pod — use `kubectl exec` to access it.

```bash
# Recovery (run first):
nrfjprog --recover --snr <PROBE_SERIAL> -f NRF52 --clockspeed 4000

# Flash:
nrfjprog --program <file.hex> --chiperase --verify --reset --snr <PROBE_SERIAL> -f NRF52 --clockspeed 4000
```

### J-Link Probe Mapping (REV 1.2 MTIB at 10.4.45.33)

| Probe SNR | Family | Target |
|-----------|--------|--------|
| 821009543 | NRF52 | nRF52840 app processor |
| 821009541 | NRF91 | nRF9151 comms coprocessor |

## Test MTIBs

| Address | Revision | DUT SNR | Device ID | Notes |
|---------|----------|---------|-----------|-------|
| 10.4.45.33 | REV 1.2 | 0964 | `70B3D584C01E1FCC` | K8s pod runs MTIB server. SSH: torizon@10.4.45.33 (pass: corekinect). |
| 10.4.45.32 | REV 1.1 | 097D | `70B3D584C01E20A2` | K8s pod runs MTIB server. SSH: torizon@10.4.45.32 (pass: corekinect). |

## V1 Client API Quick Reference

```python
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
# PYTHONPATH must include: libs/python:libs:libs/protocols

cfg = MtibV1Client.Config(net=NetConfig(addr='10.4.45.33', port=50053))
client = MtibV1Client(cfg)
err = client.connect()  # MUST call before any RPC

# Power: DutPowerRead() returns 4-tuple (current_a, voltage_v, power_w, error)
# GPIO: GpioConfig(gpio=N, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
# GPIO: GpioWrite(gpio=N, state=False)
# UART: UartStream(target=HostType, request_iterator=iter) — bidirectional streaming
```

## ADC Channel Mapping (Measured)

| Channel | REV 1.2 Reading | REV 1.1 Reading | Likely Signal |
|---------|----------------|----------------|---------------|
| Ch 0 | 4.52V | 4.49V | Power rail (DUT voltage) |
| Ch 1 | 2.52V | 2.54V | Battery voltage divider |
| Ch 2 | 4.51V | 4.48V | Backup power rail |
| Ch 3 | 0.01V | 0.02V | Unused / unconnected |
| Ch 4 | 0.01V | 0.01V | Unused / unconnected |
| Ch 5 | 0.01V | 0.01V | Unused / unconnected |
| Ch 6 | 0.01V | 0.02V | Unused / unconnected |
| Ch 7 | 3.30V | 3.31V | 3.3V reference rail |

**Note:** Manufacturing code labels differ (BATT_SYS=1, SYS=3, 3V3=0, VBCKP=2). Actual mapping may depend on fixture wiring.

## UART Stream Protocol

The UART stream requires **continuous request pumping** — the server only yields responses when it receives requests from the client. Send requests at ~20Hz (50ms interval) to get real-time UART data:

```python
def req_gen():
    yield UartStreamRequest(target=HostType.HOST_TYPE_NRF9151)
    while not stop_event.is_set():
        time.sleep(0.05)  # 20 Hz polling
        yield UartStreamRequest(target=target)

for resp in client.UartStream(target, req_gen()):
    if resp.data:
        print(resp.data.decode('utf-8', errors='replace'))
```

**Critical:** Open UARTs BEFORE power-on to capture boot output (MCUboot, init logs, mfg shell prompt).

## Known MTIB Server Issues

- **ListProgrammers returned empty** — Fixed: `_assign_jlinks()` was not called during ListProgrammers. Now scans on every call. **Needs redeploy.**
- **MotionStart returned non-iterator** — Fixed: used `yield`/`yield from` instead of `return`. **Needs redeploy.**
- **Server implements both V1 and V2 RPCs** — DutPowerEnable (V1) and PowerEnable (V2) both work. No proto mismatch.
- **Motion not available** — `MOTION_ENABLED=False`. FluidNC linear rail not connected to validation MTIBs.
- **UART stream byte-by-byte delivery** — At 115200 baud, UART data arrives one byte per gRPC response instead of buffered chunks. Client-side UART output lags 30-60s behind actual device activity. Root cause likely in MTIB server serial read loop (no buffering/batching). **Needs investigation.**
