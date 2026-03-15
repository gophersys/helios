# FUOTA in CoreCloud v1.0

## Overview

FUOTA (Firmware Update Over The Air) is the mechanism by which CoreCloud v1.0 delivers firmware updates to deployed devices. Updates are managed through **plans** containing ordered **stages**, each stage specifying **target firmware versions** per Application ID. The server evaluates FUOTA eligibility on every device uplink, determines the next required update, and streams firmware chunks alongside normal uplink responses.

This document covers the FUOTA architecture, data model, constraints, and the gaps that must be addressed for Stage 4 validation automation.

---

## 1. Architecture

### Server-Side Evaluation

FUOTA is entirely server-driven. The CoreCloud socket server evaluates FUOTA on every device packet uplink:

1. Device connects and sends a boot message containing its current firmware versions (one per App ID).
2. Server looks up the device's FUOTA settings (`fuotasettingsperdevicetbl`) to find its assigned `planId`, whether updates are enabled (`enablefuota`), and the maximum stage it may progress to (`maxstage`).
3. Server loads the FUOTA plan (`fuotaplanstbl`) and its stages (`fuotaplanstagestbl`) with target versions (`fuotaplanstagetargetstbl`).
4. Server compares the device's current firmware versions against the plan's stages to determine the next required update.
5. If an update is needed, the server begins sending firmware chunks (pages) with every subsequent uplink until the transfer is complete.
6. After FUOTA completion, the device reboots (boot reason = `2: Reboot due to completing FUOTA`) and reports its new firmware version in the next boot message.
7. A **5-minute cooldown** is enforced between FUOTA completions before the next update can begin.

### Device-Side Behavior

- The device is a passive recipient; it does not request updates.
- Firmware chunks arrive piggy-backed on uplink responses.
- The device applies chunks to external flash, then validates and swaps on reboot.
- Both processors (comms + app) must be in the same plan stage before the next stage can begin.

### Message UIDs Involved

| UID | Message | Direction |
|-----|---------|-----------|
| 504 | Firmware Update | Server -> Device |
| 505 | Firmware Update Response | Device -> Server |
| 506 | Firmware Update Reset | Server -> Device |
| 510 | Firmware Update Prepare | Server -> Device |
| 511 | Firmware Update V2 | Server -> Device |
| 513 | Boot | Device -> Server |
| 514 | Firmware V2 | Device -> Server |
| 544 | Firmware V3 | Device -> Server |
| 545 | Firmware Update V3 | Server -> Device |
| 546 | Firmware Update Response V2 | Device -> Server |
| 547 | Firmware Update Reset V2 | Server -> Device |
| 548 | Boot V2 | Device -> Server |

---

## 2. Data Model

### Entity Relationship

```
fuotaplanstbl (Plan)
  |-- devicetypeid, devicevariantid --> devicetypevarianttbl
  |
  +-- fuotaplanstagestbl (Stages)
  |     PK: (planid, updatestage)
  |
  +-- fuotaplanstagetargetstbl (Stage Targets)
  |     PK: (planid, updatestage, appid)
  |     Fields: releasetrack, ismfg, majorversion, minorversion, revision, updateorder
  |
  +-- fuotasettingsperdevicetbl (Per-Device Settings)
  |     PK: deviceid
  |     FK: planid -> fuotaplanstbl, deviceid -> devicestbl
  |     Fields: enablefuota, maxstage
  |
  +-- fuotasettingsperdevicetypetbl (Per-Device-Type Settings)
        PK: (devicetypeid, devicevariantid, accountid)
        Fields: enablefuota, maxstage

fuotaprogresstbl (Active Progress)
  PK: (deviceid, appid)
  Fields: majorversion, minorversion, revision, releasetrack, ismfg,
          pagesapplied, totalpages, timestarted, lastupdated

fuotaprogresshistorytbl (Completed Transfers)
  PK: recordid
  Indexed on: deviceid
  Fields: (same as progress) + timefinished

devicefirmwarecurrenttbl (Current FW Versions)
  PK: (deviceid, appid)
  Fields: majorversion, minorversion, revision, releasetrack, ismfg, lastupdated
```

### ORM Classes

All defined in `libs/python/corekinect/core_cloud/db_orm_v1_0.py`:

