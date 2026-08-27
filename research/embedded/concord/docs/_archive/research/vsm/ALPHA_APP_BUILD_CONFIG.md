# Alpha B0 Application Build Configuration - VSM Analysis

Analysis of the Alpha wearable manufacturing firmware (`_fw_build/`) targeting the Alpha B0 hardware platform (nRF52840 application processor + nRF9151 communications coprocessor).

---

## 1. Application Architecture

### Project Identity

- **CMake project name**: `theta_mfg_nrf52840`
- **Firmware Application ID**: 111 (Kconfig `APP_CORE_FW_APP_ID`)
- **Version**: 0.1.1 (manufacturing build, `IS_MANUFACTURING = 1`)
- **Zephyr RTOS** on Nordic nRF52840 (Cortex-M4F)

### Thread Map

The application instantiates the following threads, listed by priority (lower number = higher priority):

| Thread | Priority | Stack Size | Source File | Role |
|--------|----------|------------|-------------|------|
| BLE thread | 3 (`CONFIG_BLE_THREAD_PRIORITY`) | (Zephyr default) | `ble_handler.c` | Bluetooth LE advertising, MAC address management |
| Shell thread | 5 (`CONFIG_SHELL_THREAD_PRIORITY`) | 8192 B | Zephyr shell subsystem | Manufacturing UART shell (7-second timeout) |
| App thread | 7 (`CONFIG_APP_THREAD_PRIORITY`) | 8192 B | `app.c` | Main application loop: coordinates all handlers |
| Lights handler | 8 (`CONFIG_LIGHTS_THREAD_PRIORITY` / `LIGHTS_THREAD_PRIORITY`) | 1024 B | `lights_handler.c`, `alpha_lights.c` | Status LED + LP5814 charge LED control |
| Flash eraser | 9 (`CONFIG_FLASH_ERASER_THREAD_PRIORITY`) | 1024 B | `fuota_eraser.c` | Background external flash erase for FUOTA |
| Vibrator | 9 (hardcoded) | 512 B | `platform/vibrator.c` | PWM vibration motor pattern engine |
| **VSM vitals thread** | **(set by VSM driver)** | **(set by VSM driver)** | `vsm_drv/` (external module) | PPG acquisition, heart rate, SpO2, skin detection |

Additionally, the `main()` thread (in `main.c`) simply logs "Hi" and sleeps forever -- all real work happens in the statically-defined `app_thread`.

### App Thread Main Loop

The app thread (`app.c`) is the central coordinator. After initialization, it enters an infinite loop that calls these handlers in sequence each iteration:

```
init sequence:
  init_restart_handler()
  init_ipc_handling()
  init_hw_failure_handler()
  start_shell_timer()                 -- 7-second manufacturing shell window
  ipc_set_fw_version()
  init_fuota()
  init_sensor_handler()               -- IMU motion, charger, battery, BME280
  init_assembly_detect()              -- I2C bus scan for VSM + membrane
  init_button_handler()
  init_motion_state_machine(1, 10, 60)
  init_vsm_handler()                  -- VSM driver init (PPG, IMU, IR temp)
  ble_init()
  init_watchdog_handler()             -- 75-second WDT
  init_gps_handler()

main loop (each iteration):
  1. handle_app_ipc()                 -- process IPC messages from nRF9151
  2. handle_personalization_events()  -- IPC key rotation
  3. run_button_handler()             -- button press patterns (2/3/4/7 presses)
  4. run_gps_handler()                -- GPS position acquisition
  5. run_sensor_handler()             -- battery, charger, BME280, IMU connectivity
  6. run_motion_state_machine()       -- motion detection state machine
  7. run_vsm_handler()                -- process VSM vitals callbacks
  8. run_fuota_handler()              -- firmware update download
  9. run_hw_failure_handler()         -- hardware failure reporting
  10. handle_pending_restart()        -- reboot orchestration
  11. feed_watchdog()                 -- WDT feed (75s timeout)
  12. handle_theta_lights()           -- LED status updates
  13. heartbeat position (hourly)
  14. sleep (30ms if events pending, K_FOREVER otherwise)
```

