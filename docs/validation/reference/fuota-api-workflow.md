# FUOTA API Workflow (CoreCloud v1.0)

Confirmed by Jared 2026-03-06. These are the actual REST API endpoints for FUOTA
plan management. Base URL: `https://val.office.corekinect.cloud:2018`

Note: These use the `/singleton/` path prefix, NOT `/api/`. This is different from
the device management endpoints which use `/api/System/Devices/...`.

## Prerequisites

Before FUOTA can work:
1. Device registered in CoreCloud (`/api/System/Devices/Register`)
2. Device public key uploaded to CoreCloud DB (`deviceprofilestbl`)
3. Device type and variant tied to correct AppIds
4. CFW files generated from hex builds
5. CFW files uploaded to server

## Step 1: Generate CFW Files

CFW = CoreFirmware. Binary container wrapping encrypted app-only firmware image.

```python
from corekinect.firmware.cfw import generate_cfw_from_build, APPID_NRF52840_APP, APPID_NRF9151_COMMS

# Input: zephyr.signed.encrypted.bin from west build
# Each build produces TWO CFW files (one per MCU):
#   - AppId 108 (nRF9151 comms coprocessor)
#   - AppId 109 (nRF52840 app processor)

generate_cfw_from_build(
    "path/to/alpha_fw/build/alpha_fw/zephyr/zephyr.signed.encrypted.bin",
    app_id=109, major=0, minor=8, build=0, release_track=TRACK_BENCH,
    manufacturing=True, debug=True)

generate_cfw_from_build(
    "path/to/comm_coproc_mfg/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin",
    app_id=108, major=0, minor=8, build=0, release_track=TRACK_BENCH,
    manufacturing=True, debug=True)
```

CFW format v2: 23-byte header (big-endian) + encrypted firmware binary.
Header: FileVersion(u16) + Timestamp(u64) + AppId(u16) + Flags(u8) + Major(u16) + Minor(u16) + Build(u16) + ImageLength(u32).

Naming convention: `{appId}.{major}.{minor}.{build}-{track}.cfw`
- Track suffixes: P=Production, E=Engineering, B=Bench
- Optional: M=Manufacturing, D=Debug (e.g., `109.0.8.0-BMD` = Bench+Manufacturing+Debug)

Existing CFW files: `apps/firmware/products/alpha/artifacts/cfw/`

### CFW Flags — CRITICAL: Must Match Firmware VersionDevice.h

The CFW flags byte encodes: `(release_track & 0x03) << 1 | manufacturing | (debug << 3)`

The firmware FUOTA handler (`version_api.c:is_valid_fuota_target()`) validates incoming CFW
by comparing THREE fields between current firmware and the CFW header:
1. **app_id must match** (108 or 109)
2. **bootloader_id must match** (bits 1-2 of flags = release_track)
3. **target version must be higher** than current version

**The root cause of "inapplicable fw version" FUOTA rejections is almost always a
bootloader_id mismatch.** The firmware's `VersionDevice.h` defines `BOOTLOADER_ID`
and the CFW flags must use the same track value.

#### Current Alpha VersionDevice.h values (both MFG and production):
```c
// apps/firmware/products/alpha/alpha_fw/src/VersionDevice.h
// apps/firmware/products/alpha/alpha_mfg_fw/src/VersionDevice.h
#define BOOTLOADER_ID   0   // 0=Bench, 1=Engineering, 2=Production
#define IS_MANUFACTURING 1
```

This means ALL Alpha CFW files must use `release_track=TRACK_BENCH` (bootloader_id=0).
Using `TRACK_PRODUCTION` (bootloader_id=2) will cause the device to reject the FUOTA.

