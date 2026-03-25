# Alpha Manufacturing Firmware and Tests

> Research document for the Alpha manufacturing firmware (`alpha_mfg_fw`) and the
> manufacturing test procedures that exercise it. This is the reference for
> validation engineers building the Stage 4 pipeline, where the manufacturing
> firmware serves as the starting point for FUOTA transitions to production
> firmware.
>
> **Source code examined:**
> - `apps/firmware/products/alpha/alpha_mfg_fw/` -- firmware
> - `apps/manufacturing/alpha/src/tests/` -- Python manufacturing test code

---

## 1. Manufacturing Firmware Overview

### 1.1 Purpose

The Alpha manufacturing firmware (`alpha_mfg_fw`) is a specialized build of the
Alpha device firmware designed exclusively for factory test and device
provisioning. It exposes a UART shell with hardware-diagnostic commands that
allow automated test equipment (the MTIB) to verify every peripheral, provision
device credentials, and lock the debug interface before the device leaves the
factory floor.

### 1.2 Location and Project Structure

```
apps/firmware/products/alpha/alpha_mfg_fw/
  CMakeLists.txt               # Top-level build — 15 ZEPHYR_EXTRA_MODULES
  Kconfig                       # App IDs, shell timeout, IPC key defaults
  prj.conf                      # 137 Kconfig options (shell, BLE, sensors, crypto)
  version.conf                  # CONFIG_APP_FW_MAJOR_VERSION / MINOR
  build_all.sh                  # Builds both processors
  default_personalization.conf  # Default EUI, EC keys, IPC key, server URLs
  main.c                        # Entry point
  pm_static.yml                 # Partition manager layout
  boards/
    alpha_b0_nrf52840.overlay   # App processor DTS overlay
    alpha_b0_nrf9151_ns.overlay # Comms processor DTS overlay
  src/
    VersionDevice.h             # IS_MANUFACTURING=1, BUILD_NUM, App IDs
    app/
      shell_handler.c/.h       # lock_shell, debug_enable, skip_shell
      button_handler.c/.h      # Button-press test modes
      personalization.c         # IPC rekey, flash personalization storage
      sensor_handler.c          # Accelerometer, altimeter, VSM tests
      ble_handler.c/.h          # BLE scan test
      fuota.c/.h                # FUOTA support (mfg -> production transition)
      ...
    platform/
      led.c/.h                  # LED control
      vibrator.c/.h             # Vibration motor control
      emer_button.c/.h          # Emergency button input
      hard_reset.c/.h           # Hard reset trigger
      coproc_reset.c/.h         # Coprocessor reset control
  comm_coproc_mfg/              # Comms coprocessor firmware (nRF9151)
    Kconfig                     # COMM_COPROC_FW_APP_ID default 100 (overridden to 108)
    ...
```

### 1.3 Dual-Processor Architecture

The Alpha device is a dual-MCU system. Both processors run independent firmware
images with their own Zephyr shell:

| Property | App Processor | Comms Coprocessor |
|----------|---------------|-------------------|
| **MCU** | nRF52840 | nRF9151 |
| **UART** | UART1 (`/dev/verdin-uart2`) | UART0 (`/dev/verdin-uart1`) |
| **App ID** | 109 (`CONFIG_APP_CORE_FW_APP_ID`) | 108 (`CONFIG_COMM_COPROC_FW_APP_ID`) |
| **Responsibilities** | Sensors, BLE, VSM, LEDs, vibrator, button | LTE modem, OTA/FUOTA, cloud comms, crypto keys |
| **IPC** | LPUART with AES-128 encryption | LPUART with AES-128 encryption |
| **Shell prompt** | `Mfg shell: ` | `Mfg shell: ` |
| **Build target** | `alpha_b0/nrf52840` | `alpha_b0/nrf9151/ns` |

### 1.4 Manufacturing Flag

The `IS_MANUFACTURING` flag is set to `1` in `src/VersionDevice.h`:

```c
#define APPLICATION_ID    CONFIG_APP_CORE_FW_APP_ID   // 109
#define MAJOR_RELEASE_NUM CONFIG_APP_FW_MAJOR_VERSION  // 0
#define MINOR_RELEASE_NUM CONFIG_APP_FW_MINOR_VERSION  // 5
#define BUILD_NUM         1
#define BOOTLOADER_ID     0
#define IS_MANUFACTURING  1
```

Production firmware uses `IS_MANUFACTURING 0`. The App IDs (108/109) are shared
between manufacturing and production firmware -- the `IS_MANUFACTURING` flag is
the only version-level discriminator.

### 1.5 Shell Timeout Behavior

The manufacturing shell is time-limited. From `Kconfig`:

```
config SHELL_TIMEOUT_SEC
    int "Time the shell should be active in seconds"
    default 7
```

After boot, the shell is active for **7 seconds** (configurable). If no
`lock_shell` command is received within this window, the shell auto-deactivates
via `mark_shell_expired()` and the firmware transitions to its normal operating
mode. This means:

1. UARTs must be opened **before** power-on.
2. `lock_shell` must be sent **immediately** after boot UART output appears.
3. Receiving `lock_shell` stops the expiration timer and locks the shell on
   permanently (until reboot or `skip_shell`).

The `shell_handler.c` implementation:

```c
void set_shell_command_rxed(void)
{
    if (0 != k_timer_remaining_get(&shell_expiration_timer))
    {
        _is_shell_active = true;
        k_timer_stop(&shell_expiration_timer);
        shell_warn(shell_backend_uart_get_ptr(), "Locking shell mode ON");
    }
}
```

---

## 2. Shell Command Reference

### 2.1 App Processor (nRF52840) -- UART1 (`/dev/verdin-uart2`)

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `lock_shell` | Lock shell on permanently (stops timeout timer) | `Locking shell mode ON` |
| `skip_shell` | Immediately exit shell mode (start normal operation) | Shell deactivates |
| `debug_enable 0` | Disable Zephyr log backend (reduce UART noise) | `Debug is not enabled` |
| `debug_enable 1` | Re-enable Zephyr log backend | `Debug is enabled` |
| `get_chip_ids` | Read chip identification registers (accel, ext flash, BLE MAC) | Chip ID values (verify non-zero) |
| `read_accel` | Read LSM6DSO accelerometer X/Y/Z | Acceleration values (verify non-zero) |
| `read_alt` | Read BME280 altimeter/pressure sensor | Pressure/altitude/temperature values |
| `test_ble` | Perform BLE scan test | BLE scan results (verify radio functional) |
| `write_ext_flash <addr> <data>` | Write base64-encoded data to external SPI flash at hex address | Write confirmation |
| `read_ext_flash <addr> <len>` | Read `<len>` bytes from external flash at hex address | Hex-encoded data at address |
| `erase_ext_flash` | Erase external flash sector | Erase confirmation |

### 2.2 Comms Processor (nRF9151) -- UART0 (`/dev/verdin-uart1`)

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `lock_shell` | Lock shell on permanently | `Locking shell mode ON` |
| `skip_shell` | Exit shell mode immediately | Shell deactivates |
| `debug_enable 0` | Disable log backend | `Debug is not enabled` |
| `get_pub_key` | Export ECDSA public key (for device registration) | Base64-encoded public key string |
| `personalize <device_id>` | Set device EUI/ID and regenerate ECDSA keypair | Personalization confirmation + new public key |
| `rekey_ipc` | Regenerate IPC encryption keys (replace defaults) | Rekey confirmation |
| `imei_iccids` | Read modem IMEI and SIM ICCIDs | IMEI string + ICCID list |
| `get_modem_fw` | Get nRF9151 modem firmware version | Modem FW version string |
| `write_ext_flash <addr> <data>` | Write to comms external flash | Write confirmation |
| `read_ext_flash <addr> <len>` | Read from comms external flash | Hex data |
| `erase_ext_flash` | Erase comms external flash | Erase confirmation |

### 2.3 Python Command Wrappers