### SYS_INIT Boot Order

Several modules initialize via Zephyr `SYS_INIT` before the app thread starts:

| Init Function | Phase | Priority | Module |
|---------------|-------|----------|--------|
| `init_hw_failure_before_drivers` | POST_KERNEL | KERNEL_INIT_PRIORITY_OBJECTS | hw_failure_handler.c |
| `led_init` | POST_KERNEL | KERNEL_INIT_PRIORITY_DEVICE | platform/led.c |
| `lights_handler_initialize` | POST_KERNEL | KERNEL_INIT_PRIORITY_DEVICE | lights_handler.c |
| `emer_button_init` | POST_KERNEL | KERNEL_INIT_PRIORITY_DEVICE | platform/emer_button.c |
| `init_charger_gpios` | POST_KERNEL | KERNEL_INIT_PRIORITY_DEVICE | charger_handler.c |
| `set_bus_mutexes` | POST_KERNEL | KERNEL_INIT_PRIORITY_DEFAULT | sensor_handler.c |
| `vibrator_init` | APPLICATION | KERNEL_INIT_PRIORITY_DEVICE | platform/vibrator.c |
| `init_key_handler` | APPLICATION | 0 | personalization.c |
| `restore_comm_coproc_data` | APPLICATION | 88 | alpha_mfg_persistent_data.c |

---

## 2. VSM Configuration in prj.conf

### VSM Driver and Dependencies

```kconfig
# VSM driver (vital signs monitoring)
CONFIG_CK_MODULES_VSM=y              # Enable the CK VSM driver module
CONFIG_CK_MODULES_VSM_TESTS_ENABLED=y # Enable VSM manufacturing tests (crosstalk)
CONFIG_FPU=y                          # FPU required for VSM signal processing

# Pixart PAH8151 PPG sensor driver
CONFIG_CK_PAH8151=y                   # Enable PAH8151 PPG driver
CONFIG_CK_PAH8151_BUS_MUTEX=y         # Thread-safe I2C access via bus mutex

# LSM6DSO IMU (accelerometer + gyroscope)
CONFIG_SENSOR=y                       # Zephyr sensor subsystem
CONFIG_CK_LSM6DSO=y                   # CK custom LSM6DSO driver
CONFIG_CK_LSM6DSO_BUS_MUTEX=y         # Thread-safe SPI access via bus mutex

# MLX90614 IR temperature sensor
CONFIG_CK_MLX90614=y                  # IR temp sensor for skin temperature

# LED controller (LP5814 on I2C for charge LEDs)
CONFIG_LED_CTRL_DRV=y
CONFIG_LED_LP5814_DRV=y
CONFIG_LED_CTRL_BUS_MUTEX=y
CONFIG_LED_CTRL_DRV_LOG_LEVEL=0       # Logging disabled for LED driver
```

### VSM Handler Runtime Configuration (`vsm_handler.c`)

The VSM driver is initialized with these compile-time and runtime parameters:

```c
static const vsm_config_t _vitals_config = {
    // Hardware device handles (from device tree)
    .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
    .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
    .p_temp_dev = DEVICE_DT_GET(DT_NODELABEL(mlx90614)),
    .p_ppg_enable_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(vsm_enable), gpios),

    // Callback for vitals data
    .callback = handle_vitals_callback,

    // Skin detection parameters
    .skin_temp_min_threshold_f = 75.0f,     // Min skin temp (Fahrenheit) for on-body
    .skin_temp_max_threshold_f = 100.0f,    // Max skin temp (Fahrenheit) for on-body
    .skin_detection_period_ms = 6000,       // Time to confirm skin contact
    .deskin_detection_period_ms = 6000,     // Time to confirm skin removal
};
```

### VSM State Machine (Callback Events)

The VSM driver invokes the application callback with these events:

| Event | Action |
|-------|--------|
| `VITALS_EVENT_STATE_CHANGED` / `VITALS_STATE_IDLE` | Log only |
| `VITALS_EVENT_STATE_CHANGED` / `VITALS_STATE_TOUCH_DETECTED` | Begin skin detection |
| `VITALS_EVENT_STATE_CHANGED` / `VITALS_STATE_SKIN_CONFIRMED` | Call `vsm_activate_monitoring()` |
| `VITALS_EVENT_STATE_CHANGED` / `VITALS_STATE_ACTIVE_MONITORING` | Set on-body flag, enable ECT calc |
| `VITALS_EVENT_STATE_CHANGED` / `VITALS_STATE_TOUCH_LOST` | Begin deskin detection |
| `VITALS_EVENT_STATE_CHANGED` / `VITALS_STATE_DESKIN_CONFIRMED` | Clear on-body flag, stop ECT timer |
| `VITALS_EVENT_METRICS_UPDATED` | Process HR, SpO2, skin temperature |
| `VITALS_EVENT_HW_ERROR` | Deinit VSM, retry in 5 seconds |
| `VITALS_EVENT_PSP_ERROR` | Deinit VSM, set PSP error flag, retry in 5 seconds |

### VSM Data Output

The VSM handler produces a `vsm_data_t` structure:

```c
typedef struct vsm_data {
    int16_t heartrate;                // BPM
    uint8_t heartrate_confidence;     // 0-100% (quality * 25)
    int16_t spo2;                     // Percentage
    uint8_t spo2_confidence;          // 0-100% (quality * 25)
    int16_t skin_temp_degC_q8p8;      // Q8.8 fixed-point Celsius
    uint8_t heat_strain_index_tenths; // aPSI * 10
    int16_t est_core_temp_degC_q8p8;  // Q8.8 fixed-point Celsius (Kalman filter)
} vsm_data_t;
```

### Derived Metrics

- **Estimated Core Temperature (ECT)**: Extended Kalman filter using heart rate, recalculated every 60 seconds. Initial state: 37.0 degC. Parameters: gamma=0.022^2, b0=-7887.1, b1=384.4286, b2=-4.5714, sigma=18.88^2.
- **Adaptive Physiological Strain Index (aPSI)**: Calculated from ECT, skin temp, and heart rate. Uses HR_REST=65, HR_CRITICAL=180.

### Other Sensor CONFIG_ Options

```kconfig
# Environmental sensor (BME280)
CONFIG_BME280_DRV=y

# GPS
CONFIG_UBLOX_M10_GPS_DRV=y
CONFIG_UBLOX_Mxx_GPS_DRV_I2C=y

# Battery charger (BQ25622)
CONFIG_BQ25622_CHARGER=y
CONFIG_BATTERY_CHARGE_CV_MIN_CURRENT_CUTOFF_mA=20
CONFIG_BATTERY_CHARGING_CURRENT_LIMIT_mA=480
CONFIG_BATTERY_MAX_VOLTAGE_mV=4480
CONFIG_BAT_CHARGE_HIGH_BMS_TEMP_THRESHOLD=42
CONFIG_BAT_CHARGE_LOW_TEMP_THRESHOLD=10
CONFIG_CHARGER_ENABLE_TS_IGNORE=y     # Ignore thermistor, use BMS temp instead

# Battery management system (MAX17263)
CONFIG_MAXIM_BMS_DRV=y
CONFIG_BMS_LIPO=y
CONFIG_BMS_BATTERY_CAPACITY=770       # 770 mAh
CONFIG_BMS_BATTERY_VEMPTY=350         # 3.50V empty threshold
CONFIG_BMS_ICHGTERM=128               # 128mA charge termination
CONFIG_BMS_CHARGE_ABOVE_4p2V=y        # Allow charging above 4.2V

# NFC
CONFIG_NFC_DRV=y

# Crypto (for IPC encryption)
CONFIG_CK_CRYPTO=y
CONFIG_CK_CRYPTO_WOLFCRYPT=y
CONFIG_WOLFCRYPT=y

# BLE
CONFIG_BT=y
CONFIG_BT_OBSERVER=y
CONFIG_BT_EXT_ADV=y
CONFIG_BT_PERIPHERAL=y
CONFIG_BT_DEVICE_NAME="Alpha Device"
CONFIG_BT_DEVICE_APPEARANCE=840
CONFIG_BT_SETTINGS=y
CONFIG_BT_CTLR_TX_PWR_DYNAMIC_CONTROL=y
CONFIG_BT_CTLR_ADV_DATA_LEN_MAX=128
CONFIG_BT_RX_STACK_SIZE=4096
```

