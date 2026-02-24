# ICLE Super Monitor - Zephyr Firmware

ESP32-WROOM-32 based power monitoring and logging tool for DUT validation.

## Quick Start

### Prerequisites
- Use the **Zephyr v4.0 devcontainer**: `concord-devcontainer-zephyr:v4.0`
- Or build it: `nx run devcontainer-zephyr-v4.0:build`

### Build
```bash
cd /workspaces/concord/apps/firmware/icle/icle_zephyr
west build -b esp32_devkitc_wroom/procpu
```

### Flash
```bash
west flash
# Or with esptool directly:
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash 0x0 build/zephyr/zephyr.bin
```

### Monitor
```bash
west espressif monitor
# Or:
screen /dev/ttyUSB0 115200
```

---

## Network Credentials

Default WiFi configuration (from legacy ICLE firmware):
```
SSID:     CoreKinect_2G
Password: Trap101!
```

To configure at runtime, use Config Mode (see Operating Modes below).

---

## Hardware: ICLE v1.0

### MCU
- **ESP32-WROOM-32** (Xtensa LX6 dual-core, 240MHz, 4MB flash, 520KB SRAM)

### Peripherals
| Peripheral | Interface | Address/Pin | Description |
|------------|-----------|-------------|-------------|
| INA209 | I2C0 | 0x40 | Power/current monitor (bus voltage, shunt current) |
| SD Card | SPI2 (VSPI) | GPIO5 (CS) | FAT filesystem for log storage |
| Status LED | GPIO | GPIO4 | User feedback |
| Wake Button | GPIO | GPIO0 (BOOT) | Wake from deep sleep, mode selection |
| MUX Control | GPIO | GPIO15, GPIO2, GPIO23 | 3-bit channel select |
| P-FET Gate | GPIO | GPIO19 | DUT power control |
| ADC Inhibit | GPIO | GPIO32 | ADC control |

### Pin Mapping
```
GPIO0  - BOOT button (wake source, active low)
GPIO2  - MUX bit 1
GPIO4  - Status LED
GPIO5  - SD Card CS
GPIO12 - SPI2 MISO
GPIO13 - SPI2 MOSI
GPIO14 - SPI2 CLK
GPIO15 - MUX bit 0
GPIO19 - P-FET gate
GPIO21 - I2C0 SDA
GPIO22 - I2C0 SCL
GPIO23 - MUX bit 2
GPIO32 - ADC inhibit
```

---

## Operating Modes

### State Machine
```
                    +-----------------+
                    |   DEEP SLEEP    |<------------------+
                    |   (Default)     |                   |
                    +--------+--------+                   |
                             |                            |
                             | Button press (GPIO0)       |
                             v                            |
                    +-----------------+                   |
                    |  BOOT_DECIDE    |                   |
                    |  (2 sec window) |                   |
                    +--------+--------+                   |
                             |                            |
            +----------------+----------------+           |
            |                                 |           |
            | Short press (<2s)               | Long press (>=2s)
            v                                 v           |
    +-----------------+              +-----------------+  |
    |  CONFIG_MODE    |              |  LOGGER_MODE    |  |
    |  (WiFi STA)     |              |  (Active log)   |  |
    |  5 min timeout  |              |  SD + HTTP sync |  |
    +--------+--------+              +--------+--------+  |
            |                                 |           |
            | Timeout/double press            | Long press (3s)
            +---------------------------------+-----------+
```

### Mode Details

| Mode | Entry | LED Pattern | Description |
|------|-------|-------------|-------------|
| **Deep Sleep** | Default / timeout | Off | ~10uA consumption, GPIO wake enabled |
| **Boot Decide** | Button press | Slow blink | 2-second window to determine mode |
| **Config Mode** | Short press (<2s) | Green solid/blink | WiFi STA, Concord UI access, 5-min idle timeout |
| **Logger Mode** | Long press (>=2s) | Red blink | Active power sampling, SD write, HTTP sync |
| **Shutdown** | 3s hold / critical error | Fast blink | Graceful shutdown sequence |

---

## Module Architecture

