# CoreCloud Integration Surface

> Explored 2026-03-01. Source: `libs/python/corekinect/core_cloud/`

---

## Architecture Overview

Four interconnected layers:

1. **REST API client** — `CoreCloudRestInterface` for pushing device configs (GPS, etc.)
2. **DB interface** — `CoreCloudDBInterface` for reading telemetry from PostgreSQL
3. **Message types** — Frozen dataclasses in `msg_def_v1_0.py` wrapping ORM models
4. **CoreOps proxy** — Manufacturing proxy at `https://10.4.45.3:443` for device ID assignment, key upload, SIM registration

---

## Environment Configuration

Three CoreCloud environments are defined:

| Namespace | DB Type | DB Host | REST API | Notes |
|-----------|---------|---------|----------|-------|
| `VAL_1_0` | PostgreSQL | `validation.ad.corekinect.com:5432` | `https://val.office.corekinect.cloud:2018/api` | Validation cloud |
| `DEV_1_0` | PostgreSQL (SSH tunnel) | `dmz-pg02.dmz.corekinect.com` → `corecloud_office_prod` | `https://dev.office.corekinect.cloud:2022/api` | Office dev |
| `DEV_0_9` | MySQL | `coreserver005.ad.corekinect.com:3306` | — | Legacy |

**Auth server (both):** `https://auth.office.corekinect.cloud:2013`
**Auth flow:** HTTP Basic → `POST /authentication/tokens/request` → Bearer JWT, auto-refresh on 401

**Env var pattern:** Prefix namespace, e.g. `VAL_1_0_API_REST_SERVER_HOST_NAME`

**Full .env template:** `libs/python/corekinect/core_cloud/.env.example`

---

## Message Types (DB-backed)

All message classes provide: `last()`, `since_server_time()`, `since_device_time()`, `since_record_id()`

| Class | UID | DB Table | Key Fields |
|-------|-----|----------|-----------|
| `BootMsgV2` | 548 | `messagesboottbl` | `boot_reason` (0=normal, 1=exception, 2=FUOTA, 3=charger, 4=error, 5=reboot_msg, 6=watchdog, 7=user_button), `num_exceptions`, `time_of_boot` |
| `PositionMsgV6` | 556 | `messagespositionv5tbl` | `latitude`, `longitude`, `fix_type`, `batt_voltage`, `temperature`, `air_pressure`, `avg_force`, `max_force`, `is_in_motion` |
| `BiometricDataMsg` | 557 | `messagesbiometricdatatbl` | `heart_rate`, `spo2`, `skin_temperature`, `estimated_core_temperature`, `on_body`, `vsm_on_time` |
| `NetworkStatusMsgV4` | 512 | `messagesnetworkstatusv4tbl` | `did_lte_conn`, `did_sock_conn`, `send_success`, `rsrp`, `rsrq`, `band` |
| `AlphaHwFailureMsg` | 559 | `messagesalphahwfailtbl` | `xlr_fails`, `alt_fails`, `gps_fails`, `bms_fails`, `ppg_fails`, `imu_fails` |
| `CommsHwFailureMsg` | 549 | `messagescommshwfailtbl` | `sim_fails`, `lora_fails`, `ipc_fails`, `ext_flash_fails` |
| `GPSConfMsg` | 524 | `configgpstbl` | `is_psm_enabled`, `is_aiding_enabled`, `gnss_update_freq` |

---

## REST API Endpoints (Known)

### CoreCloud REST (via `CoreCloudRestInterface`)

| Method | Path | Used By | Purpose |
|--------|------|---------|---------|
| `PUT` | `/System/Devices/Configurations/Gps` | `GPSConfMsg.send_via_rest()` | Push GPS config to device |

**Auth:** `Authorization: Bearer {JWT}` + `X-API-KEY: {key}`

### CoreOps Proxy (Manufacturing, `https://10.4.45.3:443`)

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| `POST` | `/v1/devices/ids/assign` | `{"snr": "<SNR>"}` | Get device ID for serial number (deterministic) |
| `POST` | `/v1/devices/keys/upload` | `{"deviceId": "<ID>", "pubKey": "<base64>"}` | Upload device public key |
| `POST` | `/v1/devices/iccids/save` | `{"iccid": "...", "carrier": "...", "snr": "...", "imei": "..."}` | Register SIM info |
| `GET` | `/v1/health/proxy` | — | Health check |

---

## FUOTA Integration (DB-only, no REST API found)

FUOTA is managed entirely through the DB. No REST endpoint for creating or triggering FUOTA plans was found in the SDK. Relevant tables:

| Table | Purpose |
|-------|---------|
| `fuotaplanstbl` | FUOTA plan definitions (linked to device types) |
| `fuotaprogresstbl` | Current progress per `(deviceid, appid)` — pages applied / total pages |
| `fuotaprogresshistorytbl` | Historical progress records |
| `fuotasettingsperdevicetbl` | Per-device FUOTA enable flag + max stage |
| `fuotasettingsperdevicetypetbl` | Per-device-type FUOTA settings |
| `devicefirmwarehistorytbl` | Firmware version history (post-FUOTA records) |
| `devicetransfertargetstbl` | Server transfer targets with rekey path + public keys |

**FUOTA completion detection:** `BootMsgV2.boot_reason == 2` ("Reboot due to completing FUOTA")

**Implication for Phase 5:** Without a REST API for FUOTA plan management, we may need to use direct DB ORM operations to create and monitor FUOTA plans. This bypasses server-side validation and is not ideal. Need to check with CoreCloud team or Confluence for undocumented REST endpoints.

---

## Device Management Tables (ORM)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `devicestbl` | Master device registry | `deviceid`, `devicetypeid`, `devvariantid`, `accountid`, `isactive` |
| `deviceprofilestbl` | **Public key store** | `deviceid`, `publickeycipher`, `publickeytype`, `timecreated` |
| `devicefirmwarehistorytbl` | Firmware history | `appid`, `major`, `minor`, `revision`, `releasetrack`, `ismfg` |
| `deviceaccounthistorytbl` | Account assignment history | `deviceid`, `accountid` |
| `devicetransfertargetstbl` | Transfer targets | `devicerekeypath`, `timeserverpublickey`, `serverbaseurl` |

---

## UART Shell Commands (for Re-personalization)

Via `CommsShellCommands` (nRF9151, `uart0`):

| Method | Shell Command | Returns | Timeout |
|--------|-------------|---------|---------|
| `personalize(device_id)` | `personalize {device_id_hex}` | `(hex_key, base64_key, error)` | default |
| `rekey_ipc()` | `rekey_ipc` | `(success, error)` | 15s |
| `get_imei_iccid()` | `imei_iccid` | `(imei, iccid_list, error)` | 45s |
| `get_chip_ids()` | `get_chip_ids` | `(lora_status, ext_flash_id, error)` | default |

Via `AlphaAppShellCommands` (nRF52840, `uart1`):

| Method | Shell Command | Returns |
|--------|-------------|---------|
| `get_chip_ids()` | `get_chip_ids` | `(ext_flash_id, ble_mac, error)` |
| `env_test()` | `env_test` | `(temperature_c, humidity_pct, pressure_pa, error)` |
| `meas_bat_voltage()` | `meas_bat_voltage` | `(voltage_v, error)` |
| `read_accel()` | `read_accel` | `(x, y, z in g, error)` |
| `test_bms()` | `test_bms` | `(connected, chip_id, charge_pct, capacity, temp, error)` |
| `test_charger()` | `test_charger` | `(chip_id, on_charger, charging, charge_done, voltage_mv, error)` |

**Boot + lock:** `boot_and_lock_shells(client, app_port="uart1", comms_port="uart0")`
- Shell prompt: `"Mfg shell:"`
- Activation window: ~2 seconds after boot
- TX backlog drain: up to 5 minutes at 115200 baud

---

## Automated Re-personalization — Implementation Path

To automate re-personalization in the validation pipeline:

```python
# 1. Flash firmware (already in FixtureController.flash_firmware)
ctx.fixture.flash_firmware(hex_path, target="nrf52840")

# 2. Boot and lock shells (needs MtibV2Client, not V1)
#    NOTE: Current test framework uses MtibV1Client.
#    boot_and_lock_shells() requires MtibV2Client.
#    This is a gap that needs bridging.
from corekinect.mtib_client.v2.client.shell import boot_and_lock_shells
app_shell, comms_shell, err = boot_and_lock_shells(
    v2_client, app_port="uart1", comms_port="uart0"
)

# 3. Personalize (UART command to nRF9151)
from corekinect.mtib_client.v2.client.cmd_comms import CommsShellCommands
comms_cmds = CommsShellCommands(comms_shell)
hex_key, base64_key, err = comms_cmds.personalize(device_id_hex)

# 4. Upload keys to CoreOps proxy
import requests
proxy_url = "https://10.4.45.3:443"
requests.post(f"{proxy_url}/v1/devices/keys/upload",
              json={"deviceId": device_id_hex, "pubKey": base64_key}, verify=False)
# Also save ICCIDs if needed (usually only first time)

# 5. Rekey IPC
comms_cmds.rekey_ipc()

# 6. Power cycle — device now ready for CoreCloud
ctx.fixture.power_cycle()
```

**Key gap:** The test framework uses `MtibV1Client` but `boot_and_lock_shells()` needs `MtibV2Client`. Either:
- Add a V2 client to TestContext alongside the V1 client
- Port `boot_and_lock_shells()` to work with V1 client
- Or use V1 UartStream + raw command sending for personalization
