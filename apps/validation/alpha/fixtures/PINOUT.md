# Alpha B0 Fixture — Physical Stimulus Design

**MTIB REV 1.2 | Fixture Profile: `alpha_b0.json`**

## Concept

The Alpha validation fixture physically simulates real-world conditions
to fool the DUT's sensors into producing realistic data. The DUT firmware
runs identically to production — it doesn't know it's on a test bench.

Tests are **black-box**: they stimulate the device through physical
mechanisms and verify behavior through CoreCloud messages, power
measurements, LED state, and (when available) UART debug logs.

```
┌─────────────────────────────────────────────────────┐
│  TEST (e.g. test_biometric.py)                      │
│  ctx.fixture.simulate_on_skin(on=True)              │
│  ctx.fixture.set_peltier(on=True)                   │
│  msg = ctx.cloud.wait_for_biometric(timeout_s=120)  │
└──────────────────┬──────────────────────────────────┘
                   │ calls
┌──────────────────▼──────────────────────────────────┐
│  FIXTURE CONTROLLER (product-agnostic harness)      │
│  Reads alpha_b0.json for pin/channel mappings       │
│  Translates actions → MTIB V1 RPCs                  │
└──────────────────┬──────────────────────────────────┘
                   │ drives
┌──────────────────▼──────────────────────────────────┐
│  PHYSICAL FIXTURE (product-specific hardware)       │
│  Servo, LED array, peltier, button wire, relays     │
│  Physically fools DUT sensors                       │
└──────────────────┬──────────────────────────────────┘
                   │ stimulates
┌──────────────────▼──────────────────────────────────┐
│  DUT (Alpha B0)                                     │
│  PAH8151 PPG, MLX90614 IR temp, LSM6DSO IMU,       │
│  button GPIO, LP5814 LEDs, nRF9151 modem            │
└─────────────────────────────────────────────────────┘
```

## Stimulus Signals

### 1. PPG Skin Contact Simulator (Servo + IR Blocker)

**What it does:** Simulates placing the device on skin so the PAH8151
PPG sensor detects "touch" and the VSM firmware transitions from
`VITALS_STATE_IDLE` → `TOUCH_DETECTED` → `SKIN_CONFIRMED`.

**Physical mechanism:**
- A 3D-printed black (IR-absorbing) piece sits between the DUT's PPG
  sensor glass and a green LED array on a breadboard underneath
- A servo rotates this blocker 90 degrees in/out
- **Blocked (default):** IR from PPG sensor is absorbed → no reflectance
  → sensor reports no touch → firmware stays in IDLE
- **Exposed (skin on):** Blocker moves out → green LED PCB reflects IR
  back through glass → sensor detects proximity → firmware triggers
  touch detection → after `skin_detection_period_ms` (6s), confirms skin

**MTIB wiring:**
| Signal | MTIB Pin | Direction | Notes |
|--------|----------|-----------|-------|
| Servo PWM | PWM pin 7 (SODIMM_15) | OUTPUT | Standard servo pulse: 1000us=blocked, 2000us=exposed. 50Hz PWM frame. |

**Fixture controller method:** `simulate_on_skin(on=True/False)`

**Status:** PWM RPC not yet in MTIB V1 proto. Servo control requires
server-side PWM support to be implemented.

### 2. Heart Rate Simulator (Green LED Array)

**What it does:** Pulses green LEDs at a heart-rate frequency so the
PAH8151 PPG sensor reads a pulsating optical signal. The PSP algorithm
in firmware interprets this as a real heartbeat and computes HR/SpO2.

**Physical mechanism:**
- Green LEDs (530nm, matching PPG green channel) mounted on breadboard
  under the PPG sensor window
- LEDs are toggled on/off by a GPIO at the target heart rate frequency
- At 72 BPM → 1.2 Hz toggle rate — well within GPIO capability
- The servo must be in "exposed" position (blocker out) for the PPG
  sensor to see the LEDs

**MTIB wiring:**
| Signal | MTIB Pin | Direction | Notes |
|--------|----------|-----------|-------|
| HR LED enable | GPIO 3 | OUTPUT | HIGH=LEDs on, LOW=LEDs off. Toggle at BPM/60 Hz for HR sim. Steady HIGH for touch-only (no HR data). |

