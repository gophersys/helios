# icle — knowledge

ICLE (In-Circuit Loop-back Equipment) is a **standalone Zephyr firmware** for an ESP32-WROOM-32-based handheld power-monitoring fixture. It samples DUT power via an INA209, logs to an SD card, and optionally syncs to a backend over WiFi. **It is not part of the Concord platform service mesh** — no gRPC, no http-api dependency, no K8s, no MTIB. It lives in the monorepo because the source belongs to the same product family, but it is built and flashed like any other Zephyr project.

Refresh this file when: the board target changes, a new sensor is added, the operating-mode state machine shifts, the partition table changes, or it grows a dependency on the platform (it currently has none).

## Location

- Code: `apps/firmware/icle/`
- Entry point: `apps/firmware/icle/src/main_new.c`
- App headers: `apps/firmware/icle/include/icle/`
- Board overlay: `apps/firmware/icle/boards/esp32_devkitc_wroom_procpu.overlay`
- Tests: none — verification is on-target manual + (future) Twister harness.

## Responsibilities

Owns:

- The ESP32-WROOM-32 firmware that runs on the ICLE v1.0 hardware (and on a stock ESP32 DevKit-C as a development target).
- The five-state operating-mode FSM: `BOOT → BOOT_DECIDE → {CONFIG, LOGGER} → SHUTDOWN → DEEP_SLEEP`.
- INA209 power sampling, SD card FAT logging (binary + CSV), button input (short/long/double press), LED feedback.
- WiFi STA bring-up via the in-tree `netctl` subsystem (ported from Helios), HTTP heartbeat + config fetch, OTA via the dual-slot partition table.
- Persistent configuration in ZMS/NVS via Zephyr's `settings` subsystem.
- The `icle` Zephyr shell command group for on-device diagnostics.

Does NOT own:

- Any interaction with the Concord platform. There is no MTIB gRPC, no http-api REST, no Prisma model. The HTTP heartbeat target is a separate backend specific to ICLE deployments.
- Cross-compilation for any other MCU family. This is ESP32-only; pin maps and Kconfig assume it.
- Any concept owned by the platform (TestRun, Fixture, Product, Build). It runs on hardware that ships with end users, not on a fixture node.

## Internal structure

```
apps/firmware/icle/
├── CMakeLists.txt              # Zephyr app entry, sources grouped by layer
├── Kconfig                     # ICLE-specific Kconfig (WiFi creds, netctl options)
├── prj.conf                    # Build-wide Zephyr config (logging, GPIO, I2C, SPI, WiFi, ZMS, PM)
├── partitions.csv              # ESP32 partition table (nvs, otadata, ota_0, ota_1, storage)
├── boards/
│   └── esp32_devkitc_wroom_procpu.overlay   # DevKit-C overlay (LED, button, MUX, P-FET, VSPI/SD)
├── include/
│   └── icle/
│       ├── app.h               # FSM states, event flags, public API
│       ├── config.h            # ZMS configuration API
│       ├── types.h             # icle_power_data, icle_log_entry, icle_wake_source, icle_led
│       └── version.h           # ICLE_VERSION_{MAJOR,MINOR,PATCH}
├── src/
│   ├── main_new.c              # Entry: print_banner, init_subsystems, icle_app_run (never returns)
│   ├── app/
│   │   ├── state_machine.c     # FSM transitions
│   │   └── events.c            # k_event wrappers + flag definitions
│   ├── hal/                    # hardware abstraction
│   │   ├── gpio.c              # LED, MUX (3-bit), P-FET gate
│   │   ├── power_monitor.c     # INA209 I2C wrapper
│   │   ├── storage.c           # SD card FAT mount + log file lifecycle
│   │   └── button.c            # GPIO interrupt + debounce + short/long/double
│   ├── net/
│   │   ├── wifi.c              # Thin wrapper over netctl
│   │   └── heartbeat.c         # Periodic HTTP ping
│   ├── services/
│   │   ├── logger.c            # Power sample queue → SD write (binary/CSV)
│   │   ├── http.c              # HTTP client for log upload + config fetch
│   │   ├── ota.c               # OTA over HTTP into the inactive slot
│   │   ├── pm.c                # Deep-sleep entry, wake source detection, RTC boot count
│   │   ├── config_manager.c    # ZMS-backed config persistence
│   │   ├── shell_cmds.c        # `icle` shell command group
│   │   └── netctl/             # Network control arbiter (ported from Helios)
│   └── util/
│       └── json_builder.c      # Minimal JSON serializer
├── docs/
├── DEPLOYMENT_NOTES.md
├── README.md
└── project.json                # nx targets: build, flash, monitor, menuconfig, clean
```