#### Flags byte truth table:
| VersionDevice.h | CFW release_track | Flags | Suffix | Valid? |
|----------------|-------------------|-------|--------|--------|
| BOOTLOADER_ID=0, IS_MFG=1, DEBUG=1 | TRACK_BENCH | 0x09 | BMD | YES |
| BOOTLOADER_ID=0, IS_MFG=1, DEBUG=0 | TRACK_BENCH | 0x01 | BM | YES |
| BOOTLOADER_ID=2, IS_MFG=0, DEBUG=0 | TRACK_PRODUCTION | 0x04 | P | NO — mismatch |

#### Firmware validation logic (C source):
```c
// apps/firmware/products/alpha/alpha_mfg_fw/fw_utils/zephyr/version_api.c
bool is_valid_fuota_target(fw_version_t current, fw_version_t target) {
    if (current.app_id != target.app_id) return false;
    if (current.flags.bits.bootloader_id != target.flags.bits.bootloader_id) return false;
    if (current.major < target.major) return true;
    if (current.minor < target.minor) return true;
    if (current.build_number < target.build_number) return true;
    return false;
}
```

**Lesson learned (2026-03-07):** Plans 21-23 all failed due to CFW flags mismatch.
The fix was regenerating CFW files with `TRACK_BENCH` (flags=0x09) instead of
`TRACK_PRODUCTION` (flags=0x04).

## Key Upload — Raw EC Point Format

```
POST https://val.office.corekinect.cloud:2018/api/System/Devices/Sessions/Profiles
Content-Type: application/json

{
  "Profiles": [{
    "deviceId": "70B3D584C01E1FCC",
    "publicKey": "<raw EC point base64>"
  }]
}
```

**CRITICAL**: The `publicKey` must be the raw EC P-256 uncompressed point in base64:
- Raw hex from personalization starts with `04` (65 bytes, 130 hex chars)
- Convert: `base64.b64encode(bytes.fromhex(hex_key)).decode()`
- Result starts with `B` (base64 of `0x04`)
- Example: `BHLSzR5kHt6zKAbfjPoyM38Xa9zHn2fwTt4SmNqf...`

**DO NOT** use DER SubjectPublicKeyInfo format (starts with `MFkw...`). The server
returns **405** for DER-formatted keys, which looks like a permissions error but is
actually a validation/format rejection.

**Session requirement**: Use a fresh `requests.Session()`, NOT the cached session from
`CoreCloudRestInterface` — the cached session can return stale/wrong results on this
endpoint.

Returns 204 on success.

To verify: `GET /System/Devices/Sessions/Profiles` with `json={"deviceIds": ["<id>"]}`

## Step 2: Upload CFW Files to Server

```
POST https://val.office.corekinect.cloud:2018/singleton/firmwareimages
Content-Type: multipart/form-data

Field: image = <CFW file binary>
```

**NOTE**: `CoreCloudRestInterface.request()` only supports `json=` parameter.
Need to extend it with `data=` and `files=` params for multipart uploads,
OR use a raw requests call with the same auth token.

Upload each CFW file separately. The server parses the 23-byte header to extract
version metadata and AppId.

## Step 3: Create FUOTA Plan

```
POST https://val.office.corekinect.cloud:2018/singleton/firmwareupdates/plans
Content-Type: application/json

{
  "stages": [
    {
      "targets": ["108.0.8.0-P", "109.0.8.0-P"],
      "description": "v0.8.0 - Starting firmware (already flashed via J-Link)",
      "isSkippable": false
    },
    {
      "targets": ["108.0.8.1-P", "109.0.8.1-P"],
      "description": "v0.8.1 - FUOTA to new build (Firmware Under Test)",
      "isSkippable": false
    }
  ],
  "description": "Alpha v0.8 Automated Validation FUOTA - run ID: <unique>",
  "deviceTypeId": 2,
  "deviceVariantId": 3
}
```

**Important**: Each stage has TWO targets — one per MCU (108=comms, 109=app).
The `targets` array uses the CFW version string format: `{appId}.{major}.{minor}.{build}-{track}`.

**Response**: Returns the created plan including a `planId` (integer).

### FUOTA Plan Design for Validation

