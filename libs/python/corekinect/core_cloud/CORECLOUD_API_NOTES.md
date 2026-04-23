# CoreCloud REST API — Findings & Behavior Notes

**Last updated:** 2026-04-01
**Tested against:** VAL_1_0 (val.office.corekinect.cloud:2018)

## Authentication

- **Auth server:** POST `https://auth.office.corekinect.cloud:2013/authentication/tokens/request`
- **Requires:** Basic auth (username:password) + `X-API-KEY` header + `grant_type=password` form data
- **Returns:** `{"accessToken": "...", "expiresIn": 14399}` (~4 hours)
- **REST API:** All calls need `Authorization: Bearer <token>` + `X-API-KEY` header

## Device Status — `/System/Devices/Status`

**Method:** GET with JSON body `{"deviceIds": ["70B3D584C01E1FCC"]}`

**Returns:**
```json
{
  "devices": [{
    "deviceId": "70B3D584C01E1FCC",
    "positionInfo": {"recordId": 369585, "timeOfFix": "...", "latitude": 0, ...},
    "bootInfo": {"recordId": 357241, "timeOfBoot": "...", "bootReason": "Charger"},
    "commsHwFailInfo": {"recordId": ..., "hasFailures": false},
    "appHwFailInfo": {"recordId": ..., "hasFailures": true}
  }]
}
```

**Key insight:** `recordId` increases with each new device uplink. Poll for `recordId > baseline` to detect new events.

## GroundModeConfigV2 — Configuration

### Read (Search)
**Method:** POST `/System/Devices/Configurations/GroundModeV2/Search`
**Body:** `{"deviceIds": ["70B3D584C01E1FCC"]}`

**Returns:** The config values the DEVICE LAST REPORTED — NOT the desired state.
```json
{
  "groundModeConfigurations": [{
    "deviceId": "70B3D584C01E1FCC",
    "gpsHeartbeatPeriod": 60,
    "continuousMotionPeriod": 30,
    "stopMotionTimeout": 60,
    "heartbeatAcquisitionTimeout": 60,
    "motionAcquisitionTimeout": 60,
    "motionAcquisitionOnTime": 30,
    "motionInitialAcquisitionOnTime": 60,
    "xlrMotionThreshold": 20,
    "xlrMotionDuration": 4,
    "startMotionWindowStart": 3,
    "startMotionWindowEnd": 30
  }]
}
```

### Write
**Method:** PUT `/System/Devices/Configurations/GroundModeV2`
**Body:** Full config object (ALL fields required, not partial updates)

**CRITICAL:** The PUT sets the DESIRED state on the server. The device receives
this on its next uplink (heartbeat). The Search endpoint will NOT reflect the
change until the device acknowledges and reports back the new config.

**Timeline:**
1. PUT config → HTTP 200 (server accepted the desired state)
2. Device heartbeat (up to 60 minutes) → device receives new config
3. Device applies config and reports back → Search now shows new values

**For validation tests:** Config override tests cannot just write and read back.
They must either:
- Wait for the device to report the new config (up to one heartbeat period)
- Verify the PUT was accepted (HTTP 200) and trust the server will deliver it
- Power cycle the device to force an immediate heartbeat

### Write Format
The PUT endpoint requires ALL fields. Partial updates return HTTP 400:
```json
// WRONG — partial update
{"deviceId": "...", "gpsHeartbeatPeriod": 120}
// → 400: JSON deserialization error

// CORRECT — full config object
{"deviceId": "...", "gpsHeartbeatPeriod": 120, "continuousMotionPeriod": 30, ...all fields...}
// → 200 OK
```

## FUOTA Endpoints — `/singleton/`

**Important:** FUOTA endpoints use the SINGLETON base URL, not the REST API `/api` prefix.

- `GET /singleton/firmwareupdates/plans` — list plans
- `GET /singleton/firmwareupdates/plans?planId=N` — get specific plan
- `POST /singleton/firmwareupdates/plans` — create plan
- `POST /singleton/firmwareupdates/settings/devices` — assign device to plan
- `GET /singleton/firmwareupdates/progress?deviceId=<DevEUI>` — check progress
- `POST /singleton/firmwareimages` — upload CFW (multipart)

### D-Flag Stripping (CRITICAL BUG)
CoreCloud strips the D (debug) flag from FUOTA plan targets. A CFW uploaded
as `109.0.8.0-BMD` creates a plan target `109.0.8.0-BM`. This causes a
version mismatch — FUOTA delivery never starts.

**Workaround:** Never use D-flag in CFW tracks for FUOTA builds.
See `libs/python/corekinect/validation/FUOTA_CONSTRAINTS.md`.

## Device Management — `/System/Devices/`

Source: https://corekinect.atlassian.net/wiki/spaces/EN/pages/2407137281

### Register Device
**Method:** POST `/System/Devices/Register`
**Body:**
```json
{
  "Devices": [
    {"DeviceId": "70B3D584C0201234", "DeviceType": 2, "DeviceVariantId": 3}
  ]
}
```
**Returns:** `{"RegisteredDevices": [...], "DevicesAlreadyRegistered": [...]}`

### Search Devices
**Method:** GET `/System/Devices/Search?page=1&resultsPerPage=100`
**Body (filters):** `{"DeviceId": "*1234", "DeviceTypeId": 9}`

### Set Device Profile (Public Key)
**Method:** POST `/System/Devices/Sessions/Profiles`
**Body:** Device ID + base64(raw EC point bytes) — NOT DER format
**Key format:** Must start with `B` (base64 of 0x04 prefix), NOT `MFkw...` (DER)

## Known Issues

1. **Config Search returns device-reported values, not desired values.**
   PUT `/Configurations/GroundModeV2` sets the desired state on the server.
   POST `/Configurations/GroundModeV2/Search` returns what the device last
   reported. There is no endpoint to read "pending" config. The config is
   delivered to the device on next heartbeat uplink (up to 60 minutes).

   **Impact on validation tests:** Config override tests cannot verify
   server-side state. They can only:
   a) Verify PUT returns 200 (server accepted the desired config)
   b) Wait for the device to heartbeat and report back (slow, minutes)
   c) Power cycle to force immediate heartbeat (requires MTIB)

2. **D-flag stripping on FUOTA plan targets.**
   CoreCloud strips debug flag, causing version mismatch.
   See `libs/python/corekinect/validation/FUOTA_CONSTRAINTS.md`.

3. **Profile upload returns 204 but profileId stays null.**
   Escalated to CoreCloud team (Jared).

4. **Full config required for PUT.**
   Partial config updates return HTTP 400. Must read current config,
   merge changes, then PUT the full object.
