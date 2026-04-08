# Firmware Build & FUOTA Delivery for Stage 4

## Overview

This document covers how firmware is built, how FUOTA (Firmware Update Over The
Air) works in CoreCloud v1.0, how to trigger firmware updates, and the remaining
gaps for Stage 4 validation automation.

---

## 1. Firmware Build System

### Build Controller

The build system lives at `apps/firmware/products/ctl.sh`. It uses Docker with
the NCS (nRF Connect SDK) toolchain image to guarantee reproducible builds.

```bash
# Build everything (mfg + app, all variants, all MTIB revisions)
./apps/firmware/products/ctl.sh build-all alpha

# Build specific target
./apps/firmware/products/ctl.sh build alpha --target mfg
./apps/firmware/products/ctl.sh build alpha --target app --variant debug
./apps/firmware/products/ctl.sh build alpha --target app --variant release

# Parallel build (mfg + app groups concurrently)
./apps/firmware/products/ctl.sh build-all alpha --parallel

# List artifacts
./apps/firmware/products/ctl.sh artifacts alpha

# Collect to validation assets directory
./apps/firmware/products/ctl.sh collect alpha
```

### Docker Image

Each firmware submodule specifies its NCS Docker image in
`.devcontainer/devcontainer.json`:

- **Alpha FW**: `containers.ad.corekinect.com/ncs-fw-dev:2.7.0`
- Docker is available in the dev container — no build server required.

### Build Matrix (Alpha)

| Target | Variant | Output |
|--------|---------|--------|
| mfg | — | `alpha_mfg_fw/alpha_b0/{app_nrf52840,comms_nrf9151}.hex` |
| app | debug | `alpha_fw/alpha_b0/{app_nrf52840,comms_nrf9151}.hex` |
| app | release | Same |

3 build invocations, each producing 2 MCU hex files = 6 total hex files.

### Encryption Keys

MCUboot requires ECDSA-P256 encryption keys (`encryption_key.pem`,
`comms_encryption_key.pem`). These are `.gitignore`d and auto-generated on
first build via `imgtool.py` inside the Docker container.

### Build Outputs

| Format | Contents | Bootloader | Use Case |
|--------|----------|------------|----------|
| `.hex` | Full image (app + bootloader) per MCU | Yes | J-Link flashing |
| `.cfw` | App-only image, encrypted, both MCUs | **No** | FUOTA delivery |
| `.zip` (DFU) | Separate app/comms hex files | No | DFU updates |
| `.zip` (modem) | nRF91x1 modem firmware | N/A | Modem updates |

### Current Artifacts (as of 2026-03-05)

```
artifacts/alpha_mfg_fw/alpha_b0/app_nrf52840.hex    (1.6M)
artifacts/alpha_mfg_fw/alpha_b0/comms_nrf9151.hex    (1.3M)
artifacts/alpha_fw/alpha_b0/app_nrf52840.hex          (1.1M)
artifacts/alpha_fw/alpha_b0/comms_nrf9151.hex         (1.3M)
```

---

## 2. How FUOTA Works (CoreCloud v1.0)

### Architecture

FUOTA is entirely **server-driven**. The device is a passive recipient.

1. Device boots and sends firmware version per App ID (BootMsgV2, UID 548)
2. CoreCloud Socket Server checks the device's FUOTA settings in the DB
3. If firmware doesn't match the plan's next target stage, server starts
   streaming firmware chunks with every uplink response
4. Device writes chunks to external flash, validates, swaps on reboot
5. Device reboots with boot reason `2` ("Reboot due to completing FUOTA")
6. **5-minute cooldown** before next FUOTA can start
7. For dual-MCU devices (Alpha), both processors must complete their stage
   before the device advances to the next stage

### Message Flow

| UID | Message | Direction |
|-----|---------|-----------|
| 544 | Firmware V3 | Device -> Server |
| 545 | Firmware Update V3 | Server -> Device |
| 546 | Firmware Update Response V2 | Device -> Server |
| 547 | Firmware Update Reset V2 | Server -> Device |
| 548 | Boot V2 | Device -> Server |