The manufacturing test code uses typed wrapper classes from the `corekinect`
library rather than raw UART string manipulation:

```python
from corekinect.mtib_client.v2.client.cmd_comms import CommsShellCommands
from corekinect.mtib_client.v2.client.cmd_alpha_app import AlphaAppShellCommands

# Created after boot_and_lock_shells():
app_cmds = AlphaAppShellCommands(app_shell)
comms_cmds = CommsShellCommands(comms_shell)

# Usage:
id_1, id_2, error = app_cmds.get_chip_ids()
hex_key, base64_key, error = comms_cmds.personalize(device_id)
success, error = comms_cmds.rekey_ipc()
```

---

## 3. Build System

### 3.1 Build Script: `build_all.sh`

The `build_all.sh` script orchestrates a multi-step build for both processors:

```bash
# Step 1: Build Application Processor (nRF52840)
west build --pristine -d build -b alpha_b0/nrf52840 --sysbuild . -- \
    -DBOARD_ROOT=ck_boards/current/ \
    -DEXTRA_CONF_FILE=version.conf \
    -DDTC_OVERLAY_FILE=boards/alpha_b0_nrf52840.overlay

# Merge PSP (proprietary signal processing) binary
mergehex -m build/merged.hex vsm_drv/src/.../psp.hex -o build/merged.hex

# Step 2: Build Communications Coprocessor (nRF9151) -- first pass
west build --pristine -d comm_coproc_mfg/build -b alpha_b0/nrf9151/ns --sysbuild comm_coproc_mfg -- \
    -DBOARD_ROOT=ck_boards/current/ \
    -DOVERLAY_CONFIG=dev.conf \
    "-DEXTRA_CONF_FILE=version.conf;default_personalization.conf" \
    -DDTC_OVERLAY_FILE=boards/alpha_b0_nrf9151_ns.overlay

# Step 3: Calculate FIPS hash and rebuild comms with hash
python3 wolfssl/scripts/gen_fips_hash.py build/merged.hex build/zephyr/zephyr.map > fips.conf

# Step 4: Final comms build with FIPS hash overlay
west build -d comm_coproc_mfg/build ... -DOVERLAY_CONFIG="dev.conf;fips.conf" ...
```

Key details:
- The comms processor requires a **two-pass build**: first to produce the
  binary, then to calculate the WolfSSL FIPS integrity hash, then rebuild with
  the hash embedded.
- The `dev.conf` overlay enables manufacturing-specific features
  (`CONFIG_COMM_COPROC_MFG_SUPPORT=y`).
- The `default_personalization.conf` provides factory-default credentials:
  - Default EUI: `70B3D584C02003B4`
  - Default IPC key: `C0C1C2C3C4C5C6C7C8C9CACBCCCDCECF`
  - CoreCloud server: `dev.office.corekinect.cloud`

### 3.2 Build Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| `build/merged.hex` (nRF52840) | App processor directory | Plaintext `.hex` for J-Link flash |
| `comm_coproc_mfg/build/merged.hex` (nRF9151) | Comms directory | Plaintext `.hex` for J-Link flash |
| Encrypted `.cfw` variants | Build output | FUOTA packages (bootloader omitted, encrypted) |
| `fips.conf` | Comms directory | FIPS integrity hash for WolfSSL |
| `.map` files | Build output | Linker maps for FIPS hash calculation |

### 3.3 Firmware Configuration Highlights

From `prj.conf` (selected entries relevant to manufacturing):

