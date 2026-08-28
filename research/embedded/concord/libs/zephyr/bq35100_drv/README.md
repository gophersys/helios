# BQ35100 Primary Battery Fuel Gauge Driver

Zephyr sensor driver for the Texas Instruments BQ35100 primary (non-rechargeable) battery
fuel gauge with impedance tracking. Designed for Li-SOCl2 and Li-MnO2 chemistries.

**Last reviewed:** 2026-03-20
**Status:** Active

## Hardware Overview

| Parameter | Value |
|-----------|-------|
| IC | TI BQ35100 (TSSOP-14) |
| I2C Address | 0x55 (fixed) |
| I2C Clock | 8 kHz – 400 kHz |
| Supply | 2.45 – 4.5 V |
| Shutdown Current | 50 nA (GE=LOW) |
| Active Current | 130 µA (ACC), 40 µA (SOH), 315 µA peak (EOS) |
| Operating Temp | -40°C to +85°C |
| ADC Resolution | 15-bit (voltage and current) |
| Flash Retention | 10 years, 20,000 write cycles |

## Features Implemented

### Standard Sensor API Channels

| Channel | Type | Units | Description |
|---------|------|-------|-------------|
| `SENSOR_CHAN_GAUGE_VOLTAGE` | Standard | V (val1.val2) | Battery voltage (0–5V) |
| `SENSOR_CHAN_VOLTAGE` | Standard | V (val1.val2) | Alias for gauge voltage |
| `SENSOR_CHAN_GAUGE_AVG_CURRENT` | Standard | mA (val1) | Discharge current (signed, 1mA resolution) |
| `SENSOR_CHAN_CURRENT` | Standard | mA (val1) | Alias for gauge current |
| `SENSOR_CHAN_GAUGE_TEMP` | Standard | °C (val1.val2) | External NTC or internal temp (see OpCfgA TEMPS bit) |
| `SENSOR_CHAN_GAUGE_STATE_OF_HEALTH` | Standard | % (val1) | SOH percentage (0–100) |
| `SENSOR_CHAN_GAUGE_REMAINING_CHARGE_CAPACITY` | Standard | Ah (val1.val2) | Accumulated capacity since GAUGE_START |

### Custom Channels (`SENSOR_CHAN_PRIV_START` + N)

| Channel | Units | Description |
|---------|-------|-------------|
| `SENSOR_CHAN_BQ35100_SOH` | % | State of Health (duplicate for convenience) |
| `SENSOR_CHAN_BQ35100_ACCUMULATED_CAP` | µAh (raw) | Raw accumulated capacity (32-bit) |
| `SENSOR_CHAN_BQ35100_IMPEDANCE` | mΩ | Cell impedance (EOS mode only) |
| `SENSOR_CHAN_BQ35100_SCALED_R` | mΩ | Scaled cell resistance (EOS mode only) |
| `SENSOR_CHAN_BQ35100_INTERNAL_TEMP` | °C | Internal die temperature (always available) |
| `SENSOR_CHAN_BQ35100_DESIGN_CAP` | mAh | Design capacity from data flash |
| `SENSOR_CHAN_BQ35100_BATTERY_STATUS` | flags | Raw BatteryStatus byte |
| `SENSOR_CHAN_BQ35100_BATTERY_ALERT` | flags | Raw BatteryAlert byte |
| `SENSOR_CHAN_BQ35100_CONTROL_STATUS` | flags | Raw CONTROL_STATUS word |

### Custom Attributes (via `sensor_attr_set`)

| Attribute | Description |
|-----------|-------------|
| `SENSOR_ATTR_BQ35100_GAUGE_START` | Enter active gauging mode |
| `SENSOR_ATTR_BQ35100_GAUGE_STOP` | Stop gauging (waits for G_DONE) |
| `SENSOR_ATTR_BQ35100_ENABLE` | Assert GE pin (power up) |
| `SENSOR_ATTR_BQ35100_DISABLE` | Deassert GE pin (shutdown) |
| `SENSOR_ATTR_BQ35100_UNSEAL` | Unseal with default keys |
| `SENSOR_ATTR_BQ35100_SEAL` | Seal device |
| `SENSOR_ATTR_BQ35100_NEW_BATTERY` | Reset for new battery |
| `SENSOR_ATTR_BQ35100_RESET` | Full device reset |

### Direct API Functions