### Key Timing

- Device uplinks every ~60 seconds
- Each uplink carries one firmware chunk
- A typical firmware image (~100KB) takes ~50-100 uplinks = ~50-100 minutes
- After FUOTA completion: 5-minute cooldown before next update

---

## 3. FUOTA Data Model

### Database Tables

| Table | Purpose |
|-------|---------|
| `fuotaplanstbl` | Plan definitions (description, device type/variant) |
| `fuotaplanstagestbl` | Ordered stages within a plan |
| `fuotaplanstagetargetstbl` | Target firmware version per App ID per stage |
| `fuotasettingsperdevicetbl` | Per-device settings (plan assignment, enable, max stage) |
| `fuotaprogresstbl` | Active transfer progress |
| `fuotaprogresshistorytbl` | Completed transfer records |
| `devicefirmwarecurrenttbl` | Current firmware version per device per App ID |
| `devicefirmwareappidstbl` | App ID registration per device type/variant |

### FUOTA Plan Structure

A plan contains ordered stages. Each stage specifies target firmware versions
for every App ID in the device:

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

### Per-Device FUOTA Settings

```json
{
  "deviceId": "70B3D584C0201234",
  "planId": 1,
  "enableUpdates": true,
  "maxStage": 2
}
```

- `enablefuota` must be explicitly `true` (defaults to `false`)
- `maxstage` limits how far the device can progress in the plan
- Per-device settings override per-device-type defaults

### Firmware Version String Format

`AppId.Major.Minor.Build-Flags`

| Flag | Meaning |
|------|---------|
| `B` | Bench release track |
| `E` | Engineering release track |
| `P` | Production release track |
| `M` | Manufacturing firmware |
| `D` | Debug build |

Examples:
- `109.1.0.0-PM` — App ID 109, v1.0.0, Production, Manufacturing
- `109.2.0.0-P` — App ID 109, v2.0.0, Production Release
- `109.2.0.0-PD` — App ID 109, v2.0.0, Production Debug

### Alpha B0 Device Identity

| Parameter | Value |
|-----------|-------|
| Device Type | 2 |
| Device Variant | 3 |
| Comms Processor App ID | 108 (nRF9151) |
| App Processor App ID | 109 (nRF52840) |

---

## 4. FUOTA Rules and Constraints

### Version Rules
- Firmware versions may only **increase** (major.minor.build comparison)
- **Exception**: Manufacturing-to-production transition (M flag removal)
- No downgrade allowed within the same track

### Release Track Rules
- **No track switching** via FUOTA (Production stays Production, etc.)
- **No debug firmware on Production track** (only Bench/Engineering)
- Track is encoded in flags byte and stored in `releasetrack` column

### Dual-Processor Synchronization
- Both App ID 108 (nRF9151) and App ID 109 (nRF52840) must complete their
  targets in a stage before advancing to the next stage
- `updateorder` field controls which processor updates first within a stage

### RMA / Downgrade
- To downgrade from production to manufacturing firmware, create a FUOTA plan
  with a single stage targeting only manufacturing images

---

## 5. How to Trigger FUOTA

There is **no REST API endpoint** for FUOTA plan management. FUOTA is triggered
by writing directly to the CoreCloud database.

### Step-by-Step

1. **Upload `.cfw` files** to the Socket Server's `fuota/` directory
   - The Socket Server reads firmware binary from this directory
   - File path is stored in the FUOTA plan stage targets

2. **Create a FUOTA plan** (or reuse existing) in `fuotaplanstbl`
   - Set device type/variant to match the target devices

3. **Create plan stages** in `fuotaplanstagestbl`
   - Each stage has an `updatestage` number (1-indexed, ordered)

4. **Create stage targets** in `fuotaplanstagetargetstbl`
   - One entry per App ID per stage
   - Specifies the exact firmware version + release track + mfg flag

5. **Assign the plan to the device** in `fuotasettingsperdevicetbl`
   - Set `planid`, `enablefuota=True`, `maxstage=<target stage>`

6. **Wait** — on next uplink (~60s), the Socket Server evaluates and starts
   pushing chunks automatically