**Fixture controller methods:**
- `simulate_heartbeat(bpm=72)` — start pulsing at target BPM
- `stop_heartbeat()` — stop pulsing, LEDs off

**Status:** GPIO toggle implemented. Pulsing thread not yet built.
Actual HR simulation parameters (duty cycle, waveform shape) need
experimental characterization against PAH8151 + PSP algorithm.

### 3. Button Press Simulator

**What it does:** Drives the DUT button membrane switch line to simulate
physical button presses. Firmware behavior depends on press duration:
- Short press (<1s): Status LED flash
- Long press (3s): SOS mode
- Very long press (8s): Power off

**Physical mechanism:**
- Wire from MTIB GPIO directly to DUT button input pad
- DUT has internal pull-up resistor on button line
- GPIO drives LOW to simulate press, HIGH to release (active-low)

**MTIB wiring:**
| Signal | MTIB Pin | Direction | Polarity |
|--------|----------|-----------|----------|
| Button | GPIO 2 | OUTPUT | **Active LOW** — LOW=pressed, HIGH=released |

**Initial state:** HIGH (released). Critical: if left LOW after GPIO
config, firmware sees an 8s hold and powers off the DUT.

**Fixture controller methods:**
- `press_button(duration_s=0.5)` — short press
- `long_press_button(duration_s=3.0)` — SOS press
- `long_press_button(duration_s=8.0)` — power off press

### 4. Skin Temperature Simulator (Peltier Heater)

**What it does:** Heats a surface near the DUT's MLX90614 IR temperature
sensor to simulate realistic skin temperature (~33C). The VSM firmware
checks `skin_temp_min_threshold_f` — if the IR sensor reads too cold,
the device won't enter active monitoring even with PPG touch confirmed.

**Physical mechanism:**
- Peltier element (or resistive heater) positioned near the MLX90614
  sensor's field of view
- MTIB GPIO drives a MOSFET gate that switches peltier power
- Takes ~30-60s to reach target temperature from ambient

**MTIB wiring:**
| Signal | MTIB Pin | Direction | Notes |
|--------|----------|-----------|-------|
| Peltier MOSFET gate | GPIO 4 | OUTPUT | HIGH=heater on, LOW=heater off. MOSFET source=GND, drain=peltier element. |

**Fixture controller method:** `set_peltier(on=True/False)`

### 5. Charger Relay

**What it does:** Connects/disconnects the charger power rail (5V) to
the DUT's VCHG input via a relay. Used for battery mode testing where
the BQ25180 charger IC manages power distribution between battery sim
rail (ch0) and charger rail (ch1).

**Physical mechanism:**
- Relay NO contact connects ch1 PSU output to DUT VCHG pad
- MTIB GPIO drives relay coil

**MTIB wiring:**
| Signal | MTIB Pin | Direction | Notes |
|--------|----------|-----------|-------|
| Charger relay coil | GPIO 5 | OUTPUT | HIGH=relay closed (charger connected), LOW=relay open |

**Fixture controller methods:**
- `connect_charger()` / `disconnect_charger()`
- Also managed automatically by `power_on()` based on `battery_installed`

## Measurement Signals (Fixture → Test)

These are **read-only** — the fixture reads DUT state, it doesn't drive it.

### LED Photodiodes (ADC ch 4-6)

**What they measure:** Light output from DUT status LEDs (red/green/blue).
Used to verify LED responses to button presses, status changes, errors.

**Physical mechanism:**
- Photodiode per color channel positioned directly over corresponding
  DUT LED in the membrane
- Ambient light shield (opaque tube or foam gasket) recommended
- Circuit: `3.3V ──[10k]──┬── ADC ch`, photodiode to GND

| ADC Channel | Color | Expected idle | Expected LED on |
|-------------|-------|---------------|-----------------|
| Ch 4 | Red | ~0.01V | >0.1V |
| Ch 5 | Green | ~0.01V | >0.1V |
| Ch 6 | Blue | ~0.01V | >0.1V |

**Status:** Not yet wired on current fixture. Tests marked `@pytest.mark.xfail`.

### Power Measurement (INA219 ch 0-1)