```ini
# Shell configuration
CONFIG_SHELL=y
CONFIG_SHELL_PROMPT_UART="Mfg shell: "
CONFIG_SHELL_ASYNC_API=y
CONFIG_SHELL_CMD_BUFF_SIZE=768
CONFIG_SHELL_STACK_SIZE=8192

# Sensor drivers (for POST tests)
CONFIG_CK_LSM6DSO=y             # Accelerometer/gyro
CONFIG_BME280_DRV=y              # Altimeter/pressure
CONFIG_CK_PAH8151=y             # PPG (heart rate)
CONFIG_CK_MLX90614=y            # IR temperature
CONFIG_CK_MODULES_VSM=y         # Vital signs monitor

# BLE (for BLE scan test)
CONFIG_BT=y
CONFIG_BT_OBSERVER=y

# External flash (for flash read/write/erase tests)
CONFIG_FLASH=y
CONFIG_SPI_NOR=y

# Crypto (for personalization and IPC rekey)
CONFIG_CK_CRYPTO=y
CONFIG_CK_CRYPTO_WOLFCRYPT=y
CONFIG_BASE64=y

# Battery management
CONFIG_BQ25622_CHARGER=y
CONFIG_MAXIM_BMS_DRV=y

# Bootloader (required for FUOTA)
CONFIG_BOOTLOADER_MCUBOOT=y
```

---

## 4. Manufacturing Test Phases

Manufacturing tests are orchestrated from
`apps/manufacturing/alpha/src/tests/` and run on the MTIB test bench via gRPC.
There are three major test suites that execute in sequence.

### 4.1 Phase 1: Electrical Test (`PRDTST-224`)

**Source:** `apps/manufacturing/alpha/src/tests/electrical/test.py`

The electrical test verifies power rail behavior at multiple voltage levels
without any firmware interaction. It uses only MTIB power supply and ADC
measurements.

**Fixture configuration** (from `shared/config.py`):

| Parameter | Default Value | Purpose |
|-----------|---------------|---------|
| `electrical_uvlo_voltage_v` | 3.4V | Below UVLO threshold |
| `electrical_nominal_voltage_v` | 3.7V | Normal battery voltage |
| `electrical_high_voltage_v` | 4.5V | Upper battery limit |
| `electrical_chrg_voltage_v` | 5.0V | Charger input voltage |
| `electrical_stabilization_period_s` | 30s | Max wait for voltage stabilization |

**Test Steps:**

| Step | Code | Description | Pass Criteria |
|------|------|-------------|---------------|
| 1 | `step_1.py` | Apply +3.4V to +BATT_IN (below UVLO) | Power supply accepts voltage |
| 2 | `step_2.py` | Verify device is OFF at UVLO voltage | 3.3V rail < 0.55V, current < 1mA |
| 3 | `step_3.py` | Apply +3.7V to +BATT_IN (nominal) | Power supply accepts voltage |
| 4 | `step_4.py` | Verify +3.3V remains below threshold during startup delay | 3.3V stays below threshold for stabilization period |
| 5 | `step_5.py` | Verify device electrical state (powered) | BATT_SYS/SYS track BATT_IN, 3.3V in 3.2-3.4V, current in 5-150mA |
| 6 | `step_6.py` | Apply +4.5V to +BATT_IN | Power supply accepts voltage |
| 7 | `step_7.py` | Verify +SYS voltage tracks +BATT_IN | SYS within 0.15V of BATT_IN |
| 8 | `step_8.py` | Apply 5.0V to +CHRG (charger input) | Charge power enabled |
| 9 | *(skipped)* | *(Charger state verification -- commented out)* | -- |
| 10 | `step_10.py` | Remove power from +CHRG | Clean shutdown of charge rail |

**Init/Deinit pattern:** The test initializes by disabling all power on all
MTIB nodes, and de-initializes by disabling power again to leave a clean state.
Tests run in parallel across a 4-panel fixture (one MTIB per slot).

### 4.2 Phase 2: Firmware Flash

**Source:** `apps/manufacturing/alpha/src/tests/fw_flash/test.py`

After electrical tests pass, the manufacturing firmware is flashed onto both
processors via J-Link/SWD through the MTIB.

**Steps:**

| Step | Code | Description | Timeout |
|------|------|-------------|---------|
| 1 | `step_1.py` | Flash nRF52840 app + nRF9151 modem firmware via J-Link | 5 min |
| 2 | `step_2.py` | Flash nRF9151 comms application firmware via J-Link | 2 min |
| 3 | `step_3.py` | Enable APPROTECT on both processors | 30 sec |

**Firmware files** (from config):