```
+------------------------------------------------------------------+
|                         Application Layer                         |
|  icle_app.h (state machine) | icle_button.h | icle_log.h         |
+------------------------------------------------------------------+
|                         Service Layer                             |
|  icle_wifi.h | icle_storage.h | icle_http.h                      |
+------------------------------------------------------------------+
|                         Driver Layer                              |
|  icle_power.h (INA209) | icle_gpio.h (LEDs, MUX, FET)            |
+------------------------------------------------------------------+
|                      Zephyr RTOS Layer                            |
+------------------------------------------------------------------+
```

### Source Files

| File | Description |
|------|-------------|
| `src/main.c` | Main state machine, mode transitions, thread lifecycle |
| `src/icle_wifi.c` | WiFi STA connection, reconnection with backoff |
| `src/icle_power_mgmt.c` | Deep sleep, RTC memory, idle timers |
| `src/icle_button.c` | Debounce, short/long/double press detection |
| `src/icle_log.c` | Sample queue, SD persistence, CSV/binary format |
| `src/services/icle_storage.c` | SD card mount, file rotation, sync tracking |
| `src/services/icle_http.c` | REST client, log upload, config fetch |
| `src/drivers/icle_gpio.c` | LED, MUX channel, P-FET control |
| `src/drivers/icle_power.c` | INA209 sensor driver wrapper |

### Headers

| File | Description |
|------|-------------|
| `include/icle_app.h` | App states, events, config structure |
| `include/icle_wifi.h` | WiFi API, callbacks, status |
| `include/icle_power_monitor.h` | Power management, sleep, RTC state |
| `include/icle_storage.h` | SD card API, file operations |
| `include/icle_log.h` | Log entry format, sampling control |
| `include/icle_button.h` | Button events, timing config |
| `include/icle_http.h` | HTTP client, sync API |

---

## Thread Model

All threads created programmatically with `k_thread_create()` (no K_THREAD_DEFINE macros).

| Thread | Priority | Stack | Active In | Description |
|--------|----------|-------|-----------|-------------|
| main | 0 | 4096 | Always | State machine, mode control |
| button_handler | 5 | 1024 | Always | GPIO interrupt processing |
| led_status | 7 | 512 | Always | LED pattern driver |
| log_sampler | 3 | 2048 | Logger only | INA209 periodic sampling |
| log_writer | 4 | 2048 | Logger only | SD card queue drain |
| http_sync | 6 | 4096 | Logger only | Background HTTP upload |

---

## Data Formats

### Log Entry (Binary)
```c
struct icle_log_entry {
    uint32_t timestamp_ms;     // Uptime in ms
    uint32_t rtc_time;         // RTC epoch (if available)
    int32_t  voltage_uv;       // Bus voltage (microvolts)
    int32_t  current_ua;       // Current (microamps)
    int32_t  power_uw;         // Power (microwatts)
    uint8_t  flags;            // Status flags
};
```

### Log Entry (CSV)
```csv
timestamp_ms,rtc_time,voltage_uv,current_ua,power_uw,flags
12345,1707753600,3300000,15000,49500,0
```

### SD Card Structure
```
/SD:/icle/
├── logs/
│   ├── 20260212_183045.bin
│   ├── 20260212_184532.csv
│   └── ...
└── .synced/
    └── <marker files for synced logs>
```

---

## Configuration

### Device Config (NVS)
```c
struct icle_config {
    char     wifi_ssid[33];        // WiFi SSID
    char     wifi_psk[65];         // WiFi password
    char     device_id[32];        // Unique device identifier
    char     sync_url[128];        // Backend API URL
    uint32_t sample_interval_ms;   // Sampling rate (default: 100ms)
    uint32_t sync_interval_ms;     // HTTP sync interval (default: 60s)
    uint8_t  log_format;           // 0=binary, 1=CSV
    uint8_t  flags;                // Config flags
};
```

### Kconfig Options (prj.conf)
Key configurations enabled:
- `CONFIG_WIFI=y` - WiFi support
- `CONFIG_NET_SOCKETS=y` - BSD sockets for HTTP
- `CONFIG_FILE_SYSTEM=y` + `CONFIG_FAT_FILESYSTEM_ELM=y` - SD card
- `CONFIG_PM=y` - Power management / deep sleep
- `CONFIG_SENSOR=y` - INA209 sensor
- `CONFIG_EVENTS=y` - Event-driven state machine