```c
#include <corekinect/gauges/bq35100/bq35100.h>

int bq35100_enable(dev);              // Assert GE pin
int bq35100_disable(dev);             // Deassert GE pin
int bq35100_gauge_start(dev);         // Enter ACTIVE mode
int bq35100_gauge_stop(dev);          // Stop + wait G_DONE
int bq35100_control_cmd(dev, subcmd); // Send any control subcommand
int bq35100_control_read(dev, subcmd, &result); // Subcommand + read
int bq35100_get_control_status(dev, &status);   // CONTROL_STATUS
int bq35100_unseal(dev);              // Unseal with default keys
int bq35100_seal(dev);                // Seal device
int bq35100_new_battery(dev);         // Reset impedance data
int bq35100_df_read(dev, addr, buf, len);  // Read data flash (1-32 bytes)
int bq35100_df_write(dev, addr, data, len); // Write data flash (unsealed only)
```

### Shell Commands (CONFIG_CK_BQ35100_SHELL=y)

```
bq35100 read         — All sensor channels
bq35100 status       — Status flags, security mode, GE/gauge state
bq35100 info         — Device type, FW, HW version, chemistry
bq35100 start        — GAUGE_START
bq35100 stop         — GAUGE_STOP
bq35100 unseal       — Unseal with default keys
bq35100 seal         — Seal device
bq35100 new_battery  — Reset for new battery
bq35100 df_read ADDR [LEN] — Read data flash at hex address
```

### Register Coverage

| Register | Address | Implemented | Notes |
|----------|---------|-------------|-------|
| Control | 0x00 | Yes | Subcommand interface + CONTROL_STATUS |
| AccumulatedCapacity | 0x02 | Yes | 32-bit µAh, ACC mode |
| Temperature | 0x06 | Yes | External NTC or internal |
| Voltage | 0x08 | Yes | Battery voltage in mV |
| BatteryStatus | 0x0A | Yes | Status flags |
| BatteryAlert | 0x0B | Yes | Alert flags (clears ALERT pin) |
| Current | 0x0C | Yes | Signed mA |
| ScaledR | 0x16 | Yes | EOS mode resistance |
| MeasuredZ | 0x22 | Yes | EOS mode impedance |
| InternalTemperature | 0x28 | Yes | Die temperature |
| StateOfHealth | 0x2E | Yes | SOH percentage |
| DesignCapacity | 0x3C | Yes | From data flash |
| MAC/MACData | 0x3E-0x61 | Yes | Data flash R/W |
| Cal_Count/Current/Voltage/Temp | 0x79-0x7F | Exposed via DF | Calibration registers |

| Subcommand | Code | Implemented |
|------------|------|-------------|
| CONTROL_STATUS | 0x0000 | Yes |
| DEVICE_TYPE | 0x0001 | Yes (via MAC) |
| FW_VERSION | 0x0002 | Yes |
| HW_VERSION | 0x0003 | Yes |
| CHEM_ID | 0x0006 | Yes |
| BOARD_OFFSET | 0x0009 | Via control_cmd() |
| CC_OFFSET | 0x000A | Via control_cmd() |
| CC_OFFSET_SAVE | 0x000B | Via control_cmd() |
| GAUGE_START | 0x0011 | Yes (dedicated function) |
| GAUGE_STOP | 0x0012 | Yes (dedicated function) |
| SEALED | 0x0020 | Yes |
| CAL_ENABLE | 0x002D | Via control_cmd() |
| LT_ENABLE | 0x002E | Via control_cmd() |
| RESET | 0x0041 | Yes |
| EXIT_CAL | 0x0080 | Via control_cmd() |
| ENTER_CAL | 0x0081 | Via control_cmd() |
| NEW_BATTERY | 0xA613 | Yes |

**Any subcommand** can be sent via `bq35100_control_cmd(dev, code)`. The table above
shows which have dedicated wrappers vs using the generic interface.

## Devicetree Configuration

```dts
&i2c0 {
    bq35100: bq35100@55 {
        compatible = "ti,bq35100";
        reg = <0x55>;
        enable-gpios = <&gpio0 1 GPIO_ACTIVE_HIGH>;
        alert-gpios = <&gpio0 0 GPIO_ACTIVE_LOW>;     /* optional */
        design-capacity-mah = <2200>;                   /* default */
        gauging-mode = "accumulator";                   /* or "soh", "eos" */
        power-up-delay-ms = <250>;                      /* default */
    };
};
```

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `enable-gpios` | phandle-array | Yes | — | GE pin (active-high) |
| `alert-gpios` | phandle-array | No | — | ALERT pin (active-low, open-drain) |
| `design-capacity-mah` | int | No | 2200 | Battery design capacity (mAh) |
| `gauging-mode` | string | No | "accumulator" | "accumulator", "soh", or "eos" |
| `power-up-delay-ms` | int | No | 250 | Delay after GE assertion (ms) |