| File | Target |
|------|--------|
| `alpha_app_prod_8.hex` | nRF52840 application processor |
| `alpha_comm_prod_8.hex` | nRF9151 comms processor application |
| `mfw_nrf91x1_2.0.2.zip` | nRF9151 modem firmware |

**J-Link flashing via MTIB V2 client:**

```python
# Connect to debug probe
err, session = client.debug_connect(target_id="nrf52840", probe_id="")

# Flash with erase, verify, and reset
err, flash_result = client.flash_program(
    session_id=session.session_id,
    filename="alpha_app_prod_8.hex",
    erase_before=True,
    verify_after=True,
    reset_after=True,
)
client.debug_disconnect(session.session_id)
```

**APPROTECT note:** Step 3 (APPROTECT enable) is currently **skipped** because
the MTIB V2 server does not yet implement the `EnableAppProtect` RPC. This must
be implemented before production use.

### 4.3 Phase 3: POST (Post-Electrical Tests) (`PRDTST-4`)

**Source:** `apps/manufacturing/alpha/src/tests/post/test.py`

The POST test is the most comprehensive manufacturing test. It exercises every
major hardware subsystem through the manufacturing firmware's UART shell
commands.

**Shared data structure** (`PostTestSharedData`):

```python
class PostTestSharedData:
    client: Optional[MtibV2Client] = None
    app_shell: Optional[ShellCommandHelper] = None
    comms_shell: Optional[ShellCommandHelper] = None
    app_cmds: Optional[AlphaAppShellCommands] = None
    comms_cmds: Optional[CommsShellCommands] = None
    imei: Optional[str] = None
    iccids: Optional[List[str]] = None
```

**Steps:**

| Step | Code | Description | Timeout | Fatal |
|------|------|-------------|---------|-------|
| 0 | `step_0.py` | Boot device and lock shells on both processors | 10 min | Yes |
| 1 | `step_1.py` | Verify comms processor chip IDs | 15 sec | Yes |
| 2 | `step_2.py` | Verify app processor chip IDs (accel, ext flash, BLE MAC) | 15 sec | Yes |
| 3 | `step_3.py` | Verify BMS (gas gauge) readings | -- | Yes |
| 4 | `step_4.py` | Verify battery charger IC | -- | Yes |
| 5 | `step_5.py` | Verify GPS module | -- | Yes |
| 6 | `step_6.py` | Verify modem firmware version | -- | Yes |
| 7 | `step_7.py` | Verify IMEI and ICCIDs (stored in shared data for step 9) | -- | Yes |
| 8 | `step_8.py` | Verify external flash on both processors (parallel) | 2 min | Yes |
| 9 | `step_9.py` | Personalize device (CoreOps API + UART) | 30 sec | Yes |
| 10 | `step_10.py` | Rekey IPC (replace default keys) | 15 sec | Yes |

All steps are `noPassIsFatal=True` -- any single failure aborts the entire POST
sequence.

#### Step 0: Boot and Lock Shells (Critical Path)

This step uses `boot_and_lock_shells()` from the MTIB V2 client library, which
handles the complex race condition:

```python
from corekinect.mtib_client.v2.client.shell import boot_and_lock_shells

# GPIO: configure SWD level shifter pins
client.gpio_config(pin=0, direction=1)
client.gpio_write(pin=0, value=False)

# Boot and lock — handles power cycle, UART race, TX drain, retries
app_shell, comms_shell, err = boot_and_lock_shells(
    client, app_port="uart1", comms_port="uart0"
)
```

The 10-minute timeout accounts for TX backlog drain, which can take 3-5 minutes
at 115200 baud on a device that has been running with debug output enabled.

#### Step 8: External Flash Verification (Parallel)

Both processors' external flash is tested simultaneously using
`ThreadPoolExecutor`. The test writes a known pattern
(`ALPHA_POST_TEST_PATTERN_2024`) to three locations (start `0x000000`, end
`0x100000`, random middle between `0x040000`-`0x080000`), reads back, and
verifies. If the first attempt fails, it erases and retries.