## Key patterns

### Standalone Zephyr app — not platform-coupled

This is plain `west build` + `west flash`, run on the host (with the Zephyr SDK and the ESP32 toolchain) or in the `concord-devcontainer-zephyr:v4.0` devcontainer. The nx wrappers in `project.json` exist for consistency with the rest of the monorepo but they delegate straight to `west`. No image is built, nothing is pushed to a registry, nothing is deployed by a Helm chart. The artifact is `build/zephyr/zephyr.bin` that gets flashed onto hardware.

### Board targets

Default (and what `nx build icle` runs):

```
west build -b esp32_devkitc_wroom/esp32/procpu
```

The board overlay at `boards/esp32_devkitc_wroom_procpu.overlay`:

- Enables the WiFi controller (`&wifi { status = "okay"; }`).
- Defines `led0` / `sw0` aliases mapped to the DevKit-C built-in LED (GPIO2) and BOOT button (GPIO0).
- Adds an `icle_controls` node with MUX0/MUX1/MUX2 (GPIO15/4/16), `pfet_gate` (GPIO17), `adc_inh` (GPIO25) — these are placeholders so the firmware can run unmodified on a stock DevKit.
- Configures SPI3 (VSPI) with CS on GPIO5 for the SD card slot at 24 MHz.

There is a separate `icle_v1_0` configuration in `project.json:build` for the real ICLE v1.0 board. That board's DTS lives outside this directory (commented in `CMakeLists.txt` as a `BOARD_ROOT` extension under `libs/embedded/ck_board`) — when the custom board is finalized, that root is enabled.

### prj.conf — what's compiled in

Highlights of `prj.conf`:

| Section | Settings | Notes |
|---|---|---|
| Kernel | `MAIN_STACK_SIZE=4096`, `HEAP_MEM_POOL_SIZE=16384`, `EVENTS=y` | App loop runs on main; events for FSM dispatch. |
| Logging | `LOG=y`, `LOG_MODE_IMMEDIATE=y`, `LOG_DEFAULT_LEVEL=3` | Synchronous logging by default — switch to deferred only after stack profiling. |
| Shell | `SHELL=y`, `SHELL_BACKEND_SERIAL=y` | The `icle` command group is registered by `services/shell_cmds.c`. |
| Hardware | `GPIO=y`, `I2C=y`, `SENSOR=y`, `SPI=y` | INA209 over I2C, SD over SPI. |
| Storage | `DISK_ACCESS=y`, `DISK_DRIVER_SDMMC=y`, `FILE_SYSTEM=y`, `FAT_FILESYSTEM_ELM=y`, `FS_FATFS_LFN=y` | SD card with FAT + long filenames. |
| Network | `WIFI=y`, `NET_DHCPV4` via netctl, `HTTP_CLIENT=y`, `POSIX_API=y`, `SNTP=y` | netctl auto-selects the bulk of networking config. |
| Storage subsys | `ZMS=y`, `NVS=y`, `SETTINGS=y`, `SETTINGS_NVS=y` | ZMS for log buffers, NVS for `settings`. |
| Power | `PM=y`, `PM_DEVICE=y`, `POWEROFF=y` | Deep sleep with RTC + GPIO wake. |
| Debug | `DEBUG=y`, `ASSERT=y`, `STACK_SENTINEL=y` | Production builds should drop these; see `DEPLOYMENT_NOTES.md`. |

WiFi credentials are baked at build time via two Kconfig symbols, `CONFIG_ICLE_WIFI_SSID` / `CONFIG_ICLE_WIFI_PSK`. They can be overridden at runtime via Config Mode + the shell or via the OTA-delivered config blob.

### Partition table

`partitions.csv` defines a dual-slot OTA layout in 4 MB flash:

```
nvs       data nvs   0x09000  0x04000
otadata   data ota   0x0d000  0x02000
phy_init  data phy   0x0f000  0x01000
ota_0     app  ota_0 0x10000  0x1E0000   (~1.9 MB application slot A)
ota_1     app  ota_1 0x1F0000 0x1E0000   (~1.9 MB application slot B)
storage   data fat   0x3D0000 0x30000    (192 KB FAT for local config/state)
```

OTA via `services/ota.c` writes the inactive slot, validates checksum, flips `otadata`, and resets. The SD card is independent of this — it holds power logs, not firmware.

### Operating-mode FSM

Defined in `include/icle/app.h` and driven by `src/app/state_machine.c`:

```
DEEP_SLEEP --button--> BOOT_DECIDE --short(<2s)--> CONFIG
                                  --long(>=2s)--> LOGGER
CONFIG    --idle 5min/double press--> SHUTDOWN
LOGGER    --long press 3s         --> SHUTDOWN
SHUTDOWN  --done                  --> DEEP_SLEEP
```

The whole loop is **async-only**: only `K_FOREVER` and `K_NO_WAIT` are permitted as blocking-call timeouts. No polling with `K_MSEC(...)`. Events are k_event flags posted by handlers (button, WiFi, SD, OTA) and consumed by the state machine. This is the firmware's defining architectural constraint — adding a `k_msleep` in a handler is a regression.

### Wake handling

`services/pm.c` detects the wake source on boot (GPIO button vs RTC timer vs cold reset) and increments a boot counter stored in RTC retention memory. The banner prints it for forensic traceability across deep-sleep cycles. On a `TIMER` wake, `main_new.c` posts a `TIMER_WAKE` event so the heartbeat path runs without traversing the full FSM.

### Hardware peripherals

| Peripheral | Bus | Pin/Addr | Driver |
|---|---|---|---|
| INA209 power monitor | I2C0 | 0x40 (SDA GPIO21, SCL GPIO22) | `src/hal/power_monitor.c` |
| SD card | SPI2 (VSPI) | CS GPIO5, MOSI 13, MISO 12, CLK 14 | `src/hal/storage.c` via Zephyr `disk_access` + FATFS |
| MUX (3-bit channel select) | GPIO | GPIO15/4/23 (real HW) — overlay maps to GPIO15/4/16 on DevKit | `src/hal/gpio.c` |
| P-FET gate (DUT power) | GPIO | GPIO19 (real HW) — GPIO17 on DevKit overlay | `src/hal/gpio.c` |
| ADC inhibit | GPIO | GPIO32 (real HW) — GPIO25 on DevKit overlay | `src/hal/gpio.c` |
| Status LED | GPIO | GPIO4 (real HW) — GPIO2 on DevKit | `src/hal/gpio.c` |
| Wake button | GPIO | GPIO0 (BOOT, both targets) | `src/hal/button.c` |
| WiFi | ESP32 radio | n/a | `src/net/wifi.c` + `src/services/netctl/wifi/wifi_sta.c` |

Note the pin-numbering divergence between the real ICLE v1.0 board and the DevKit overlay: the firmware writes to the DT alias (`led0`, etc.) so the same binary works on both targets, but the README's pin table is the **real-hardware** map. The overlay redirects to safe-on-DevKit pins for bringup.

## External dependencies