### Using the ORM

```python
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.db_orm_v1_0 import (
    Fuotaplanstbl,
    Fuotaplanstagestbl,
    Fuotaplanstagetargetstbl,
    Fuotasettingsperdevicetbl,
)

with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    session = db.session

    # Create plan
    plan = Fuotaplanstbl(
        plandesc="Stage 4 Validation",
        devicetypeid=2,
        devicevariantid=3,
    )
    session.add(plan)
    session.flush()  # get plan.planid

    # Create stage
    stage = Fuotaplanstagestbl(
        planid=plan.planid,
        updatestage=1,
        stagedesc="Mfg to Prod Debug",
        skippable=False,
    )
    session.add(stage)

    # Create targets (one per App ID)
    for appid, major, minor, rev, track, mfg in [
        (108, 2, 0, 0, 2, False),  # nRF9151 comms
        (109, 2, 0, 0, 2, False),  # nRF52840 app
    ]:
        target = Fuotaplanstagetargetstbl(
            planid=plan.planid,
            updatestage=1,
            appid=appid,
            majorversion=major,
            minorversion=minor,
            revision=rev,
            releasetrack=track,
            ismfg=mfg,
            updateorder=1,
        )
        session.add(target)

    # Assign to device
    settings = Fuotasettingsperdevicetbl(
        deviceid=0x70B3D584C01E1FCC,
        planid=plan.planid,
        enablefuota=True,
        maxstage=1,
    )
    session.add(settings)
    session.commit()
```

---

## 6. The `.cfw` File Gap

The build system (`ctl.sh`) produces `.hex` files. FUOTA delivery requires
`.cfw` files — encrypted, app-only images without the bootloader.

**Status**: The `.cfw` generation process is not in `ctl.sh`. It may be:
- A separate tool in the firmware submodule
- Part of the Socket Server's file processing
- A manual step using MCUboot's `imgtool.py`

**TODO**: Confirm with Robert how `.cfw` files are generated from build output.

---

## 7. Blockers for Stage 4 FUOTA Testing

| Blocker | Status | Resolution |
|---------|--------|------------|
| User login registered in VAL CoreCloud | **Blocked** | Admin must register login via REST API |
| Device registered in VAL CoreCloud | **Blocked** | Needs REST API access (blocked by above) |
| Device personalized against VAL | **Blocked** | Needs CoreOps pointing to VAL or manual DB registration |
| `.cfw` file generation | **Unknown** | Need to confirm process with Robert |
| FUOTA plan creation in VAL DB | **Ready** | Can do via direct DB/ORM access once device is registered |
| Socket Server `fuota/` directory access | **Unknown** | Need SSH access to VAL Socket Server host |

---

## 8. Key File References

| Purpose | Path |
|---------|------|
| Build controller | `apps/firmware/products/ctl.sh` |
| Alpha build script | `apps/firmware/products/alpha/scripts/build.sh` |
| FUOTA implementation (mfg FW) | `apps/firmware/products/alpha/alpha_mfg_fw/src/app/fuota.{c,h}` |
| FUOTA implementation (prod FW) | `apps/firmware/products/alpha/alpha_fw/src/app/fuota.{c,h}` |
| FUOTA architecture doc | `docs/validation/architecture/stage4-fuota-validation-flow.md` |
| FUOTA protocol research | `docs/validation/research/06-fuota-corecloud-v1.md` |
| FUOTA validation plan | `docs/validation/plans/stage4-proof/phases/phase-5-fuota-flow.md` |
| DB ORM definitions | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` |
| Firmware build API (Concord) | `apps/backend/http-api/src/api/v2/catalog/firmware_builds.py` |
| Sigma5 firmware service | `apps/validation/sigma5/src/services/firmware.py` |

---

## 9. Confluence References

- [Firmware Update Strategy](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2704080902)
- [Device Firmware Versioning SS V1.0](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2604630046)
- [Alpha App and PSP FUOTA](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2916417551)
- [CoreCloud Administration Guide](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2793504769)
- [How to FUOTA (legacy)](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2207842305)
