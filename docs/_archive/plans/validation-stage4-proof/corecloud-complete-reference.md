# CoreCloud Complete Reference (from Confluence)

> Extracted 2026-03-02 from 18+ Confluence pages. This is the single source of truth
> for all CoreCloud integration knowledge needed by the validation system.
> **Do not search Confluence again for these topics.**

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Server Components](#server-components)
3. [Authentication & Authorization](#authentication--authorization)
4. [Device Lifecycle](#device-lifecycle)
5. [Firmware Versioning](#firmware-versioning)
6. [App ID Table (Alpha B0)](#app-id-table-alpha-b0)
7. [FUOTA Mechanism](#fuota-mechanism)
8. [REST API Reference](#rest-api-reference)
9. [Socket Server Protocol](#socket-server-protocol)
10. [CoreOps (Manufacturing)](#coreops-manufacturing)
11. [IPC Personalization Commands](#ipc-personalization-commands)
12. [Environment Map](#environment-map)
13. [Known Gaps & Workarounds](#known-gaps--workarounds)

---

## System Architecture

CoreCloud is a .NET Core system with four server components:

```
                    ┌─────────────┐
                    │  Auth Server │  (JWT tokens, API keys, RBAC)
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
│  REST Server │  │   Singleton  │  │ Socket Server│
│  (HTTP API)  │  │ (shared svc) │  │ (device TCP) │
└──────────────┘  └──────────────┘  └──────┬───────┘
                                           │
                                    ┌──────▼──────┐
                                    │ Time Server  │
                                    │ (UTC + certs)│
                                    └─────────────┘
```

- **All inter-server communication**: HTTPS with private CA (custom cert chain)
- **External clients**: Must provide `X-API-KEY` header + `Authorization: Bearer {JWT}`
- **Socket Server**: Devices only (AES-256 encrypted, HMAC-SHA-256 authenticated)
- **Docker image tag format**: `<version>_<databases>_<flags>` (e.g., `0.3.0_pg_0`)
- **Latest release**: 0.3.0 (Apr 2025) — added device transfers, message parser API, device status

---

## Server Components

### Auth Server
- JWT token issuance and validation
- Account management (create, activate, deactivate)
- Login management (users and service accounts)
- API key CRUD
- Role-based access control (permissions + roles + inheritance)
- **Login flow**: `POST /authentication/tokens/request` with `Basic {base64(email:password)}` → Bearer JWT

### REST Server
- Device management (register, search, update, transfer)
- Device configuration (GPS, ground mode, etc.)
- Webhook management (create, update, delete, assign devices)
- Account administration
- FUOTA status queries
- **Middleware pipeline**: API key validation → Access token check → Account ID override (privileged)

### Socket Server
- Device TCP connections (encrypted protocol)
- Session management (AES-256 + HMAC-SHA-256 keys per device)
- Uplink processing (messages → DB)
- Downlink delivery (config changes, FUOTA chunks)
- **FUOTA middleware**: Runs on every device uplink — checks FuotaTbl, sends firmware chunks

### Time Server
- UTC time synchronization for devices
- TLS certificate distribution (Session Gen Server public key)
- ECDSA-signed responses (device verifies with hardcoded public key)

### Singleton
- Shared services between REST Server and Socket Server
- Internal communication only (private CA TLS)

---

## Authentication & Authorization

### API Keys
- Created by privileged users via `/Authentication/ApiKeys/Create`
- Included in `X-API-KEY` HTTP header
- Some keys grant privileged access (admin, system operations)
- API keys are scoped to accounts

### Access Tokens (JWT)
- Obtained via `POST /authentication/tokens/request` with Basic auth
- Included in `Authorization: Bearer {token}` header
- Auto-refresh on 401 (client-side)

### Privileged Access
- Privileged API keys can override `Override-Account-Id` header
- Privileged logins can access system-level operations
- Required permissions are documented per endpoint

### Roles
- `Admin` — Full system access
- `System` — Internal service-to-service
- `ClientApp` — Application-level access
- Custom roles with permission inheritance

### Getting Credentials (Bringup Sequence)
1. Auth Server seed mode → create root admin API key + user
2. CoreCloud seed mode → create CoreCloud API key + service login
3. Assign roles → `Admin` for user, `System`/`ClientApp` for service
4. Disable seed mode → use root admin credentials going forward

---

## Device Lifecycle

### Registration
1. **Register device** via `POST /System/Devices/Register` (DeviceId, DeviceType, DeviceVariantId)
   - Devices auto-assigned to account 1 (system account), marked active
2. **Upload public key** via `POST /System/Devices/Set-Device-Profile` (DeviceId + base64 public key)
   - Required for Socket Server session generation

### Manufacturing Flow
1. Flash manufacturing firmware → device generates ECDSA keypair
2. Test fixture reads public key, assigns device ID, reads IMEI/ICCID
3. Device contacts manufacturing Time Server (gets UTC time + Session Gen TLS cert)
4. Device POSTs rekey request to manufacturing REST Server:
   - Body: `DeviceId + CurrentTimeUTC + Nonce + ECDSASignature`
   - Server validates signature using stored public key
   - Server returns: `Flags(4) + SessionId(4) + AES256Key(32) + HMACKey(32)` = 72 bytes
5. Device communicates with manufacturing Socket Server using new keys
6. Manufacturing system OTAs production firmware
7. Manufacturing system uploads public key to production REST Server
8. Manufacturing system downlinks production server config (CMD_PERSONALIZE_SSV2_SRV_CFG)
9. Device rekeying against production servers
10. **Recovery**: Device falls back to manufacturing config after 5 consecutive production failures

### CMD_PERSONALIZE_SSV2_SRV_CFG (0x15)
```
Octet 0:     Command ID (0x15)
Octet 1:2:   MLength (105 bytes including CRC)
Octet 3:     Flags — bit[7]=read/write, bit[0]=prod(1)/mfg(0)
Octet 4:5:   Session Port (big endian)
Octet 6:7:   Data Port (big endian)
Octet 8:39:  Session Gen Secret Key (32 bytes AES-256)
Octet 40:71: Session Gen Encryption Key (32 bytes AES-256)
Octet 72:103: Session Gen HMAC Key (32 bytes AES-256)
```

### Account Transfer
- `POST /System/Devices/Set-Account` — move devices between accounts
- `POST /System/Devices/Move-To-System-Account` — reset to system account

### Device Types & Variants
- **Device type** = message spec (different board types, e.g., Alpha vs Sigma5)
- **Device variant** = firmware application (same HW, different App ID → different variant)
- Device type 0 / variant 0 = wildcard ("don't care")
- Types and variants are compile-time constants (cannot be added at runtime)

---

## Firmware Versioning

### Binary Format (7 bytes)
```
AppId(2 bytes) + Flags(1 byte) + Major(1 byte) + Minor(1 byte) + Build(2 bytes)
```

### Flags Byte
```
Bit [7:4]  Reserved
Bit [3]    Debug flag (1 = debug build)
Bit [2:1]  Release Track:
             00 = Bench
             01 = Engineering
             10 = Production
             11 = Reserved
Bit [0]    Manufacturing flag (1 = manufacturing FW)
```

### String Format
```
AppId.Major.Minor.Build-Flags
Example: 109.1.2.305-PM   (App=109, v1.2.305, Production Manufacturing)
```

### Build Artifacts
| Type | Extension | Use Case |
|------|-----------|----------|
| Plaintext hex | `.hex` | J-Link direct flash |
| Encrypted hex | `.hex` | Build prerequisite |
| Encrypted binary (no bootloader) | `.cfw` / `.ckbin` | OTA (FUOTA) |

### Important Rules
- Manufacturing FW shares App ID with production FW (enables mfg→prod FUOTA)
- Bootloader contains signing public key + encryption key → **cannot be updated OTA**
- App IDs must change when firmware is incompatible (e.g., different bootloader)
- Version numbers only increase (except mfg→production transition)

### Hex File Naming
```
<FirmwareVersionInfo>_<OptionalInfo>.hex
Example: 00018013_Nur_RevB_v4_Gold_Prod.hex
```

### CKBIN File Naming
```
<FirmwareVersionInfo>_<CRC32>_<BinaryFileSize>_<OptionalInfo>.ckbin
Example: 00018013_290C66F0_00014000_Nur_RevB_v4_Gold_Prod.ckbin
```

---

## App ID Table (Alpha B0)

| App ID | Name | Chipset | MCU | CoreCloud Type | CoreCloud Variant |
|--------|------|---------|-----|----------------|-------------------|
| 108 | Comms | Alpha Bx | nRF9151 | 2 | 3 |
| 109 | Alpha | Alpha Bx | nRF52840 | 2 | 3 |

**Other relevant App IDs:**
| App ID | Name | Chipset | MCU | Type | Variant |
|--------|------|---------|-----|------|---------|
| 100 | Comms | Sigma5 Cx | nRF9160 | 1 | 1 |
| 101 | Sigma5 V2 | Sigma5 Cx | nRF52840 | 1 | 1 |
| 102 | Comms | Alpha Ax | nRF9160 | 2 | 1 |
| 103 | Alpha | Alpha Ax | nRF52840 | 2 | 1 |
| 106 | Comms | Theta Cx | nRF9151 | 3 | 1 |
| 107 | Theta | Theta Cx | nRF52840 | 3 | 1 |

**For our validation devices (Alpha B0):**
- nRF9151 comms = App ID 108, CoreCloud type=2, variant=3
- nRF52840 app = App ID 109, CoreCloud type=2, variant=3

---

## FUOTA Mechanism

### Overview
There is **no REST API** for FUOTA management. FUOTA is managed through:
1. **Azure file upload** → `cc-smb-fs` storage account → `C:\CoreCloud\CoreCloud.SocketServer\fuota`
2. **Direct DB INSERT** into `FuotaTbl` (firmware image registry)
3. **Release list assignment** via `FuotaListsTbl` (device→plan mapping)
4. **Socket Server middleware** — runs on every device uplink, checks for pending FUOTA

### Step-by-Step FUOTA Process
1. Build encrypted `.cfw` / `.ckbin` firmware files
2. Upload files to Azure Storage: `portal.azure.us` → `ckstdstgacctfs` → `cc-smb-fs`
3. Copy files to Socket Server host: `\\coreserver003\Share\Fuota\{Product}\{Stepping}\{Build}\`
4. INSERT into `FuotaTbl`:
   ```sql
   INSERT INTO FuotaTbl (DeviceTypeId, IsActive, FwVersion, FilePath, ReleaseList, Released)
   VALUES (
     9,              -- DeviceTypeId (9=Sigma, check for Alpha)
     1,              -- IsActive
     0x2C1C8,        -- FwVersion (hex of version bytes)
     '.\fuota\{filename}.ckbin',  -- Relative path from server root
     {release_list},  -- ReleaseList ID
     0               -- Released (ignored for now)
   );
   ```
5. Assign device to release list:
   ```sql
   UPDATE FuotaListsTbl
   SET ReleaseList = {your_release_list}
   WHERE DeviceID = 0x{your_device_id};
   ```
6. Trigger device check-in (shake, charger, power cycle)
7. Server middleware detects pending FUOTA on next uplink, begins chunk download
8. Device receives all chunks, applies update, reboots with `boot_reason=2` (FUOTA complete)

### FUOTA Plans (Socket Server v1.0)
Plans use staged JSON format:
```json
{
  "targets": [
    {"appId": 108, "version": "108.1.0.100", "stage": 1},
    {"appId": 109, "version": "109.1.0.100", "stage": 2}
  ],
  "isSkippable": false,
  "maxStage": 2
}
```

### Per-Device FUOTA Settings
```json
{
  "deviceId": "70B3D584C01E1FCC",
  "planId": 1,
  "enableUpdates": true,
  "maxStage": 2
}
```

### FUOTA Rules
- Versions only increase (except manufacturing → production transition)
- No cross-release-track updates (e.g., can't go from Production to Engineering)
- No production debug images
- 5-minute cooldown between firmware downloads
- Device type + variant determines which App IDs are eligible
- Auxiliary images (modem FW, PSP library) can be side-loaded as separate stages

### Alpha PSP FUOTA (Special)
- PSP library (Philips binary blob) at fixed address in nRF52840 flash
- Function-address mapping array bundled with library
- Downloaded like regular FUOTA, then copied from external flash to internal flash
- Rollback capability: keeps previous version until new one validated

### FUOTA Database Tables
| Table | Purpose |
|-------|---------|
| `FuotaTbl` | Firmware image registry (DeviceTypeId, FwVersion, FilePath, ReleaseList) |
| `FuotaListsTbl` | Device-to-release-list mapping (DeviceID → ReleaseList) |
| `FuotaSettingsPerDeviceTbl` | Per-device: planId, enableUpdates, maxStage |
| `FuotaSettingsPerDeviceTypeTbl` | Per-device-type: default FUOTA settings |
| `FuotaPlansTbl` | Plan definitions (stages JSON) |
| `FuotaProgressTbl` | Current progress: pages_applied / total_pages per (deviceId, appId) |
| `FuotaProgressHistoryTbl` | Historical progress records |
| `FirmwareUpdateMessageTbl` | Server-side FUOTA message log |
| `JumpTrackFirmwareV2MessageTbl` | Legacy firmware update messages |
| `DeviceFirmwareHistoryTbl` | Firmware version history (appId, major, minor, build, track, isMfg) |
| `DeviceTransferTargetsTbl` | Server transfer targets (rekey path, public keys) |

### FUOTA Completion Detection
- `BootMsgV2.boot_reason == 2` → "Reboot due to completing FUOTA"
- Query `FuotaProgressTbl` for pages_applied == total_pages
- Query `DeviceFirmwareHistoryTbl` for new version entry

### FUOTA Status Monitoring (SQL)
```sql
-- Check FUOTA progress for a device
SELECT * FROM FuotaProgressTbl WHERE DeviceID = 0x70B3D584C01E1FCC;

-- Check if device completed FUOTA
SELECT * FROM FuotaProgressTbl
WHERE DeviceID = 0x70B3D584C01E1FCC
  AND PagesApplied = TotalPages;

-- Get release list members
SELECT * FROM FuotaListsTbl WHERE ReleaseList = {list_id};

-- Get all active FUOTA images
SELECT * FROM FuotaTbl WHERE IsActive = 1;
```

---

## REST API Reference

### Authentication

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/authentication/tokens/request` | Basic | Get JWT access token |
| `POST` | `/Authentication/ApiKeys/Create` | Privileged | Create API key |
| `GET` | `/Authentication/ApiKeys/Get?apiKeyId=` | Privileged | Fetch API key value |
| `GET` | `/Authentication/ApiKeys/GetAll` | Privileged | List all API keys |
| `POST` | `/Authentication/ApiKeys/Revoke?apiKeyId=` | Privileged | Revoke API key |

### Account Administration

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/Authentication/Accounts/Register` | Privileged | Register accounts from Auth Server |
| `GET` | `/Authentication/Accounts/List?page=&resultsPerPage=` | Privileged | Search accounts |

### Device Management (`/System/Devices/`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/System/Devices/Register` | Privileged | Register devices (DeviceId, DeviceType, DeviceVariantId) |
| `GET` | `/System/Devices/Search?...` | Privileged | Paginated device search with filters |
| `PATCH` | `/System/Devices/Update` | Privileged | Update device type/variant |
| `POST` | `/System/Devices/Set-Account` | Privileged | Transfer devices to another account |
| `POST` | `/System/Devices/Move-To-System-Account` | Privileged | Reset devices to system account |
| `POST` | `/System/Devices/Set-Device-Profile` | Privileged | Upload device public key (base64) |

### Device Configuration

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `PUT` | `/System/Devices/Configurations/Gps` | Bearer + API Key | Push GPS config to device |

### Webhook Management (`/Account/Webhooks/`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/Account/Webhooks/Create` | Non-privileged | Create webhook (URL, auth config) |
| `GET` | `/Account/Webhooks/List` | Non-privileged | List webhooks |
| `PATCH` | `/Account/Webhooks/Update` | Non-privileged | Update webhook config |
| `DELETE` | `/Account/Webhooks/Delete?webhookId=` | Non-privileged | Delete webhook |
| `POST` | `/Account/Webhooks/Assign-Devices` | Non-privileged | Assign devices to webhook |
| `POST` | `/Account/Webhooks/Assign-Device-Types` | Non-privileged | Assign device types to webhook |
| `DELETE` | `/Account/Webhooks/Unassign-Devices` | Non-privileged | Unassign devices |
| `DELETE` | `/Account/Webhooks/Unassign-Device-Types` | Non-privileged | Unassign device types |
| `GET` | `/Account/Webhooks/Search-Devices?webhookId=` | Non-privileged | Get devices on webhook |
| `GET` | `/Account/Webhooks/Search-Device-Types?webhookId=` | Non-privileged | Get device types on webhook |

### CoreOps Proxy (`https://10.4.45.3:443`)

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| `POST` | `/v1/devices/ids/assign` | `{"snr": "<SNR>"}` | Get device ID (deterministic) |
| `POST` | `/v1/devices/keys/upload` | `{"deviceId": "<ID>", "pubKey": "<b64>"}` | Upload public key |
| `POST` | `/v1/devices/iccids/save` | `{"iccid": "...", "carrier": "...", "snr": "...", "imei": "..."}` | Save SIM info |
| `GET` | `/v1/health/proxy` | — | Health check |

---

## Socket Server Protocol

### Time Server Communication
1. Device sends: `MessageType(1) + Length(2) + RandomArray(16)` = 19 bytes
2. Time Server responds: `MessageType(1) + Length(2) + ResponseData(variable) + ECDSASignature(70-72)`
3. Device verifies signature over `RandomArray + ResponseData` using hardcoded public key

### Session Generation (Rekey)
1. Device sends POST to `POST /v1.0/management/devices/create-device-keys`:
   ```
   MessageType(1) + Length(2) + DeviceId(8) + CurrentTimeUTC(4) + Nonce(16) + ECDSASignature(70-72)
   ```
2. Server validates: signature, time within 60s of server UTC, device registered
3. Server responds with 72 bytes:
   ```
   Flags(4) + DeviceSessionId(4) + AES256Key(32) + HMACKey(32)
   ```

### Data Server Communication
1. Device opens TCP socket to Data Server
2. Packet format: `Header(12) + EncryptedPayload(variable) + MAC(32)`
3. Header: `ProtocolVersion(1) + SessionId(4) + EpochSeconds(4) + PacketCount(1) + PayloadLength(2)`
4. Payload encrypted with AES-256 CBC, MAC is HMAC-SHA-256 over header + encrypted payload
5. Packet count prevents replay attacks:
   - 0 = session reset (first 16 bytes of payload = new IV)
   - Increments within same epoch second
   - Resets to 1 on new epoch second
   - Server ignores packets with ID <= last successfully received

---

## CoreOps (Manufacturing)

### Overview
CoreOps is the internal manufacturing operations system. Key functions:
- Device ID assignment (IEEE address block, deterministic per SNR)
- Serial number generation (Base36 encoded, min 4 chars = 1.67M serials)
- Board identification (QR code on PCB → unique board identifier)
- Manufacturing pipeline tracking (stages, pass/fail, debug/failed/passed/RMA)
- SIM activation and traceability
- Test fixture support (result upload, pass/fail criteria)

### Manufacturing Pipeline Stages
1. Board serialization (implicit first stage)
2. Custom stages per device type (fixture tests, etc.)
3. Terminal stages:
   - **Debug** — failed, needs investigation (can return to pipeline)
   - **Failed** — unrecoverable
   - **Abandoned** — incomplete but no longer needed
   - **Passed** — ready for production
   - **RMA** — returned device

### Integration Points for Validation
- `POST /v1/devices/ids/assign` — we use this for re-personalization
- `POST /v1/devices/keys/upload` — upload new public key after re-flash
- `POST /v1/devices/iccids/save` — register SIM info (first time only)
- Board ID / serial number lookup (if needed for traceability)

---

## IPC Personalization Commands

### Via nRF9151 Comms UART (uart0)
| Shell Command | Method | Returns | Timeout |
|--------------|--------|---------|---------|
| `lock_shell` | `cmd_comms_coproc_lock_shell()` | `(success, error)` | 2s window after boot |
| `debug_enable 0` | `cmd_comms_coproc_debug_uart_disable()` | — | — |
| `personalize {device_id_hex}` | `alpha_cmd_personalize(device_id)` | `(hex_key, b64_key, error)` | default |
| `rekey_ipc` | `cmd_comms_coproc_rekey_ipc()` | `(success, error)` | 15s |
| `imei_iccid` | `alpha_cmd_get_imei_iccids()` | `(imei, iccid_list, error)` | 45s |

### Via nRF52840 App UART (uart1)
| Shell Command | Method | Returns |
|--------------|--------|---------|
| `lock_shell` | — | Lock app shell |
| `get_chip_ids` | `get_chip_ids()` | `(ext_flash_id, ble_mac, error)` |
| `env_test` | `env_test()` | `(temp_c, humidity_pct, pressure_pa, error)` |
| `meas_bat_voltage` | `meas_bat_voltage()` | `(voltage_v, error)` |
| `read_accel` | `read_accel()` | `(x, y, z in g, error)` |
| `test_bms` | `test_bms()` | `(connected, chip_id, charge_pct, capacity, temp, error)` |
| `test_charger` | `test_charger()` | `(chip_id, on_charger, charging, charge_done, voltage_mv, error)` |

---

## Environment Map

### DEV_1_0 (Our Validation Target)
| Service | URL | Port |
|---------|-----|------|
| Auth Server | `https://auth.office.corekinect.cloud` | 2013 |
| REST Server | `https://dev.office.corekinect.cloud` | 2022 |
| Session Server | `https://dev.office.corekinect.cloud` | 2022 |
| Data Server | `https://dev.office.corekinect.cloud` | 2023 |
| Time Server | `https://dev.office.corekinect.cloud` | 2024 |
| Database | `dmz-pg02.dmz.corekinect.com` (SSH tunnel) | 5432 |

### Required Credentials (from Jarred)
```
DEV_1_0_DB_USERNAME=<from Jarred>
DEV_1_0_DB_PASSWORD=<from Jarred>
DEV_1_0_DB_DATABASE_NAME=<from Jarred>
DEV_1_0_DB_HOST=127.0.0.1          # via SSH tunnel
DEV_1_0_SSH_HOST=dmz-pg02.dmz.corekinect.com
DEV_1_0_SSH_PORT=22
DEV_1_0_SSH_USERNAME=<from Jarred>
DEV_1_0_SSH_PASSWORD=<from Jarred>
DEV_1_0_API_AUTH_SERVER_HOST_NAME=https://auth.office.corekinect.cloud:2013
DEV_1_0_API_REST_SERVER_HOST_NAME=https://dev.office.corekinect.cloud:2022/api
DEV_1_0_API_AUTH_USERNAME=<from Jarred>
DEV_1_0_API_AUTH_PASSWORD=<from Jarred>
DEV_1_0_API_KEY=<from Jarred>
```

### VAL_1_0 (Unused — devices not personalized here)
| Service | URL | Port |
|---------|-----|------|
| REST Server | `https://val.office.corekinect.cloud` | 2018 |
| Database | `validation.ad.corekinect.com` | 5432 |

### DEV_0_9 (Legacy, MySQL)
- DB: `coreserver005.ad.corekinect.com:3306`
- Not used for validation

---

## Known Gaps & Workarounds

### No FUOTA REST API
**Gap**: No REST endpoints for creating FUOTA plans, uploading .cfw files, or managing release lists.
**Workaround**: Direct DB writes via ORM + Azure file upload. Core Admin PRD shows FUOTA CRUD is planned but not yet implemented.
**What we need from Jarred**: DB write access (DEV_1_0 credentials) + Azure storage access for `cc-smb-fs`.

### No Device Status REST API (v1.0 only)
**Gap**: Device status API was added in v0.3.0 but endpoint details not documented in Confluence.
**Workaround**: Query `devicestbl` directly for device active/inactive status.

### No Configuration CRUD API (beyond GPS)
**Gap**: Only GPS config has a documented REST endpoint. Ground mode, biometric config, etc. not documented.
**Workaround**: Direct DB writes or wait for Core Admin implementation.

### Alpha-Specific: PSP Library FUOTA
**Gap**: PSP library FUOTA is unique to Alpha (Philips binary blob). Requires special handling in FUOTA plan.
**Impact**: Phase 5 FUOTA testing must account for PSP library as a separate stage.

### Build Server Path
- Build artifacts stored at `\\CoreServer001\Builds\{Project}\{Track}\{Build}\`
- Azure file share: `portal.azure.us` → `ckstdstgacctfs` → `cc-smb-fs`
- We may need to use a different path for validation (not production build server)