---

## 3. Device Tree - Sensor Bus Bindings

### Bus Topology

```
nRF52840
  |
  +-- SPI0 (1 MHz) --+-- W25Q64JVIQ external flash (CS: P1.09)
  |                   +-- LSM6DSO IMU/accel (CS: P0.08)
  |
  +-- I2C1 (400 kHz Fast Mode) --+-- u-blox MIA-M10 GPS (0x42)
  |                               +-- BQ25622 charger (0x6B)
  |                               +-- MAX17263 BMS (0x36)
  |                               +-- BME280 env sensor (0x76) [overlay]
  |                               +-- LP5814 LED ctrl (0x2C) [overlay]
  |                               +-- PAH8151 PPG (0x15) [overlay]
  |
  +-- GPIO I2C (bit-bang, 100 kHz) --+-- MLX90614 IR temp (0x5A) [overlay]
  |     SCL: P1.04, SDA: P1.06
  |
  +-- UART0 (115200) -- Debug/shell console
  |     TX: P0.23, RX: P0.25
  |
  +-- UART1/LPUART (460800) -- IPC to nRF9151
  |     TX: P0.28, RX: P0.03, REQ: P0.29, RDY: P0.30
  |
  +-- PWM0 -- Vibration motor
        OUT: P1.07
```

### VSM-Specific Device Tree Nodes

#### PAH8151 PPG Sensor (I2C1 overlay: `alpha_b0_nrf52840.overlay`)

```dts
pah8151: pah8151@15 {
    compatible = "pixart,pah8151";
    reg = <0x15>;
    irq-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;    /* PPG.INT1 - P0.20 */
    int1-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;
    int2-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;    /* Same pin (single INT) */
    int-pin = <1>;
    led-current-ir = <255>;                        /* Maximum IR LED current */
    led-current-red = <255>;                       /* Maximum Red LED current */
    led-current-green = <255>;                     /* Maximum Green LED current */
};
```

All three LED channels are set to maximum current (255). Only one interrupt pin is physically connected (P0.20), used for both INT1 and INT2.

#### LSM6DSO IMU (SPI0, base DTS)

```dts
lsm6dso0: lsm6dso0@1 {
    compatible = "ck,lsm6dso";
    reg = <1>;                                     /* SPI CS index 1 */
    int-pin = <2>;                                 /* Use INT2 */
    spi-max-frequency = <1000000>;                 /* 1 MHz SPI */
    irq-gpios = <&gpio0 14 GPIO_ACTIVE_HIGH>;     /* INT pin P0.14 */
    accel-pm = <1>;       /* LSM6DSO_DT_LP_NORMAL_MODE */
    accel-range = <3>;    /* LSM6DSO_DT_FS_8G */
    accel-odr = <3>;      /* LSM6DSO_DT_ODR_52HZ */
    gyro-pm = <1>;        /* LSM6DSO_DT_GY_NORMAL_MODE */
    gyro-range = <0>;     /* LSM6DSO_DT_GY_FS_250DPS */
    gyro-odr = <2>;       /* LSM6DSO_DT_GY_ODR_26HZ */
    drdy-pulsed;
};
```