| Power Channel | INA219 | Voltage | DUT Connection |
|---------------|--------|---------|----------------|
| Ch 0 (DUT) | #0 | 4.5V | Battery sim rail (VBAT) |
| Ch 1 (CHARGER) | #1 | 5.0V | Charger input (VCHG) via relay |

**Battery mode behavior:** After ~4s boot, BQ25180 charger takes over.
Ch0 drops to ~0mA, ch1 carries 17-33mA. Use `read_total_current()` or
measure on ch1 (`primary_power_channel`).

### Manufacturing ADC Rails (ch 0-3, 7)

| ADC Channel | Signal | Expected |
|-------------|--------|----------|
| Ch 0 | Power rail (post-regulator) | ~4.5V |
| Ch 1 | Battery voltage divider | ~2.5V |
| Ch 2 | Backup power rail | ~4.5V |
| Ch 3 | System rail (unused on Alpha) | ~0V |
| Ch 7 | 3.3V reference | ~3.3V |

## Reserved Signals

| MTIB Pin | Signal | Notes |
|----------|--------|-------|
| GPIO 0 | SWD level shifter enable | **Always OUTPUT LOW.** Required for DUT to boot. Never assign to fixture. |
| GPIO 1 | SWD level shifter enable | **Always OUTPUT LOW.** Same as GPIO 0. |
| GPIO 6 | Available | Unassigned. Future use (haptic vibration sensor, etc.) |
| GPIO 8 | PWM_2 (SODIMM_16) | Available PWM pin. Unassigned. |

## UART Ports

| UART Port | Device Path | Baud | DUT Target | Data |
|-----------|------------|------|------------|------|
| uart0 | /dev/verdin-uart1 | 115200 | nRF9151 (comms) | Modem AT cmds, checkin logs |
| uart1 | /dev/verdin-uart2 | 115200 | nRF52840 (app) | Mfg shell, sensor data, VSM state transitions |

**Critical:** UART streams must be opened BEFORE power-on to capture boot output.

## Full Skin Contact Test Sequence

For a complete "on-skin biometric" test, the fixture orchestrates:

```
1. set_peltier(on=True)              # Start heating (needs ~30-60s)
2. time.sleep(60)                    # Wait for temp to reach ~33C
3. simulate_on_skin(on=True)         # Servo moves blocker out, HR LED on
4. time.sleep(10)                    # PAH8151 detects touch
   # ... firmware: IDLE → TOUCH_DETECTED → (6s) → SKIN_CONFIRMED
5. simulate_heartbeat(bpm=72)        # Start pulsing LEDs at HR frequency
6. time.sleep(30)                    # PSP algorithm needs ~20s of data
   # ... firmware: SKIN_CONFIRMED → ACTIVE_MONITORING
7. msg = cloud.wait_for_biometric()  # Verify CoreCloud got HR/SpO2 data
8. stop_heartbeat()                  # Stop HR simulation
9. simulate_on_skin(on=False)        # Servo blocks PPG sensor
10. set_peltier(on=False)            # Heater off
```

## Physical Wiring Checklist

- [ ] GPIO 0+1 → SWD level shifter (on MTIB PCB, no external wiring)
- [ ] GPIO 2 → Button membrane switch line on DUT button input pad
- [ ] GPIO 3 → Green LED array (530nm LEDs on breadboard under PPG window)
- [ ] GPIO 4 → Peltier MOSFET gate (source=GND, drain=peltier near MLX90614)
- [ ] GPIO 5 → Charger relay coil (NO connects ch1 PSU to DUT VCHG)
- [ ] PWM pin 7 → Servo signal wire (positions IR blocker, 50Hz PWM)
- [ ] Servo power → 5V supply (separate from DUT power)
- [ ] 3D-printed IR blocker → mounted on servo horn, positioned between PPG glass and LED array
- [ ] LED array PCB → positioned under DUT PPG sensor window
- [ ] Peltier element → positioned in MLX90614 field of view
- [ ] Power ch0 → DUT VBAT pad (battery simulator rail, 4.5V)
- [ ] Power ch1 → Charger relay COM (relay switches 5V to DUT VCHG)
- [ ] UART0 TX/RX → nRF9151 UART pads
- [ ] UART1 TX/RX → nRF52840 UART pads
- [ ] SWD → nRF52840 SWDIO/SWDCLK via J-Link mux