| ORM Class | Table | Purpose |
|-----------|-------|---------|
| `Fuotaplanstbl` | `fuotaplanstbl` | FUOTA plan definition (description, device type/variant) |
| `Fuotaplanstagestbl` | `fuotaplanstagestbl` | Ordered stages within a plan |
| `Fuotaplanstagetargetstbl` | `fuotaplanstagetargetstbl` | Target firmware version per app ID per stage |
| `Fuotasettingsperdevicetbl` | `fuotasettingsperdevicetbl` | Per-device FUOTA settings (plan assignment, enable, max stage) |
| `Fuotasettingsperdevicetypetbl` | `fuotasettingsperdevicetypetbl` | Default FUOTA settings per device type/variant/account |
| `Fuotaprogresstbl` | `fuotaprogresstbl` | Active FUOTA transfer progress |
| `Fuotaprogresshistorytbl` | `fuotaprogresshistorytbl` | Historical FUOTA transfer records |
| `Fuotasettingsperdevicehistorytbl` | `fuotasettingsperdevicehistorytbl` | Audit trail for per-device settings changes |
| `Fuotasettingsperdevicetypehistorytbl` | `fuotasettingsperdevicetypehistorytbl` | Audit trail for per-device-type settings changes |
| `Devicefirmwarecurrenttbl` | `devicefirmwarecurrenttbl` | Current firmware version per device per app ID |
| `Devicefirmwareappidstbl` | `devicefirmwareappidstbl` | App ID registration per device type/variant |

---

## 3. FUOTA Plan Structure

A plan is a sequence of firmware stages. Each stage defines the target firmware version for every App ID in the device.

### Example Plan (JSON representation)

```json
{
  "description": "Alpha B0 Production Rollout",
  "deviceType": 2,
  "deviceVariant": 3,
  "stages": [
    {
      "description": "Factory image",
      "isSkippable": false,
      "targets": ["108.1.0.0-PM", "109.1.0.0-PM"]
    },
    {
      "description": "Latest production",
      "isSkippable": false,
      "targets": ["108.2.0.0-P", "109.2.0.0-P"]
    }
  ]
}
```

### How Stages Map to Database Tables

| JSON Field | Table | Column |
|------------|-------|--------|
| `description` (plan) | `fuotaplanstbl` | `plandesc` |
| `deviceType` | `fuotaplanstbl` | `devicetypeid` |
| `deviceVariant` | `fuotaplanstbl` | `devicevariantid` |
| `stages[n].description` | `fuotaplanstagestbl` | `stagedesc` |
| `stages[n].isSkippable` | `fuotaplanstagestbl` | `skippable` |
| `stages[n]` (order) | `fuotaplanstagestbl` | `updatestage` (integer, 1-indexed) |
| `stages[n].targets[m]` | `fuotaplanstagetargetstbl` | `appid`, `majorversion`, `minorversion`, `revision`, `releasetrack`, `ismfg` |

### Target Version String Encoding

A target like `"109.2.0.0-P"` maps to:

| Field | Value |
|-------|-------|
| `appid` | 109 |
| `majorversion` | 2 |
| `minorversion` | 0 |
| `revision` | 0 |
| `releasetrack` | 2 (Production) |
| `ismfg` | false |

---

## 4. Device FUOTA Settings

Each device has individual FUOTA settings that control its update behavior.

### Example Settings (JSON representation)

```json
{
  "deviceId": "70B3D584C0201234",
  "planId": 1,
  "enableUpdates": true,
  "maxStage": 2
}
```

### Database Mapping

| JSON Field | Column (`fuotasettingsperdevicetbl`) |
|------------|--------------------------------------|
| `deviceId` | `deviceid` (BigInteger, hex device ID converted to int) |
| `planId` | `planid` (FK to `fuotaplanstbl`) |
| `enableUpdates` | `enablefuota` (Boolean) |
| `maxStage` | `maxstage` (Integer) |

### Key Behaviors

- **`enablefuota` must be explicitly set to `true`** for a device to receive any updates. Defaults to `false`.
- **`maxstage` limits progression** through the plan. A device will not advance beyond this stage number even if higher stages exist in the plan.
- **Per-device settings override per-device-type defaults** (`fuotasettingsperdevicetypetbl`).
- Both per-device and per-device-type settings maintain history tables for audit.

---

## 5. Firmware Version Format

### Binary Layout (7 bytes)

```
Byte 0-1:  App ID          (16-bit, big-endian)
Byte 2:    Flags           (8-bit)
Byte 3:    Major Version   (8-bit)
Byte 4:    Minor Version   (8-bit)
Byte 5-6:  Build/Revision  (16-bit, big-endian)
```