| Concern | Where |
|---|---|
| Toolchain | Zephyr SDK + ESP32 toolchain. Get them via the `concord-devcontainer-zephyr:v4.0` devcontainer (`nx run devcontainer-zephyr-v4.0:build` if it's not yet on your machine). |
| Zephyr modules | `west` workspace at the monorepo root (see `west.yml`). |
| HTTP backend | An ICLE-specific HTTP heartbeat endpoint. **Not** the Concord http-api — different host, different schema. Configured at build time and overridable via runtime config. |
| OTA server | Same backend. Serves signed binary blobs from a known URL path. |
| WiFi credentials | `CONFIG_ICLE_WIFI_SSID` / `CONFIG_ICLE_WIFI_PSK` at build time, or runtime via Config Mode. |

No K8s, no Helm, no compose, no Docker registry — this firmware doesn't ship that way.

## How to add common things

### Add a new sensor

1. Pick a driver path. If Zephyr's `sensor` subsystem has a driver, enable `CONFIG_<SENSOR>` in `prj.conf` and add a DT node in the board overlay (or in the future `icle_v1_0` board DTS).
2. If it needs custom logic, add `src/hal/<sensor>.c` + header following the INA209 pattern: an init function, a read function returning a typed struct in `include/icle/types.h`.
3. Wire the read into the sample loop in `src/services/logger.c` and extend `icle_log_entry` (mind the alignment padding — keep struct size a multiple of 4 bytes).
4. Bump `ICLE_VERSION_MINOR` in `CMakeLists.txt` (it propagates to `version.h` via `target_compile_definitions`).
5. Update this knowledge file's peripherals table and the README pin table.

### Change a power threshold

Thresholds (under/over-voltage cutoffs, sample rate, deep-sleep idle timeout) live in `src/services/logger.c` and `src/services/config_manager.c`. If the threshold is meant to be reconfigurable at runtime, expose it through the `icle_config_*` API in `include/icle/config.h` so it persists in ZMS. Then add an `icle` shell sub-command in `src/services/shell_cmds.c` for on-device tuning. Don't sprinkle magic numbers in the HAL.

### Build / flash / monitor

All via nx, which wraps `west`:

```
nx build icle                        # default: esp32_devkitc_wroom/esp32/procpu
nx run icle:build -c pristine        # west build -p always (clean tree)
nx run icle:build -c icle_v1_0       # custom board (when finalized)
nx run icle:flash                    # west flash (auto-detects /dev/ttyUSB0)
nx run icle:monitor                  # west espressif monitor
nx run icle:menuconfig               # interactive Kconfig
nx run icle:clean                    # rm -rf build
```

All targets must run inside the Zephyr devcontainer or on a host with the equivalent SDK; the host concord devcontainer for Python services does not have `west` or the ESP32 toolchain.

## Common failure modes

- **`west build` fails with "Board not found: icle_v1_0".** The custom board DTS isn't on `BOARD_ROOT` yet. `CMakeLists.txt` has the line commented; until the board is finalized, build for `esp32_devkitc_wroom/esp32/procpu` and run the overlay.
- **Flash succeeds but the device boots into the bootloader.** `partitions.csv` must match the Zephyr expectation for ESP32 dual-slot OTA. If you regenerate or hand-edit it, double-check `otadata` placement at 0xd000.
- **Deep-sleep current is ~mA instead of ~10 µA.** Something is holding a peripheral on — most commonly WiFi didn't fully tear down before `POWEROFF`, or the INA209 is still being read. Confirm via Zephyr's `pm` subsystem state and check that `services/pm.c` calls the right `pm_device_action_run(... PM_DEVICE_ACTION_SUSPEND)` for every active device. The async-only rule applies to shutdown too — no `k_msleep` in the suspend path.
- **WiFi connects but heartbeat times out.** SNTP hasn't completed before HTTP fires, so the TLS cert validation fails. `prj.conf` enables `CONFIG_SNTP=y` but doesn't sequence it. The fix is in `net/heartbeat.c` — wait for the netctl "time-synced" event before posting.
- **Shell command `icle` not found.** `CONFIG_SHELL_BACKEND_SERIAL` is set but the shell didn't register because the UART console wasn't taken — check `CONFIG_UART_CONSOLE=y` and that nothing else is grabbing the same UART instance.
- **OTA write fails mid-flight.** `ota_1` slot smaller than the new binary; bump `ota_*` size in `partitions.csv` and confirm no overlap with `storage`. Zephyr's MCUboot is **not** used here — `services/ota.c` does the slot management directly via `esp_ota_*` style calls.

## Related knowledge

- [`architecture.md`](../../architecture.md) — note ICLE sits outside the three-tier platform diagram; it's listed under apps as "standalone".
- [`libs/embedded.md`](../../libs/embedded.md) — Zephyr modules and `ck_board` overlays (where the future `icle_v1_0` board will live).
- [`libs/embedded.md`](../../libs/embedded.md) — shared Zephyr drivers and board overlays; the canonical "Zephyr build pattern" reference for this repo.
- [`glossary.md`](../../glossary.md) — note: ICLE is NOT an MTIB. They share the test-fixture concept loosely but ICLE ships with end users and runs on its own.