A complete validation FUOTA flow uses 3 stages:
- Stage 0: Starting firmware (the J-Link flashed version — already running)
- Stage 1: FUOTA INTO new build (tests that OTA update works)
- Stage 2: FUOTA OUT to next build (tests that updated device can OTA again)

Stage 2 firmware is identical code to Stage 1 but with bumped build number.

## Step 4: Assign Device to Plan

```
POST https://val.office.corekinect.cloud:2018/singleton/firmwareupdates/settings/devices
Content-Type: application/json

{
  "planId": <planId from step 3>,
  "enableFuota": true,
  "maxStage": 2,
  "deviceIds": ["70B3D584C01E1FCC"]
}
```

**DANGER ZONE**: This is the operation that can affect production devices.
- `maxStage` is 0-indexed. `maxStage: 2` means device goes through all 3 stages.
- `deviceIds` must contain ONLY the test DUT DevEUI. Triple-check this.
- This endpoint modifies `fuotasettingsperdevicetbl` in the DB.

## Step 5: Monitor FUOTA Progress

```
GET https://val.office.corekinect.cloud:2018/singleton/firmwareupdates/progress?deviceId=70B3D584C01E1FCC
```

Poll this endpoint to track which stage the device is on. The server processes
FUOTA on every device uplink (middleware in socket server). Progress depends on:
- Device uplink interval (LTE-M PSM wake cycle, typically 15-60 min)
- Delta patch generation time
- Device download + apply + reboot cycle

## Step 6: Verify Firmware Version

After each stage completes, verify the device is running expected firmware:
- Use `/api/System/Devices/Status` for boot info (boot reason = "Fuota" for FUOTA reboots)
- The progress endpoint should show stage advancement

## Safety Rules

1. **NEVER assign production devices** to test FUOTA plans
2. **NEVER modify existing FUOTA plans** that may be assigned to production devices
3. **Always create NEW plans** with unique names (include run ID)
4. **Always verify deviceIds** before the assignment POST
5. **Read-only probes first**: GET progress endpoint before any POST operations
6. **Cleanup**: After validation, disable FUOTA for the test device (enableFuota: false)

## API Interface Gap

`CoreCloudRestInterface.request()` at `libs/python/corekinect/core_cloud/api_interface.py:195`
only accepts `json=` parameter. For multipart file uploads (Step 2), we need either:
- Extend `request()` to accept `files=` and `data=` kwargs
- OR add a separate `upload()` method
- OR use the session directly with manual auth header injection

The `/singleton/` endpoints may also need different URL construction than `/api/` endpoints.
Need to verify if `_ensure_url()` handles the `/singleton/` prefix correctly since the
base `rest_server_host_name` may already include `/api`.

## Prerequisite: Register App IDs (one-time per device type/variant)

Before creating a FUOTA plan, App IDs must be registered for the device type/variant.
Without this, plan creation returns 404 "Target app ids not set".

```
GET /singleton/firmwareupdates/appids?deviceTypeId=2&deviceVariantId=3
POST /singleton/firmwareupdates/appids
{
  "deviceTypeId": 2,
  "deviceVariantId": 3,
  "appIds": [
    {"appId": 108, "isAuxiliary": false},
    {"appId": 109, "isAuxiliary": false}
  ]
}
```

Confirmed registered for Alpha B0 (type=2, variant=3) on 2026-03-06.

## URL Construction

The `CoreCloudRestInterface` base URL includes `/api` suffix. FUOTA endpoints use
`/singleton/` prefix. Use `/../singleton/` path trick to go up one level:

```python
api.request('GET', '/../singleton/firmwareupdates/plans')
# Resolves to: https://val.office.corekinect.cloud:2018/singleton/firmwareupdates/plans
```

For file uploads (multipart), use raw requests with base URL minus `/api`:
```python
base = api.api.rest_server_host_name.replace('/api', '')
url = f'{base}/singleton/firmwareimages'
```

## Verified Findings (2026-03-06)