### Flags Byte

```
Bit 7-4:  Reserved
Bit 3:    Debug flag (1 = debug build)
Bit 2-1:  Release Track
             00 = Bench (0)
             01 = Engineering (1)
             10 = Production (2)
Bit 0:    Manufacturing flag (1 = manufacturing firmware)
```

### String Format

`AppId.Major.Minor.Build-Flags`

Where Flags characters are:
- `B` = Bench, `E` = Engineering, `P` = Production (release track)
- `M` = Manufacturing
- `D` = Debug

### Examples

| String | App ID | Major | Minor | Build | Track | Mfg | Debug |
|--------|--------|-------|-------|-------|-------|-----|-------|
| `109.1.0.0-PM` | 109 | 1 | 0 | 0 | Production | Yes | No |
| `109.2.0.0-P` | 109 | 2 | 0 | 0 | Production | No | No |
| `109.2.0.0-PD` | 109 | 2 | 0 | 0 | Production | No | Yes |
| `108.1.0.0-PM` | 108 | 1 | 0 | 0 | Production | Yes | No |
| `109.1.0.5-E` | 109 | 1 | 0 | 5 | Engineering | No | No |
| `109.0.1.0-BD` | 109 | 0 | 1 | 0 | Bench | No | Yes |

### Database Version Fields

The `Devicefirmwarecurrenttbl` stores the currently running firmware per device per app ID:

| Column | Type | Description |
|--------|------|-------------|
| `deviceid` | BigInteger | Device identifier |
| `appid` | Integer | Application ID (108, 109, etc.) |
| `majorversion` | Integer | Major version number |
| `minorversion` | Integer | Minor version number |
| `revision` | Integer | Build/revision number |
| `releasetrack` | SmallInteger | 0=Bench, 1=Engineering, 2=Production |
| `ismfg` | Boolean | Manufacturing firmware flag |
| `lastupdated` | DateTime | Last time this record was updated |

---

## 6. FUOTA Rules and Constraints

### Version Ordering

- Firmware versions may ONLY increase (major.minor.build comparison).
- **Exception**: Manufacturing-to-production transition. Manufacturing firmware (M flag) can be replaced by production firmware of the same or higher version.

### Release Track Rules

- **No release track switching.** Bench, Engineering, and Production are separate tracks.
- A device on the Production track cannot receive Engineering or Bench firmware via FUOTA.
- Track is encoded in the flags byte and stored in `releasetrack` columns.

### Debug Firmware Rules

- **No debug firmware on production release tracks** via FUOTA.
- Debug builds (D flag) are only valid on Bench and Engineering tracks.
- Debug builds are used for development and validation testing but must not ship to production devices.

### Manufacturing Firmware Rules

- Manufacturing firmware (M flag) shares the same App ID as production firmware.
- Version comparison still applies: a manufacturing v1.0.0 is compared against production v1.0.0.
- The manufacturing-to-production transition is the one case where the "versions only increase" rule has a special exception.

### Dual-Processor Synchronization

- Both processors must be in the same plan stage before the next stage begins.
- For Alpha B0: App ID 108 (nRF9151 comms) and App ID 109 (nRF52840 app) must both match their respective targets in a stage before the device advances to the next stage.
- The `updateorder` field in `fuotaplanstagetargetstbl` controls which processor gets updated first within a stage.

### Cooldown

- **5-minute cooldown** between FUOTA completions before the next update can start.
- This prevents rapid successive updates that could destabilize the device.

---

## 7. Alpha B0 Specifics

### Device Identity

| Parameter | Value |
|-----------|-------|
| Device Type | 2 |
| Device Variant | 3 |
| Comms Processor | nRF9151 (App ID 108) |
| App Processor | nRF52840 (App ID 109) |

### Build Artifacts

| Extension | Purpose | Contains Bootloader | Encrypted |
|-----------|---------|---------------------|-----------|
| `.hex` | J-Link flashing | Yes | No |
| Encrypted `.hex` | Secure J-Link flashing | Yes | Yes |
| `.cfw` | FUOTA delivery | No (bootloader omitted) | Yes |

The `.cfw` file is the artifact used by CoreCloud for FUOTA delivery. It omits the bootloader because FUOTA updates the application only; the bootloader is flashed once during manufacturing and is not updated OTA.

### Manufacturing Firmware