Key settings for VSM:
- **Accelerometer**: 52 Hz ODR, +/-8g range, normal power mode
- **Gyroscope**: 26 Hz ODR, +/-250 DPS range, normal power mode
- **Interrupt**: INT2 on P0.14, pulsed data-ready
- **Bus**: SPI at 1 MHz (shared with external flash via bus mutex)

#### MLX90614 IR Temperature Sensor (GPIO-I2C overlay)

```dts
ir_i2c: ir_i2c {
    compatible = "gpio-i2c-fast";
    clock-frequency = <100000>;    /* 100 kHz */
    cpu-frequency = <64000000>;    /* 64 MHz (nRF52840) */
    scl-gpios = <&gpio1 4 (GPIO_ACTIVE_HIGH | GPIO_PULL_UP)>;
    sda-gpios = <&gpio1 6 (GPIO_ACTIVE_HIGH | GPIO_PULL_UP)>;

    mlx90614: mlx90614@5a {
        compatible = "melexis,mlx90614";
        reg = <0x5a>;
        emissivity = <65535>;      /* Maximum emissivity (1.0) */
    };
};
```

The MLX90614 is on a dedicated bit-banged GPIO-I2C bus, separate from the main I2C1 bus. This avoids clock-stretching issues and bus contention with other I2C peripherals.

#### VSM Enable GPIO

```dts
vsm_enable: vsm_enable {
    gpios = <&gpio1 10 GPIO_ACTIVE_HIGH>;
    label = "VSM Enable / PPG en";
};
```

GPIO P1.10 controls power to the PPG sensor module. The VSM driver uses this via the `DT_ALIAS(vsm_enable)` alias.

---

## 4. Memory Layout

### Internal Flash (1 MB, nRF52840)

| Partition | Address | Size | Description |
|-----------|---------|------|-------------|
| `boot_partition` (MCUboot) | 0x00000 | 48 KB (0xC000) | Bootloader |
| `slot0_partition` (image-0) | 0x0C000 | 844 KB (0xD3000) | Active application firmware |
| `personalization` | 0xDF000 | 4 KB (0x1000) | IPC encryption key storage |
| `psp_lib` | 0xE0000 | 80 KB (0x14000) | **PSP (Pixart Signal Processing) library binary** |
| `settings_storage` | 0xF4000 | 36 KB (0x9000) | BLE settings, NVS |
| `fuota_metadata` | 0xFD000 | 8 KB (0x2000) | FUOTA download tracking bitmap |
| `persistent_data` | 0xFF000 | 4 KB (0x1000) | Boot flags, exception counter |

### External Flash (8 MB, W25Q64JVIQ on SPI0)

| Partition | Address | Size | Description |
|-----------|---------|------|-------------|
| `slot1_partition` (image-1) | 0x00000 | 848 KB (0xD4000) | MCUboot secondary slot (OTA image) |
| `external_flash` (remaining) | 0xD1000 | 7.2 MB (0x72F000) | Available for other use |

### pm_static.yml Partition Manager

The `pm_static.yml` file defines a `nonsecure_storage` span from 0xE0000 with size 0x20000 (128 KB) that encompasses:
- personalization (4 KB)
- psp_lib (80 KB)
- fuota_metadata (8 KB)
- settings_storage (36 KB)
- persistent_data (4 KB)

### PSP Library Placement

The PSP (Pixart Signal Processing) library is a **pre-compiled binary** (`vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex`) that gets merged into the final hex file at the `psp_lib` partition address (0xE0000). This is done via:

```bash
mergehex -m build/merged.hex vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex -o build/merged.hex
```

The PSP library occupies 80 KB of internal flash and is loaded by the VSM driver at runtime from this fixed partition address.

### RAM Usage

The nRF52840 has 256 KB of SRAM. Key stack allocations:

| Consumer | Size |
|----------|------|
| App thread stack | 8192 B |
| Shell thread stack | 8192 B |
| BLE RX stack | 4096 B |
| System workqueue stack | 4096 B |
| Log buffer | 4096 B |
| Lights handler stack | 1024 B |
| Flash eraser stack | 1024 B |
| Alpha lights stack | 1024 B |
| Vibrator stack | 512 B |
| VSM vitals thread | (defined in vsm_drv module) |