#### Step 9: Device Personalization

The personalization step involves three systems:

1. **CoreOps API** -- Assigns a unique device ID based on the J-Link serial
   number:
   ```
   POST /v1/devices/ids/assign  {"snr": "000A"}
   ```

2. **UART command** -- Sends the device ID to the comms processor, which
   generates a new ECDSA keypair:
   ```python
   hex_key, base64_key, error = comms_cmds.personalize(device_id)
   ```

3. **CoreOps API** -- Uploads the device's public key, IMEI, and ICCIDs:
   ```
   POST /v1/devices/keys/upload    {"deviceId": "...", "pubKey": "..."}
   POST /v1/devices/iccids/save    {"iccid": "...", "carrier": "...", ...}
   ```

   Carrier detection is by ICCID prefix:
   | ICCID Prefix | Carrier |
   |-------------|---------|
   | `891480` | Verizon |
   | `8942310` | Soracom |
   | `894573` | Onomondo |
   | `890103` | AT&T |

#### Step 10: IPC Rekey

Replaces the default hard-coded IPC encryption key
(`C0C1C2C3C4C5C6C7C8C9CACBCCCDCECF`) with a device-specific randomly generated
AES-128 key. This ensures each device has unique inter-processor encryption
from the factory.

```python
success, error = comms_cmds.rekey_ipc()
```

On the firmware side (`personalization.c`), the rekey callback writes the new
key to flash and updates the IPC layer:

```c
static void start_ipc_rekey(uint8_t *p_new_key)
{
    _is_ipc_rekey = true;
    memcpy(_new_ipc_key, p_new_key, AES128_KEY_LENGTH);
    wakeup_app();
}
```

---

## 5. Button Test Modes

The manufacturing firmware supports interactive button-press test modes via the
emergency button. The button handler in `button_handler.c` uses press counting
with a 3.3-second timeout window:

| Presses | Action | Description | Timeout |
|---------|--------|-------------|---------|
| 1 | Vibrate | Run vibration motor for 1.5 seconds | 3 sec |
| 2 | Assembly test | Full assembly test: GPS cold start + HW failure report + IPC dual-SIM test | 5 min |
| 3 | Crosstalk test | PPG sensor optical crosstalk calibration | 5 sec |
| 4 | Heartrate test | 35-second heart rate/SpO2/temperature measurement | 35 sec |
| 7 | Hard reset | Trigger full device restart | Immediate |

From `button_handler.c`:

```c
#define NUM_PRESSES_FOR_VIBRATE           1
#define NUM_PRESSES_FOR_ASSEMBLY_TEST     2
#define NUM_PRESSES_FOR_CROSSTALK_TEST    3
#define NUM_PRESSES_FOR_HEARTRATE_TEST    4
#define NUM_PRESSES_FOR_HARD_RESET        7
```

Press counts 5 and 6 are **not mapped** -- they produce a "Not starting test"
warning and no action.

---

## 6. MTIB Integration for Manufacturing Tests

### 6.1 Power Sequencing

The Alpha B0 uses a BQ25180 battery charger with a UVLO threshold that requires
**4.5V** on the battery simulation rail for reliable boot.

```python
# Power DUT (MUST be 4.5V for BQ25180 UVLO)
client.power_enable(channel=0, voltage_v=4.5)  # Ch0: battery sim
client.power_enable(channel=1)                   # Ch1: charge/USB (5V default)
time.sleep(5)                                     # Wait for boot
```

**Verification:** `power_status(channel=0)` must show >50mA after boot. If
0mA, the DUT is not booting (common with 4.0V -- too low for BQ25180).

### 6.2 J-Link Flashing

The MTIB V2 client provides a high-level flashing API that abstracts `nrfjprog`:

```python
# Always recover first to clear APPROTECT
err, session = client.debug_connect(target_id="nrf52840", probe_id="")
err, flash_result = client.flash_program(
    session_id=session.session_id,
    filename="alpha_app_prod_8.hex",
    erase_before=True,     # --chiperase
    verify_after=True,     # --verify
    reset_after=True,      # --reset
)
client.debug_disconnect(session.session_id)
```