- Has the `IS_MANUFACTURING` flag set (bit 0 of flags byte).
- Includes manufacturing-specific test routines (sensor self-test, calibration, etc.).
- Uses the same App IDs (108, 109) as production firmware.
- First FUOTA transition in the field is typically manufacturing -> production.

### Boot Message (UID 548)

The `BootMsgV2` class (in `libs/python/corekinect/core_cloud/msg_def_v1_0.py`) decodes the boot message that reports firmware versions. Key fields:

| Field | Bits | Values |
|-------|------|--------|
| MCU Type | `flags[6:7]` | 0 = Comms Core, 1 = App Core |
| FW Triggered | `flags[5]` | 0 = Soft reset, 1 = FW-triggered |
| Boot Reason | `flags[0:4]` | 0 = Normal, 1 = Exception, **2 = FUOTA complete**, 3 = Charger, 4 = Error, 5 = Reboot msg, 6 = Watchdog, 7 = User button |

Boot reason `2` ("Reboot due to completing FUOTA") is the primary signal that a FUOTA transfer finished successfully.

---

## 8. FUOTA Progress Tracking

### Active Transfer (`fuotaprogresstbl`)

During an active FUOTA transfer, progress is tracked per device per app ID:

| Column | Description |
|--------|-------------|
| `deviceid` | Device being updated |
| `appid` | App ID being updated (108 or 109) |
| `majorversion` | Target firmware major version |
| `minorversion` | Target firmware minor version |
| `revision` | Target firmware build/revision |
| `releasetrack` | Target release track |
| `ismfg` | Target is manufacturing firmware |
| `pagesapplied` | Number of firmware pages (chunks) successfully sent |
| `totalpages` | Total number of pages in the firmware image |
| `timestarted` | When the transfer began |
| `lastupdated` | When the last page was sent |

**Completion indicator**: `pagesapplied == totalpages` means all chunks have been sent. The device will then reboot and report the new version.

### Transfer History (`fuotaprogresshistorytbl`)

Completed transfers are archived here with an additional `timefinished` field. This provides a full audit trail of all FUOTA operations per device.

---

## 9. API Access for Automation

### What Exists

**Database ORM (fully available):**

The SQLAlchemy ORM in `libs/python/corekinect/core_cloud/db_orm_v1_0.py` provides complete access to all FUOTA tables:

```python
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.db_orm_v1_0 import (
    Fuotaplanstbl,
    Fuotaplanstagestbl,
    Fuotaplanstagetargetstbl,
    Fuotasettingsperdevicetbl,
    Fuotaprogresstbl,
    Fuotaprogresshistorytbl,
    Devicefirmwarecurrenttbl,
)

# Example: Query current firmware versions for a device
with CoreCloudDBInterface(db_env="VAL_1_0") as session:
    fw_versions = session.query(Devicefirmwarecurrenttbl).filter(
        Devicefirmwarecurrenttbl.deviceid == device_id_int
    ).all()
```

**REST API (limited):**

The `CoreCloudRestInterface` in `libs/python/corekinect/core_cloud/api_interface.py` supports:
- Authenticated token-based requests with auto-refresh
- Namespaced environment configuration (`VAL_1_0`, `DEV_1_0`, `DEV_0_9`)
- GPS configuration endpoints (`/System/Devices/Configurations/Gps`)

It does **NOT** expose any FUOTA plan CRUD endpoints.

### What Is Missing

The Python SDK has **no REST endpoints** for FUOTA operations. Specifically, there are no methods for:
- Creating, reading, updating, or deleting FUOTA plans
- Creating or modifying plan stages and targets
- Setting or updating per-device FUOTA settings
- Querying FUOTA progress via REST

### Possible Paths Forward

| Approach | Pros | Cons |
|----------|------|------|
| **1. Discover existing C# REST endpoints** | Uses official API with business logic validation; no direct DB manipulation | Requires documentation from C# team; endpoints may not exist or may be incomplete |
| **2. Direct database access via ORM** | Works immediately; full control over all tables; Python ORM is already defined | Bypasses server-side business logic (cooldown enforcement, version validation); risk of data inconsistency |
| **3. Request new REST endpoints** | Clean, official API; proper validation and audit | Requires C# team development time; timeline dependency |
| **4. Hybrid approach** | Use ORM for reads (progress monitoring, version queries) and REST for writes (if endpoints are discovered) | Complexity of two access patterns |

