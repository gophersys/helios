# ICLE Super Monitor Tool - Architecture

## Overview

The ICLE (In-Circuit Loop-back Equipment) Super Monitor is an ESP32-WROOM-32 based test fixture designed for power consumption monitoring and DUT validation. The device operates primarily in deep sleep to conserve power, waking on button press to enter either Configuration mode or Logger mode.

## State Machine

```
                              +------------------+
                              |                  |
                              |   DEEP SLEEP     |<--------------------+
                              |   (Default)      |                     |
                              |                  |                     |
                              +--------+---------+                     |
                                       |                               |
                                       | BTN_WAKE (GPIO wakeup)        |
                                       v                               |
                              +------------------+                     |
                              |                  |                     |
                              |   BOOT_DECIDE    |                     |
                              |   (2 sec window) |                     |
                              |                  |                     |
                              +--------+---------+                     |
                                       |                               |
                  +--------------------+--------------------+          |
                  |                                         |          |
                  | BTN held < 2s                           | BTN held >= 2s
                  | (single press)                          | (long press)
                  v                                         v          |
         +------------------+                      +------------------+ |
         |                  |                      |                  | |
         |   CONFIG_MODE    |                      |   LOGGER_MODE    | |
         |   (WiFi STA)     |                      |   (Active log)   | |
         |                  |                      |                  | |
         +--------+---------+                      +--------+---------+ |
                  |                                         |          |
                  | Timeout (5 min)                         |          |
                  | or BTN double-press                     |          |
                  |                                         |          |
                  +-----------------------------------------+----------+
                                                            |
                                                            | BTN long press (3s)
                                                            | or critical error
                                                            |
                                                            v
                                                   +------------------+
                                                   |                  |
                                                   |    SHUTDOWN      |
                                                   |   (Cleanup)      |
                                                   |                  |
                                                   +------------------+
```

## Operating Modes

### Deep Sleep (Default)
- All peripherals powered down
- WiFi/BLE radio off
- Only RTC memory preserved
- Wake sources: GPIO button, RTC timer (optional periodic wake)
- Current consumption: ~10uA

### Boot Decide (Transition State)
- 2-second window to determine target mode
- LED indicates waiting state (slow blink)
- Monitors button state to determine mode
- Single press/release -> Config Mode
- Held for 2+ seconds -> Logger Mode

### Config Mode
- WiFi STA connects to configured network
- Device appears in Concord UI for configuration
- Allows setting: WiFi credentials, log sync URL, device ID, sample rate
- Configuration stored in NVS (non-volatile storage)
- Auto-timeout to deep sleep after 5 minutes of inactivity
- LED: Green solid when connected, green blink when connecting

### Logger Mode
- Active power monitoring mode
- Samples INA209 at configured rate (default 100ms)
- Always writes to SD card (primary storage)
- Maintains WiFi connection for sync
- Syncs logs to backend via HTTP POST when connected
- LED: Red blink indicates logging active
- Exit via long button press or critical error

## Module Architecture

```
+------------------------------------------------------------------+
|                         Application Layer                         |
|                                                                    |
|  +-------------------+  +-------------------+  +----------------+  |
|  |    icle_app.h     |  |   icle_button.h   |  |  icle_log.h    |  |
|  |  State machine    |  |  Button handler   |  | Log manager    |  |
|  |  Mode transitions |  |  Debounce/events  |  | Format/queue   |  |
|  +-------------------+  +-------------------+  +----------------+  |
|                                                                    |
+------------------------------------------------------------------+
                               |
+------------------------------------------------------------------+
|                        Service Layer                              |
|                                                                    |
|  +-------------------+  +-------------------+  +----------------+  |
|  |   icle_wifi.h     |  |  icle_storage.h   |  |  icle_http.h   |  |
|  |  WiFi STA mgmt    |  |  SD card storage  |  | HTTP client    |  |
|  |  Connect/status   |  |  File ops/rotate  |  | Log sync API   |  |
|  +-------------------+  +-------------------+  +----------------+  |
|                                                                    |
+------------------------------------------------------------------+
                               |
+------------------------------------------------------------------+
|                        Driver Layer                               |
|                                                                    |
|  +-------------------+  +-------------------+  +----------------+  |
|  |   icle_power.h    |  |   icle_gpio.h     |  | (Future BLE)   |  |
|  |  INA209 sensor    |  |  GPIO controls    |  |                |  |
|  |  Power readings   |  |  LEDs, MUX, FET   |  |                |  |
|  +-------------------+  +-------------------+  +----------------+  |
|                                                                    |
+------------------------------------------------------------------+
                               |
+------------------------------------------------------------------+
|                      Zephyr RTOS Layer                            |
|   kernel, drivers, networking, filesystem, power management       |
+------------------------------------------------------------------+
```

## Thread Model

All threads are created programmatically using `k_thread_create()` - no static macros.

| Thread          | Priority | Stack  | Description                              |
|-----------------|----------|--------|------------------------------------------|
| main            | 0        | 4096   | App init, state machine, mode control    |
| button_handler  | 5        | 1024   | GPIO interrupt -> work queue processing  |
| log_sampler     | 3        | 2048   | Periodic INA209 sampling (Logger mode)   |
| log_writer      | 4        | 2048   | SD card write from queue (Logger mode)   |
| http_sync       | 6        | 4096   | Background HTTP sync (Logger mode)       |
| led_status      | 7        | 512    | LED pattern driver                       |