Underneath, this maps to:

```bash
# Recovery (clear APPROTECT):
nrfjprog --recover --snr <PROBE_SERIAL> -f NRF52 --speed 4000

# Flash:
nrfjprog --program <file.hex> --chiperase --verify --reset \
    --snr <PROBE_SERIAL> -f NRF52 --speed 4000
```

Rules:
- **Always use speed 4000** (4 MHz) for SWD through the MTIB mux.
- **Always power the DUT at 4.5V** before any J-Link/SWD operation.
- **Always run `--recover` before flashing** to clear APPROTECT.
- `nrfjprog` is only available inside the K8s pod -- use `nsenter` for manual
  access.

### 6.3 UART Port Mapping

| Port Name | Device Path | Alpha B0 Target |
|-----------|------------|-----------------|
| `uart0` | `/dev/verdin-uart1` | nRF9151 comms coprocessor |
| `uart1` | `/dev/verdin-uart2` | nRF52840 app processor |

### 6.4 GPIO Configuration

The MTIB V2 fixture uses a TCA9534A GPIO expander (REV 1.2) for SWD level
shifter control. Before flashing or booting, pins must be configured:

```python
# Configure SWD level shifter pins as outputs, drive low
client.gpio_config(pin=0, direction=1)
client.gpio_config(pin=1, direction=1)
client.gpio_write(pin=0, value=False)
client.gpio_write(pin=1, value=False)
```

### 6.5 Shell Locking Sequence

The complete boot-and-lock sequence using `boot_and_lock_shells()`:

1. Open both UART ports **before** applying power (win the race)
2. Apply 4.5V to channel 0
3. Immediately spam `lock_shell` on both UARTs
4. Wait for shell lock confirmation on both ports
5. Send `debug_enable 0` on both ports to silence log output
6. Drain TX backlog (can take 1-5 minutes at 115200 baud)
7. Retry with J-Link debug reset on first failure for clean boot

---

## 7. Relevance to Validation Pipeline (Stage 4)

### 7.1 Manufacturing Firmware as Starting Point

In the Stage 4 validation pipeline, the manufacturing firmware serves a
critical role:

1. **Initial device state**: Every device in Stage 4 begins in the
   manufacturing firmware state, exactly as it would arrive from the factory
   floor. This is the most realistic starting condition for validation.

2. **FUOTA source firmware**: The first firmware-over-the-air update (FUOTA)
   transitions the device FROM manufacturing firmware TO production firmware.
   This tests the complete OTA path that production devices will use.

3. **Hardware baseline**: POST results from the manufacturing test confirm that
   all hardware is functional before production firmware is loaded. If a Stage 4
   test fails, you can rule out hardware faults by referencing the POST results.

4. **Personalization state**: After manufacturing tests, the device has:
   - A unique device ID registered with CoreOps
   - A unique ECDSA keypair (public key uploaded to CoreCloud)
   - Device-specific IPC encryption keys
   - IMEI and ICCIDs registered with carrier information
   - APPROTECT enabled (debug port locked)

### 7.2 Stage 4 Transition Flow

```
[Factory State]                    [Stage 4 Validation]

 Manufacturing FW (IS_MFG=1)
   |
   +-- Electrical test (PRDTST-224)
   +-- Flash mfg FW via J-Link
   +-- POST test (PRDTST-4)
   +-- APPROTECT enable
   |
   v
 Device ready for FUOTA ---------> Stage 4 begins here
                                     |
                                     +-- FUOTA: mfg FW -> production FW
                                     +-- Verify production firmware boots
                                     +-- Run Stage 4 product test suite
                                     +-- Verify CoreCloud message delivery
```

### 7.3 What Stage 4 Reuses from Manufacturing