---

## 5. Thread Priorities

Zephyr uses a preemptive priority scheduler where **lower numbers = higher priority**.

```
Priority 3:  BLE thread           -- Highest app-level priority
Priority 5:  Shell thread         -- Manufacturing shell responsiveness
Priority 7:  App thread           -- Main application loop (K_ESSENTIAL)
Priority 8:  Lights handler       -- LED update thread
Priority 9:  Flash eraser         -- Background FUOTA erase
Priority 9:  Vibrator thread      -- PWM vibration patterns
Priority ?:  VSM vitals thread    -- Set by VSM driver module (not visible here)
```

The VSM thread priority is configured inside the `vsm_drv` Zephyr module and is not directly visible in the application Kconfig. However, the VSM driver communicates with the app thread via a callback function (`handle_vitals_callback`) which sets trigger flags and calls `wakeup_app()`. This means the VSM thread runs independently and wakes the app thread (priority 7) when new data is available.

The callback pattern means the VSM thread likely runs at a priority higher than 7 (the app thread) so it can preempt the app loop to deliver time-critical PPG data. The app thread then processes VSM events in its next iteration.

### Watchdog

The watchdog timer (`wdt0`) is configured with a 75-second timeout and resets the SoC on expiry. The app thread feeds it every iteration.

---

## 6. Build Variants

### Board Target

The only board target is `alpha_b0/nrf52840`. The build system uses:

```bash
west build -b alpha_b0/nrf52840 --sysbuild <workspace> -- -DBOARD_ROOT=<workspace>/ck_boards/current/
```

Custom board definitions live in `ck_boards/current/boards/corekinect/alpha_b0/`.

### Assembly Build Kconfig Option

```kconfig
config ALPHA_ASSEMBLY_BUILD
    bool "Build for full assembly (with membrane + VSM)"
    default n
    help
      Enable this for post-assembly testing builds.
      Adds VSM driver and membrane sensor support.
      Runtime auto-detect determines which tests run.

config ALPHA_MEMBRANE_SUPPORT
    bool "Membrane daughter board support"
    default n
    depends on ALPHA_ASSEMBLY_BUILD
```

Currently both default to `n`. However, the VSM driver (`CONFIG_CK_MODULES_VSM=y`) and PPG sensor (`CONFIG_CK_PAH8151=y`) are **always enabled** in `prj.conf` regardless of `ALPHA_ASSEMBLY_BUILD`. The assembly detect module at runtime probes I2C for the PAH8151 (0x15) and membrane components (PCA9536 at 0x41, BME280 at 0x76).

### Build Flavors via `build_all.sh`

The build script produces two complete firmware images:

1. **Application Processor (nRF52840)**:
   - Built with `--sysbuild` (includes MCUboot)
   - PSP hex merged post-build
   - Output: `build/merged.hex`

2. **Communications Coprocessor (nRF9151)**:
   - Built with manufacturing overlay (`dev.conf`) enabling shell and debug logging
   - FIPS hash calculated and injected for WolfSSL compliance
   - Built twice: first to generate .map file, then with FIPS hash
   - Output: `comm_coproc_mfg/build/merged.hex`

### MCUboot Configuration (`sysbuild/mcuboot.conf`)

- Upgrade-only mode (no rollback): `CONFIG_BOOT_UPGRADE_ONLY=y`
- Downgrade prevention enabled
- ECDSA-P256 signature verification
- **Image encryption enabled**: `SB_CONFIG_BOOT_ENCRYPTION=y`
- External flash secondary slot
- Maximum 256 image sectors

### VSCode Build Tasks