### Thread Lifecycle

Threads are created/destroyed based on operating mode:

- **Always active**: main, button_handler, led_status
- **Logger mode only**: log_sampler, log_writer, http_sync
- **Config mode**: Uses main thread for HTTP server (if implemented)

### Synchronization Primitives

All created programmatically:

```c
// Queues
struct k_queue log_sample_queue;    // Samples from sampler -> writer
struct k_queue log_sync_queue;      // Files ready for HTTP sync

// Mutexes
struct k_mutex storage_mutex;       // SD card access
struct k_mutex wifi_mutex;          // WiFi state
struct k_mutex app_state_mutex;     // State machine

// Semaphores
struct k_sem wifi_connected_sem;    // WiFi connection signal
struct k_sem http_complete_sem;     // HTTP request complete

// Events
struct k_event button_events;       // Button press patterns
struct k_event app_events;          // Mode change signals
```

## Data Flow

### Logger Mode Data Flow

```
+------------+     +---------------+     +---------------+     +------------+
|  INA209    | --> | log_sampler   | --> | log_sample_   | --> | log_writer |
|  Sensor    |     | thread        |     | queue         |     | thread     |
+------------+     +---------------+     +---------------+     +-----+------+
                                                                     |
                                                                     v
+------------+     +---------------+     +---------------+     +------------+
|  Concord   | <-- | http_sync     | <-- | log_sync_     | <-- | SD Card    |
|  Backend   |     | thread        |     | queue         |     | Files      |
+------------+     +---------------+     +---------------+     +------------+
```

### Log Entry Format

```c
struct icle_log_entry {
    uint32_t timestamp_ms;     // Uptime in ms
    uint32_t rtc_time;         // RTC epoch if available
    int32_t  voltage_uv;       // Bus voltage (microvolts)
    int32_t  current_ua;       // Current (microamps)
    int32_t  power_uw;         // Power (microwatts)
    uint8_t  flags;            // Status flags
};
```

### SD Card File Format

- Directory: `/icle/logs/`
- Filename: `YYYYMMDD_HHMMSS.bin` (binary) or `.csv` (text)
- Max file size: 1MB, then rotate
- Retention: Delete oldest when SD < 10% free

## Configuration Storage (NVS)

```c
struct icle_config {
    char     wifi_ssid[33];
    char     wifi_psk[65];
    char     device_id[32];
    char     sync_url[128];
    uint32_t sample_interval_ms;
    uint32_t sync_interval_ms;
    uint8_t  log_format;        // Binary or CSV
    uint8_t  flags;
};
```

## Future BLE Considerations

ESP32 shares a single 2.4GHz antenna between WiFi and BLE. Considerations:

1. **Mutual Exclusion**: Only one radio active at a time
2. **Mode Handoff**:
   - Config mode could use BLE instead of WiFi for initial setup
   - BLE provisioning -> store WiFi credentials -> switch to WiFi
3. **Architecture Support**:
   - `icle_radio.h` abstraction layer
   - `icle_ble.h` for BLE-specific functionality
   - Radio mutex to prevent concurrent access
4. **State Machine Extension**:
   - BLE_CONFIG_MODE state (alternative to WiFi config)
   - Provisioning complete event triggers mode switch

### BLE Integration Points

```c
// Future radio abstraction
enum icle_radio_mode {
    ICLE_RADIO_OFF,
    ICLE_RADIO_WIFI,
    ICLE_RADIO_BLE,
};

int icle_radio_set_mode(enum icle_radio_mode mode);
```

## Error Handling

### Critical Errors (Trigger Shutdown)
- SD card mount failure in Logger mode
- Repeated WiFi connection failures (>10 retries)
- Memory allocation failure
- Watchdog timeout

### Recoverable Errors
- Single HTTP sync failure (retry with backoff)
- WiFi disconnect (auto-reconnect)
- Single sensor read failure (skip sample)

### LED Error Patterns
- Red solid: Critical error
- Red fast blink: Recoverable error
- Red slow blink: Warning

## Power Management

### Deep Sleep Entry
1. Flush pending log writes
2. Complete or cancel HTTP sync
3. Disconnect WiFi gracefully
4. Save state to RTC memory
5. Configure wake sources
6. Enter deep sleep

### Wake Sources
- GPIO: Button press
- Timer: Optional periodic wake for sensor check

### RTC Memory Preserved Data
```c
struct icle_rtc_state {
    uint8_t  last_mode;
    uint32_t boot_count;
    uint32_t last_sync_time;
    uint32_t pending_samples;
};
```

## API Summary

See individual header files in `include/` for complete API documentation:

- `icle_app.h` - Application state machine and mode control
- `icle_power.h` - Power measurement (existing driver layer)
- `icle_wifi.h` - WiFi station management
- `icle_storage.h` - SD card log storage
- `icle_log.h` - Log manager and formatting
- `icle_button.h` - Button input handling
- `icle_http.h` - HTTP client for backend sync