| Manufacturing Component | Stage 4 Usage |
|------------------------|---------------|
| `boot_and_lock_shells()` | Same function used to interact with mfg FW before FUOTA |
| `MtibV2Client` | Same client for power control, GPIO, and flashing |
| MTIB fixture wiring | Same physical test bench (power, UART, J-Link) |
| CoreOps device registration | Stage 4 verifies messages from a device already registered during POST |
| `ThetaFixtureConfig` | Extended for Stage 4 with additional config fields |

### 7.4 Key Differences from Manufacturing Tests

| Aspect | Manufacturing Tests | Stage 4 Validation |
|--------|--------------------|--------------------|
| Firmware under test | Manufacturing FW (`IS_MFG=1`) | Production FW (`IS_MFG=0`) |
| Test interface | UART shell commands | Black-box only (no shell) |
| Pass/fail authority | UART responses + MTIB measurements | CoreCloud messages + MTIB measurements |
| Duration | Minutes per device | Hours to days per test suite |
| Scope | Hardware verification | Product specification compliance |

---

## 8. Manufacturing Python Test Code Reference

### 8.1 Directory Structure

```
apps/manufacturing/alpha/
  setup.py
  config/
    config.py               # Global configuration (proxy server URL, etc.)
    log.py                  # Logging configuration
  src/
    main.py                 # Test runner entry point
    tests/
      lib.py                # Test framework base classes (Test, TestStep, TestStepResult)
      shared/
        config.py           # ThetaFixtureConfig dataclass (all test parameters)
        rpcs.py             # mtib_servers singleton (V1 RPC wrapper)
      electrical/
        test.py             # Electrical test definition (10 steps)
        data.py             # ElectricalTestSharedData
        step_1.py ... step_10.py
      fw_flash/
        test.py             # Firmware flash test definition (3 steps)
        data.py             # FwFlashTestSharedData
        step_1.py ... step_3.py
      post/
        test.py             # POST test definition (11 steps, 0-10)
        data.py             # PostTestSharedData
        step_0.py ... step_10.py
```

### 8.2 Test Framework Pattern

All manufacturing tests follow a consistent pattern:

```python
# Test definition
test: Test = Test(
    info=TestInfo(name="...", description="...", defaultConfig=...),
    config_type=ThetaFixtureConfig,
    init_func=test_init,           # Called once before all steps
    deinit_func=test_deinit,       # Called once after all steps
    usr_data=shared_data_dict,     # Dict[str, SharedData] keyed by node
    steps=[step_1, step_2, ...],   # Ordered list of TestStep objects
)

# Step definition
step: TestStep = TestStep(
    info=StepInfo(name="...", description="...", noPassIsFatal=True),
    timeout_ms=15000,
    handler=step_handler,          # (config, node, usr_data) -> TestStepResult
)

# Step handler
def step_handler(config, node, usr_data) -> TestStepResult:
    result = TestStepResult(success=False)
    # ... test logic ...
    result.success = True
    return result
```

### 8.3 Multi-Node Parallelism

Manufacturing tests support running across multiple MTIB nodes simultaneously
(4-panel fixture). Init and deinit use `ThreadPoolExecutor` to parallelize
per-node setup:

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = {executor.submit(init_node, node): node for node in nodes}
    for future in concurrent.futures.as_completed(futures):
        error = future.result()
```

Individual test steps run per-node and are orchestrated by the test runner
framework.

---

## 9. Known Issues and TODOs

| Issue | Impact | Status |
|-------|--------|--------|
| APPROTECT enable not implemented in V2 server | Devices ship without debug lock | `step_3.py` returns success but does nothing |
| Electrical step 9 (charger state) commented out | Charger verification incomplete | Skipped in `electrical/test.py` |
| Several electrical sub-checks commented out | Steps 2/5 only verify subset of rails | Partial voltage/current checks |
| `ThetaFixtureConfig` naming | Config class named "Theta" but used for Alpha | Historical naming, no functional impact |
| Default COMM_COPROC_FW_APP_ID mismatch | Kconfig default is 100, overridden to 108 in personalization.conf | Works correctly via conf override |
| Shell timeout 7 seconds | Tight window for boot-and-lock race | `boot_and_lock_shells()` handles retries |