**Recommended for Stage 4**: Start with **approach 2 (direct ORM)** for initial automation, since the ORM is fully defined and the `CoreCloudDBInterface` supports the `VAL_1_0` environment. Simultaneously pursue **approach 1** to discover whether C# REST endpoints exist. Migrate writes to REST endpoints once available.

---

## 10. FUOTA Flow for Validation (Stage 4 Pipeline)

The validation pipeline must orchestrate a series of FUOTA transitions to verify that the firmware update mechanism itself works correctly, and that each firmware variant can be delivered and activated.

### Required Transitions

| # | From | To | Purpose |
|---|------|----|---------|
| 1 | Manufacturing FW | Manufacturing FW (newer) | Test FUOTA mechanism with mfg firmware |
| 2 | Manufacturing FW | Production Debug FW | Test mfg-to-production transition |
| 3 | Production Debug FW | Production Debug FW (same version) | Verify FUOTA re-application / idempotency |
| 4 | Production Debug FW | Production Non-Debug FW | Test debug-to-release transition |
| 5 | Previous Production FW | New Production Debug FW | Real upgrade path (version increase) |
| 6 | New Production Debug FW | New Production Non-Debug FW | Final release transition |

### Per-Transition Procedure

Each transition follows this sequence:

```
1. PLAN SETUP
   - Create or select a FUOTA plan with the target firmware as a stage
   - Ensure .cfw artifacts are uploaded to CoreCloud for the target version

2. DEVICE CONFIGURATION
   - Set device FUOTA settings:
     - planId = <selected plan>
     - enablefuota = true
     - maxstage = <target stage number>

3. WAIT FOR UPLINK
   - Device must perform a packet uplink for the server to evaluate FUOTA
   - Server compares current FW version against plan stage targets
   - If update is needed, server begins sending chunks

4. MONITOR PROGRESS
   - Poll fuotaprogresstbl for pagesapplied vs totalpages
   - OR monitor device boot messages for boot_reason = 2 (FUOTA complete)

5. VERIFY COMPLETION
   - Confirm device reboots with boot_reason = 2
   - Query devicefirmwarecurrenttbl for updated firmware version
   - Verify both App IDs (108 + 109) report expected versions

6. COOLDOWN
   - Wait 5 minutes before initiating next FUOTA transition
   - This is server-enforced; attempting earlier will be silently delayed
```

### Automation Pseudocode

```python
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.db_orm_v1_0 import (
    Fuotasettingsperdevicetbl,
    Fuotaprogresstbl,
    Devicefirmwarecurrenttbl,
)

def configure_device_fuota(session, device_id: int, plan_id: int, max_stage: int):
    """Set device FUOTA settings to trigger an update."""
    settings = session.query(Fuotasettingsperdevicetbl).filter(
        Fuotasettingsperdevicetbl.deviceid == device_id
    ).first()

    if settings:
        settings.planid = plan_id
        settings.enablefuota = True
        settings.maxstage = max_stage
    else:
        settings = Fuotasettingsperdevicetbl(
            deviceid=device_id,
            planid=plan_id,
            enablefuota=True,
            maxstage=max_stage,
        )
        session.add(settings)
    session.commit()


def wait_for_fuota_completion(session, device_id: int, app_id: int, timeout_s: int = 600):
    """Poll FUOTA progress until complete or timeout."""
    import time
    start = time.time()
    while time.time() - start < timeout_s:
        progress = session.query(Fuotaprogresstbl).filter(
            Fuotaprogresstbl.deviceid == device_id,
            Fuotaprogresstbl.appid == app_id,
        ).first()

        if progress and progress.pagesapplied == progress.totalpages:
            return True  # Transfer complete, device will reboot

        time.sleep(10)  # Poll every 10 seconds
    return False  # Timeout


def verify_firmware_version(session, device_id: int, app_id: int,
                            expected_major: int, expected_minor: int, expected_rev: int):
    """Verify device is running the expected firmware version."""
    current = session.query(Devicefirmwarecurrenttbl).filter(
        Devicefirmwarecurrenttbl.deviceid == device_id,
        Devicefirmwarecurrenttbl.appid == app_id,
    ).first()

    if not current:
        return False

    return (current.majorversion == expected_major
            and current.minorversion == expected_minor
            and current.revision == expected_rev)
```

### Timing Considerations