| Task | Description |
|------|-------------|
| Build | Incremental build for nRF52840 |
| Build (pristine) | Clean build for nRF52840 |
| Merge VSM hex | Merge PSP binary into merged.hex |
| Build and merge VSM lib | Sequential: build then merge |
| Build pristine and merge VSM lib | Sequential: pristine build then merge |
| Build All | Run `build_all.sh` (both processors) |
| West Flash | Flash via J-Link |

---

## 7. Personalization

### Default Personalization (`default_personalization.conf`)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `CONFIG_DEFAULT_EUI` | `70B3D584C02003B4` | Device EUI (64-bit identifier) |
| `CONFIG_DEFAULT_EC_PRIV_KEY` | (256-bit hex) | Elliptic curve private key |
| `CONFIG_DEFAULT_EC_PUB_KEY` | (512-bit hex, 04 prefix) | EC public key (uncompressed) |
| `CONFIG_DEFAULT_IPC_KEY` | `C0C1C2C3C4C5C6C7C8C9CACBCCCDCECF` | AES-128 IPC encryption key |
| `CONFIG_SOCKET_SERVER_DEFAULT_URL` | `dev.office.corekinect.cloud` | Cloud server URL |
| `CONFIG_SOCKET_SERVER_REKEY_PATH` | `/api/system/devices/sessions/ssv1` | Session rekey API path |
| `CONFIG_SOCKET_SERVER_DEFAULT_TIME_PORT` | 2024 | Time sync port |
| `CONFIG_SOCKET_SERVER_DEFAULT_SESS_PORT` | 2022 | Session port |
| `CONFIG_SOCKET_SERVER_DEFAULT_DATA_PORT` | 2023 | Data uplink port |
| `CONFIG_SOCKET_SERVER_DEFAULT_TS_PUB_KEY` | (512-bit hex) | Server TLS public key |
| `CONFIG_MAX_UPLINK_BYTES` | 1000 | Max uplink message size |
| `CONFIG_MAX_STORE_AND_FORWARD_PAYLOAD_SIZE` | 768 | Max store-and-forward payload |
| `CONFIG_COMM_COPROC_FW_APP_ID` | 110 | Comms processor firmware ID |

### Runtime Personalization

The `personalization.c` module manages a `personalization_t` structure stored in the `personalization` flash partition (0xDF000, 4 KB):

```c
typedef struct personalization {
    uint8_t ipc_encryption_key[AES128_KEY_LENGTH];  // 16 bytes
} personalization_t;
```

On first boot, the default IPC key from Kconfig is written. The key can be rotated at runtime via an IPC rekey command from the comms coprocessor.

### Persistent Data

Boot-persistent data stored in the `persistent_data` partition (0xFF000, 4 KB):

| Buffer | Data | Description |
|--------|------|-------------|
| `boot_flag_buf_e` | `boot_flag_byte_t` | Boot reason (charger, FUOTA, watchdog, etc.) and reset type (soft/hard) |
| `num_exceptions_buf_e` | `uint8_t` | Cumulative exception count for this FW version |

---

## 8. IPC - Inter-Processor Communication

### Physical Layer

The nRF52840 (app processor) communicates with the nRF9151 (comms coprocessor) via Nordic Software Low-Power UART (LPUART):

| Parameter | Value |
|-----------|-------|
| UART peripheral | UART1 |
| Baud rate | 460800 |
| TX pin | P0.28 |
| RX pin | P0.03 |
| REQ pin | P0.29 (handshake) |
| RDY pin | P0.30 (handshake) |
| Max packet size | 4096 bytes (`CONFIG_NRF_SW_LPUART_MAX_PACKET_SIZE`) |
| Encryption | AES-128 (key from personalization) |

### IPC Library

The IPC stack is provided by the `ck_ipc` Zephyr module. Configuration:

```kconfig
CONFIG_CK_IPC_UART1=y                          # Use UART1 for IPC
CONFIG_IPC_MAIN_PROC=n                          # This is NOT the main processor
CONFIG_CK_IPC_COMM_COPROC_MSGS=y               # Enable comms coprocessor messages
CONFIG_COMM_COPROC_MFG_SUPPORT=y                # Manufacturing test support
CONFIG_MAX_STORE_AND_FORWARD_PAYLOAD_SIZE=768   # Max S&F payload
```