---

## Concord Backend Integration

### API Endpoints (expected)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/icle/logs` | Upload log file (JSON with hex data) |
| GET | `/api/icle/devices/{id}/config` | Fetch device configuration |
| PUT | `/api/icle/devices/{id}/config` | Update device configuration |
| POST | `/api/icle/devices/register` | Register new device |
| GET | `/api/health` | Health check / ping |

### Log Upload Format
```json
{
  "device_id": "icle-001",
  "filename": "20260212_183045.bin",
  "format": "binary",
  "data": "<hex-encoded binary data>"
}
```

---

## Testing

### Twister (Zephyr Test Framework)
```bash
# Run all ICLE tests
west twister -p esp32_devkitc_wroom/procpu -T apps/firmware/icle/icle_zephyr/tests/

# Specific test suite
west twister -p esp32_devkitc_wroom/procpu -s icle.boot.mode_selection
```

### Recommended Test Categories
1. **Boot tests** - Deep sleep wake, mode selection
2. **WiFi tests** - STA connect, reconnection
3. **Storage tests** - SD mount, file rotation
4. **Sensor tests** - INA209 readings
5. **Integration tests** - Full mode cycles

---

## Future Enhancements

### BLE Support
The architecture is designed for future BLE integration:
- Radio abstraction layer for WiFi/BLE mutual exclusion
- BLE provisioning mode for initial WiFi setup
- BLE characteristic notifications for real-time data

### Alpha Device Pairing
Planned feature for pairing with Alpha DUT over BLE:
- BLE GATT client for Alpha connection
- Characteristic subscribe for sensor data
- Mode switch: BLE collection -> WiFi upload

---

## Troubleshooting

### Build Errors
```bash
# Clean build
rm -rf build/
west build -b esp32_devkitc_wroom/procpu --pristine
```

### WiFi Connection Issues
- Check credentials in Config Mode
- Verify 2.4GHz network (ESP32 doesn't support 5GHz)
- Check serial output for connection logs

### SD Card Not Mounting
- Verify SD card is FAT32 formatted
- Check SPI wiring (GPIO5 CS, GPIO12/13/14 for data)
- Ensure `CONFIG_DISK_DRIVER_SDMMC=y` in prj.conf

### Deep Sleep Not Working
- Verify GPIO0 is configured as wake source
- Check `CONFIG_PM=y` and `CONFIG_PM_DEVICE=y`
- Monitor RTC memory state via serial before sleep

---

## File Tree
```
apps/firmware/icle/icle_zephyr/
├── CMakeLists.txt
├── prj.conf
├── README.md                    # This file
├── docs/
│   └── ARCHITECTURE.md          # Detailed architecture doc
├── include/
│   ├── icle_app.h
│   ├── icle_button.h
│   ├── icle_http.h
│   ├── icle_log.h
│   ├── icle_power_monitor.h
│   ├── icle_storage.h
│   └── icle_wifi.h
├── src/
│   ├── main.c                   # State machine
│   ├── icle_button.c
│   ├── icle_log.c
│   ├── icle_power_mgmt.c
│   ├── icle_wifi.c
│   ├── drivers/
│   │   ├── icle_gpio.c
│   │   ├── icle_gpio.h
│   │   ├── icle_power.c
│   │   └── icle_power.h
│   └── services/
│       ├── icle_http.c
│       └── icle_storage.c
├── boards/
│   └── esp32_devkitc_wroom_procpu.overlay
└── tests/                       # (TODO: Add Twister tests)
```

---

## References

- [Zephyr ESP32 Guide](https://docs.zephyrproject.org/latest/boards/espressif/esp32_devkitc_wroom/doc/index.html)
- [INA209 Datasheet](https://www.ti.com/lit/ds/symlink/ina209.pdf)
- [ICLE v1.0 Schematic](../../hw/ICLE%20v1.0.kicad_sch)
- [Architecture Document](docs/ARCHITECTURE.md)