## Kconfig Options

| Option | Default | Description |
|--------|---------|-------------|
| `CONFIG_CK_BQ35100` | n | Enable BQ35100 driver |
| `CONFIG_CK_BQ35100_INIT_PRIORITY` | 90 | Init priority (after I2C) |
| `CONFIG_CK_BQ35100_LOG_LEVEL` | 3 | Log level (0=OFF, 4=DBG) |
| `CONFIG_CK_BQ35100_TRIGGER` | y | ALERT interrupt support |
| `CONFIG_CK_BQ35100_SHELL` | y | Shell commands |

## Directory Structure

```
bq35100_drv/
├── CMakeLists.txt
├── Kconfig
├── README.md
├── zephyr/module.yml
├── dts/bindings/gauge/
│   └── ti,bq35100.yaml
├── drivers/
│   ├── CMakeLists.txt
│   └── corekinect/gauges/bq35100/
│       ├── CMakeLists.txt
│       ├── bq35100.c          # Driver implementation (~1100 lines)
│       └── bq35100.h          # Public API + register definitions
├── samples/basic/
│   ├── CMakeLists.txt
│   ├── prj.conf
│   ├── sample.yaml
│   ├── boards/iwsck_a0_nrf54l15_cpuapp.overlay
│   └── src/main.c
└── tests/hardware/
    ├── CMakeLists.txt
    ├── prj.conf
    ├── testcase.yaml
    ├── boards/iwsck_a0_nrf54l15_cpuapp.overlay
    └── src/main.c             # 23 hardware-on-target tests
```

## Building

```bash
# Inside NCS v3.2.1 container
cd libs/zephyr/bq35100_drv/samples/basic

west build --pristine --no-sysbuild -b iwsck_a0/nrf54l15/cpuapp . \
  -- -DBOARD_ROOT=/workspace/libs/zephyr/ck_boards/current \
     -DDTS_ROOT=/workspace/libs/zephyr/ck_boards/current

nrfjprog --program build/zephyr/zephyr.hex \
  --chiperase --verify --reset \
  --snr <PROBE_SNR> -f NRF54L --clockspeed 4000
```

## Test Results (2026-03-20, IWSCK A0 Hardware)

```
SUITE PASS [bq35100_init]:         2/2  — device ready, device type via MAC
SUITE PASS [bq35100_i2c]:          5/5  — voltage, current, temp, design cap, status
SUITE PASS [bq35100_sensor_api]:   4/4  — fetch all, unsupported chan, generic chan, SOH
SUITE PASS [bq35100_lifecycle]:    3/3  — gauge start/stop, enable/disable, attr API
SUITE PASS [bq35100_data_flash]:   4/4  — device name, design cap, op config, invalid len
SUITE PASS [bq35100_consistency]:  2/2  — voltage stability (5 reads), die temp range
SUITE PASS [bq35100_alert]:        3/3  — trigger registration, unsupported trig, alert clear

Total: 23/23 PASS, 0 FAIL
```

## Known Limitations

1. **External temperature**: Reads -39°C when no NTC thermistor is connected (expected).
   Use `SENSOR_CHAN_BQ35100_INTERNAL_TEMP` for die temperature instead.
2. **DEVICE_TYPE via Control()**: Returns CONTROL_STATUS instead of device type on some
   FW revisions. Driver uses MAC-based read for reliable identification.
3. **Data flash writes**: Require device to be unsealed first. Flash has 20,000 write
   cycle limit — avoid frequent writes.
4. **SHA-1 authentication**: Not implemented as a sensor channel. Use `bq35100_control_cmd()`
   with the appropriate subcommands for battery authentication workflows.
5. **Calibration mode**: Available via `bq35100_control_cmd(dev, BQ35100_CNTL_ENTER_CAL)` but
   no dedicated calibration API. Use the shell + `df_read`/`df_write` for calibration procedures.

## Chip Assessment

See `ASSESSMENT.md` for a detailed evaluation of the BQ35100 for CoreKinect products.