### Message Types (App -> Comms)

| Message | Description | Trigger |
|---------|-------------|---------|
| `trigger_mfg_test` (ID 128) | Request manufacturing test execution | Button 2-press |
| `store_and_forward` | Queue message for cloud upload | Various test results |
| `device_battery_level` | Report battery state | Battery measurement |
| `motion_event` | Motion start/stop notification | Motion state machine |
| `app_downlink_acknowledge` | Acknowledge received downlink | After processing downlink |
| `server_time` | Forward GPS-derived time | On boot callback |
| `fw_version` | Report running FW version | On init |
| `fw_update_request` | Request next FUOTA chunk | During OTA |
| `reboot_notification` | Warn comms of impending reboot | Before restart |

### Message Types (Comms -> App)

| Callback | Description |
|----------|-------------|
| `boot_cb` | Comms processor booted (triggers battery meas, time sync) |
| `app_downlink_cb` | Application downlink data from cloud |
| `server_time_cb` | Server time update |
| `dev_eui_cb` | Device EUI received (written to NFC tag) |
| `fw_update_cb` | FUOTA chunk received |
| `fw_update_reset_cb` | FUOTA reset command |
| `reboot_notification_cb` | Comms requesting reboot |
| `reboot_notification_ack_cb` | Comms acknowledged reboot |
| `app_coproc_reboot_cb` | Comms requesting app processor reboot |
| `rekey_cb` | IPC encryption key rotation |

### IPC Error Handling

The app thread monitors IPC error state via callback. When IPC enters error state, it is logged. When error clears, it is also logged. The error state itself does not trigger a restart.

### nRF9151 Reset Control

The app processor can hardware-reset the nRF9151 via GPIO P1.11 (active-low, with pull-up):

```c
void trigger_coproc_pin_reset(void) {
    gpio_pin_configure_dt(&_coproc_reset, GPIO_OUTPUT_ACTIVE);
    keep_sleeping_for_time(500);  // Hold reset for 500ms
    gpio_pin_configure_dt(&_coproc_reset, GPIO_OUTPUT_INACTIVE);
}
```

### nRF9151 Overlay

The nRF9151 overlay (`boards/alpha_b0_nrf9151_ns.overlay`) is empty -- it uses board default UART pins (no swap needed for REV 1.2 MTIB hardware).

---

## Summary of VSM-Critical Build Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| PPG sensor | PAH8151 at I2C 0x15 | DT overlay |
| PPG interrupt | P0.20, active high | DT overlay |
| PPG LED currents | All 255 (max) | DT overlay |
| VSM enable GPIO | P1.10, active high | Base DTS |
| IMU | LSM6DSO on SPI0, CS P0.08 | Base DTS |
| IMU accel ODR | 52 Hz | DTS property `accel-odr=3` |
| IMU accel range | +/-8g | DTS property `accel-range=3` |
| IMU gyro ODR | 26 Hz | DTS property `gyro-odr=2` |
| IMU gyro range | +/-250 DPS | DTS property `gyro-range=0` |
| IMU interrupt | P0.14, INT2, pulsed | Base DTS |
| IR temp sensor | MLX90614 at GPIO-I2C 0x5A | DT overlay |
| IR emissivity | 65535 (max, 1.0) | DT overlay |
| PSP library flash | 0xE0000, 80 KB | pm_static.yml |
| Skin temp threshold | 75-100 degF | vsm_handler.c |
| Skin detect period | 6000 ms | vsm_handler.c |
| ECT recalc interval | 60 seconds | vsm_handler.c timer |
| VSM warm-up time | 60 seconds | vsm_handler.h define |
| FPU | Enabled | prj.conf |
| Bus mutexes | I2C1 + SPI0 | sensor_handler.c SYS_INIT |