| Phase | Expected Duration | Notes |
|-------|-------------------|-------|
| Device uplink interval | Unknown | Determines minimum wait before FUOTA starts |
| Chunk transfer | Minutes to tens of minutes | Depends on firmware size and uplink frequency |
| Device reboot | 5-15 seconds | After all chunks received |
| Post-FUOTA boot message | Next uplink cycle | Confirms new version |
| Cooldown | 5 minutes | Server-enforced between completions |
| Full 6-transition sequence | Estimated 1-3 hours | Dominated by uplink intervals and cooldowns |

---

## 11. Database Access Configuration

The `CoreCloudDBInterface` supports three environment namespaces:

| Namespace | Purpose | Env Var Prefix |
|-----------|---------|----------------|
| `VAL_1_0` | Validation environment (v1.0 database) | `VAL_1_0_DB_*`, `VAL_1_0_SSH_*` |
| `DEV_1_0` | Development environment (v1.0 database) | `DEV_1_0_DB_*`, `DEV_1_0_SSH_*` |
| `DEV_0_9` | Legacy development environment (v0.9) | `DEV_0_9_DB_*`, `DEV_0_9_SSH_*` |

The REST interface (`CoreCloudRestInterface`) supports the same namespaces with API-specific env vars:

| Env Var | Purpose |
|---------|---------|
| `{NS}_API_AUTH_SERVER_HOST_NAME` | Auth server hostname |
| `{NS}_API_AUTH_USERNAME` | Auth username |
| `{NS}_API_AUTH_PASSWORD` | Auth password |
| `{NS}_API_REST_SERVER_HOST_NAME` | REST API hostname |
| `{NS}_API_KEY` | API key |

For Stage 4 validation automation, use `VAL_1_0` as the target environment.

---

## 12. Gaps and Open Questions

### Critical Gaps

1. **No FUOTA REST API in Python SDK.** The `CoreCloudRestInterface` has no methods for FUOTA plan CRUD or device FUOTA settings. All FUOTA management must go through direct database access or undocumented C# endpoints.

2. **C# REST server endpoints undocumented.** The CoreCloud C# server likely has FUOTA management endpoints, but they are not documented in the Python library or accessible via the Python SDK.

3. **No `.cfw` upload mechanism.** The pipeline needs to upload firmware `.cfw` files to CoreCloud for FUOTA delivery. The mechanism for this (REST endpoint, S3 bucket, manual upload) is not documented in the Python SDK.

### Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | What is the device uplink interval? | Determines minimum FUOTA initiation latency and total pipeline duration |
| 2 | Can FUOTA be triggered immediately, or only on the next scheduled uplink? | Affects whether we can accelerate the pipeline |
| 3 | Is there a way to force a device uplink? | Could dramatically reduce pipeline execution time |
| 4 | What happens if FUOTA fails mid-transfer? | Need to understand retry behavior: automatic retry, manual reset, or stuck state |
| 5 | How does the 5-minute cooldown affect back-to-back transitions? | Six transitions with 5-minute cooldowns = 25 minutes of pure cooldown time |
| 6 | Does `updateorder` in `fuotaplanstagetargetstbl` control which processor updates first within a stage? | Need to confirm ordering semantics for dual-processor updates |
| 7 | What is the maximum `.cfw` file size supported? | Determines if large firmware images need chunking at the plan level |
| 8 | Can a FUOTA plan be modified while a device is mid-transfer? | Safety concern for plan management during active fleet updates |
| 9 | Does the per-device-type setting (`fuotasettingsperdevicetypetbl`) act as a default that per-device settings override? | Clarifies the settings hierarchy |
| 10 | How are `.cfw` files associated with plan stage targets? | Need to understand the link between the version specified in a target and the actual binary artifact |

### Action Items

- [ ] Contact CoreCloud C# team to document existing FUOTA REST endpoints
- [ ] Determine `.cfw` file upload mechanism and storage location
- [ ] Measure device uplink interval in validation environment
- [ ] Test direct ORM writes to `fuotasettingsperdevicetbl` and verify server honors them
- [ ] Build prototype automation script using `CoreCloudDBInterface` with `VAL_1_0` environment
- [ ] Validate that boot reason `2` reliably indicates FUOTA completion in `BootMsgV2` messages

---

## References

| Resource | Path |
|----------|------|
| Database ORM (v1.0) | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` |
| REST API Interface | `libs/python/corekinect/core_cloud/api_interface.py` |
| DB Connection Interface | `libs/python/corekinect/core_cloud/db_interface.py` |
| Message Definitions (v1.0) | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` |
| BootMsgV2 (UID 548) | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` (line ~1240) |