1. Auth on `/singleton/` = same Bearer token + X-API-KEY as `/api/`
2. CFW upload returns 204 No Content on success (server parses header automatically)
3. `GET /singleton/firmwareimages` returns 401 (might be POST-only or need different perms)
4. Plan creation returns full plan object with `planId`
5. Device assignment returns `{"numDevicesUpdated": 1, ...}`
6. Progress returns 404 "No firmware updates found" until first FUOTA transfer starts
7. FUOTA transfer starts on next device uplink (socket server middleware)
8. `GET /singleton/firmwareupdates/plans` lists all plans (no filtering)
9. `GET /singleton/firmwareupdates/settings/devices` lists all device assignments

## Device Settings API

```
GET https://val.office.corekinect.cloud:2018/singleton/firmwareupdates/settings/devices
```

Response format:
```json
{
  "devicesFound": [
    {"deviceId": "70B3D584C01E1FCC", "planId": 23, "enableFuota": true, "maxStage": 1}
  ]
}
```

**Note:** Response wraps devices in a `devicesFound` key (not a plain list). The
`FuotaClient.get_device_settings()` method handles this correctly.

## CFW Version Collision — Server Resolves by AppId+Version Only

**CRITICAL**: The CoreCloud FUOTA server resolves CFW files by `AppId + Major.Minor.Build`
**without considering the track suffix**. If both `108.0.8.0-P.cfw` (flags=0x04) and
`108.0.8.0-BMD.cfw` (flags=0x09) are uploaded, the server may deliver the **wrong one**
(observed: it delivered the P version despite the plan targeting BMD).

**Workaround**: Always use a **unique build number** for each track variant. Never upload
both `-P` and `-BMD` CFW files with the same `AppId.Major.Minor.Build`. For example:
- Production: `108.0.8.0-P` (flags=0x04)
- Bench/MFG/Debug: `108.0.8.2-BMD` (flags=0x09) — use build=2 to avoid collision

Plans 21-25 all failed due to this (21-23: wrong flags, 24: stale key, 25: version collision
with P-track CFW).

## Current State (2026-03-07)

- Plans 21-25: DISABLED
- **Plan 26: ACTIVE** — MFG v0.5.1-BMD → Prod v0.8.2-BMD (unique build number, no P collision)
- CFW files uploaded: `108.0.8.2-BMD.cfw`, `109.0.8.2-BMD.cfw`, `108.0.8.3-BMD.cfw`, `109.0.8.3-BMD.cfw`
- Key uploaded via REST API (raw EC point base64, 204 confirmed)
- Device connecting to CoreCloud (RSRP=45 ≈ -96dBm, usable signal)
- Waiting for next uplink to start FUOTA transfer with correct flags

## Existing Plans in VAL Server (for reference)

23+ plans total. Alpha B0 variant=3: plans 21-23 (all ours, all disabled).
Other Alpha plans: plan 4 (variant=1, A0), plans 11-20 (variant=2, Theta).

## Answered Questions

1. First uplink happens within 15-60 min (LTE-M PSM cycle). Power cycle triggers immediate connection attempt.
2. Power cycle IS the way to trigger immediate uplink — device connects within ~35s of boot.
3. Progress response when active: `{"deviceId":"..","version":"108.0.8.0-P","percentComplete":0,"pagesApplied":0,"totalPages":20109,"timeStarted":"..","lastUpdated":".."}`. Pages increment on each uplink.
4. Disable: `POST /singleton/firmwareupdates/settings/devices` with `{"planId":N,"enableFuota":false,"maxStage":0,"deviceIds":[".."]}`
5. Plans cannot be deleted (no DELETE endpoint). Disable device assignment instead.

## Open Questions (Remaining)

1. Can cross-track FUOTA work? (MFG→Prod track, same bootloader_id but different IS_MANUFACTURING flag)
2. MTIB UART stream is byte-by-byte — potential server-side buffering issue at 115200 baud
