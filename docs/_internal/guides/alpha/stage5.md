# Stage 5 Alpha Example — Gate (PR Validation + FUOTA)

> Step-by-step walkthrough of Stage 5 (Gate) validation for the Alpha B0 device.
> This is the **merge blocker** that runs on every PR.
> Duration: **< 15 minutes** (hard limit). Includes FUOTA verification.

---

## 1. Overview

Stage 5 Gate is the **fast validation + FUOTA** check that runs on every PR. It proves:

1. Device can be flashed via J-Link
2. Device boots and draws expected power
3. Device can be personalized and reach CoreCloud
4. **FUOTA works** (firmware update over the air)
5. Device boots correctly after FUOTA

**Why FUOTA is mandatory**: FUOTA is the highest-risk operation. A broken OTA can brick devices in the field. Every PR must prove OTA works.

---

## 2. Timing Budget (Hard Limit: 15 min)

| Step | Max | Typical | Timeout Action |
|------|-----|---------|----------------|
| Connect MTIB | 10s | 5s | Fail |
| Flash nRF52840 | 35s | 30s | Fail |
| Flash modem | 50s | 45s | Fail |
| Flash nRF9151 | 35s | 30s | Fail |
| Boot verify | 15s | 10s | Fail |
| Personalization | 90s | 60s | Fail |
| Cloud check-in | 120s | 90s | Fail |
| CFW upload | 30s | 15s | Fail |
| FUOTA create/assign | 20s | 10s | Fail |
| **FUOTA delivery** | **480s** | **300s** | **Fail** |
| Post-FUOTA boot | 15s | 10s | Fail |
| Cleanup | 10s | 5s | Warn |
| **TOTAL** | **900s** | **~600s** | — |

---

## 3. Test Sequence

```
GATE-01: Flash firmware (nRF52840 → modem → nRF9151)
    ↓
GATE-02: Verify boot (power cycle, check >5mA current)
    ↓
GATE-03: Personalize (lock shell, EC keygen, upload key)
    ↓
GATE-04: Cloud check-in (wait for device to report)
    ↓
GATE-05: FUOTA delivery (upload → plan → assign → monitor → complete)
    ↓
GATE-06: Post-FUOTA boot (power cycle, verify device alive)
```

---

## 4. Step-by-Step Implementation

### 4.1 GATE-01: Flash Firmware

```python
@pytest.mark.timeout(120)
def test_01_flash_firmware(self, ctx, pipeline_assets):
    """GATE-01: Flash all 3 targets via J-Link (< 2 min)."""
    from protocols.mtib.mtib_pb2 import FwFileInfo, HostType

    # Download hex files from pipeline
    app_hex = pipeline_assets.get_hex("mfg_base", "app")
    comms_hex = pipeline_assets.get_hex("mfg_base", "comms")
    modem_zip = Path("/app/firmware/modem/mfw_nrf91x1_2.0.2.zip")

    # Ensure power is on for SWD access
    ctx.fixture.power_on()
    time.sleep(3)

    # Flash nRF52840 (app processor)
    ctx.mtib.UploadFwFile(app_hex, HostType.HOST_TYPE_NRF52840)
    file_info = FwFileInfo(name=Path(app_hex).name, target=HostType.HOST_TYPE_NRF52840)
    time_ms, err = ctx.mtib.FlashFwFile(file_info, sector_erase=True, recover=True)
    assert not err, f"nRF52840 flash failed: {err}"
    log.info("nRF52840 flashed in %dms", time_ms)

    # Flash modem baseband
    ctx.mtib.UploadFwFile(str(modem_zip), HostType.HOST_TYPE_NRF9160_MODEM)
    file_info = FwFileInfo(name=modem_zip.name, target=HostType.HOST_TYPE_NRF9160_MODEM)
    time_ms, err = ctx.mtib.FlashFwFile(file_info, sector_erase=True, recover=True)
    assert not err, f"Modem flash failed: {err}"
    log.info("Modem flashed in %dms", time_ms)

    # Flash nRF9151 (comms processor)
    ctx.mtib.UploadFwFile(comms_hex, HostType.HOST_TYPE_NRF9151)
    file_info = FwFileInfo(name=Path(comms_hex).name, target=HostType.HOST_TYPE_NRF9151)
    time_ms, err = ctx.mtib.FlashFwFile(file_info, sector_erase=True, recover=True)
    assert not err, f"nRF9151 flash failed: {err}"
    log.info("nRF9151 flashed in %dms", time_ms)
```

**Flash order matters**: nRF52840 first (clears APPROTECT), modem second (baseband), nRF9151 last (comms app).

### 4.2 GATE-02: Verify Boot

```python
@pytest.mark.timeout(30)
def test_02_verify_boot(self, ctx):
    """GATE-02: Verify device boots after flash (< 30s)."""
    ctx.fixture.power_off()
    time.sleep(2)
    ctx.fixture.power_on()
    time.sleep(10)  # boot_settle_s

    powered = ctx.fixture.verify_dut_powered(min_current_ma=5.0)
    assert powered, "Device not drawing current after boot"
```

### 4.3 GATE-03: Personalize

```python
@pytest.mark.timeout(90)
def test_03_personalize(self, ctx, config):
    """GATE-03: Personalize device (< 90s)."""
    from corekinect.test.device_personalizer import DevicePersonalizer

    personalizer = DevicePersonalizer(
        mtib=ctx.mtib,
        snr=config.device_snr,
        known_device_id=config.device_id,
    )
    result = personalizer.personalize()
    assert result.success, f"Personalization failed: {result.error}"
    log.info("Personalized: device_id=%s", result.device_id)
```

**Personalization sequence**:
1. Power cycle DUT
2. Open UART BEFORE power-on (catch boot output)
3. Spam `lock_shell` within 2s window
4. Send `personalize <device_id>`
5. Parse response for public key
6. Upload key to CoreCloud

### 4.4 GATE-04: Cloud Check-in

```python
@pytest.mark.timeout(120)
def test_04_cloud_checkin(self, ctx, fuota_client, config):
    """GATE-04: Wait for device to check into CoreCloud (< 2 min)."""
    device_id = config.device_id

    # Power cycle to trigger fresh check-in
    ctx.fixture.power_off()
    time.sleep(2)
    ctx.fixture.power_on()
    time.sleep(15)

    # Get initial recordId
    initial = fuota_client.get_record_id(device_id)

    # Poll for new check-in
    deadline = time.time() + 90
    while time.time() < deadline:
        current = fuota_client.get_record_id(device_id)
        if current > initial:
            log.info("Device checked in: recordId %d -> %d", initial, current)
            return
        time.sleep(10)

    pytest.fail("Device did not check into CoreCloud within timeout")
```

### 4.5 GATE-05: FUOTA Delivery

```python
@pytest.mark.timeout(480)
def test_05_fuota_delivery(self, ctx, fuota_client, pipeline_assets, config):
    """GATE-05: Execute FUOTA and verify completion (< 8 min)."""
    device_id = config.device_id

    # 1. Upload CFW files
    log.info("Uploading CFW files...")
    for cfw_path in pipeline_assets.get_cfw_files("mfg_base"):
        fuota_client.upload_cfw(cfw_path)
    for cfw_path in pipeline_assets.get_cfw_files("mfg_bump"):
        fuota_client.upload_cfw(cfw_path)

    # 2. Parse CFW headers for target strings
    source_targets = config.source_cfw_targets  # e.g., ["108.0.5.0-BM", "109.0.5.0-BM"]
    target_targets = config.target_cfw_targets  # e.g., ["108.0.5.1-BM", "109.0.5.1-BM"]

    # 3. Create FUOTA plan
    log.info("Creating FUOTA plan: %s -> %s", source_targets, target_targets)
    plan_id = fuota_client.create_plan(
        stages=[
            {"targets": source_targets, "description": "Source"},
            {"targets": target_targets, "description": "Target"},
        ],
        device_type_id=2,
        device_variant_id=3,
    )
    log.info("Created plan %d", plan_id)

    # 4. Assign device to plan
    fuota_client.ensure_device_registered(device_id)
    fuota_client.assign_device(
        plan_id=plan_id,
        device_ids=[device_id],
        max_stage=1,
        enable=True,
    )
    log.info("Assigned device to plan")

    # 5. Power cycle to trigger FUOTA
    ctx.fixture.power_off()
    time.sleep(2)
    ctx.fixture.power_on()
    time.sleep(10)

    # 6. Monitor progress
    log.info("Monitoring FUOTA progress...")
    deadline = time.time() + 420  # 7 min
    while time.time() < deadline:
        progress = fuota_client.get_progress(device_id)
        if progress:
            log.info("Progress: %s", progress)
            if progress.get("isComplete"):
                log.info("FUOTA complete!")
                break
        time.sleep(10)
    else:
        pytest.fail("FUOTA did not complete within timeout")

    # 7. Cleanup
    fuota_client.disable_device(device_id, plan_id)
```

**FUOTA timeline**:
- t=0: Device boots with MFG_BASE
- t=15s: LTE attach
- t=30s: Heartbeat → server responds with FUOTA command
- t=1-5m: Device downloads CFW fragments
- t=5-6m: Verify + write + reboot
- t=6-7m: Device boots with MFG_BUMP

### 4.6 GATE-06: Post-FUOTA Boot

```python
@pytest.mark.timeout(30)
def test_06_post_fuota_boot(self, ctx):
    """GATE-06: Verify device boots after FUOTA (< 30s)."""
    ctx.fixture.power_off()
    time.sleep(2)
    ctx.fixture.power_on()
    time.sleep(10)

    powered = ctx.fixture.verify_dut_powered(min_current_ma=5.0)
    assert powered, "Device not drawing current after FUOTA"
```

---

## 5. CFW Version Strings

The FUOTA plan uses CFW target strings, not plain versions.

| Build | App ID | Version | Track | Target String |
|-------|--------|---------|-------|---------------|
| MFG_BASE | 108 | 0.5.0 | BM | `108.0.5.0-BM` |
| MFG_BASE | 109 | 0.5.0 | BM | `109.0.5.0-BM` |
| MFG_BUMP | 108 | 0.5.1 | BM | `108.0.5.1-BM` |
| MFG_BUMP | 109 | 0.5.1 | BM | `109.0.5.1-BM` |

**Track codes**: B=Bench, E=Engineering, P=Production, M=Mfg, D=Debug

Parse from CFW header (23 bytes):
```python
file_ver, _, app_id, flags, major, minor, build, image_len = struct.unpack(">HQHBHHHi", header)
track = {0: "B", 1: "E", 2: "P"}[(flags >> 1) & 0x03]
suffix = track + ("M" if flags & 0x01 else "") + ("D" if flags & 0x08 else "")
target = f"{app_id}.{major}.{minor}.{build}-{suffix}"
```

---

## 6. Environment Variables

```bash
# MTIB
MTIB_ADDRESS=10.4.45.33:50053
FIXTURE_PROFILE_PATH=/app/validation/alpha/fixtures/alpha_b0.json

# Pipeline
PIPELINE_ID=cmmk9o8zh00008785xh9ltn0d
CONCORD_API_URL=http://concord-api:9001
CONCORD_API_KEY=ck_run_xxx

# MinIO
STORAGE_URL=http://minio:9000
STORAGE_ACCESS_KEY=xxx
STORAGE_SECRET_ACCESS_KEY=xxx

# CoreCloud
VAL_1_0_API_KEY=xxx
VAL_1_0_REST_SERVER_HOST_NAME=https://val.office.corekinect.cloud:2018/api

# Timeouts
FUOTA_TIMEOUT_S=480
CLOUD_CHECKIN_TIMEOUT_S=120
```

---

## 7. Failure Handling

| Test | Common Failure | Fix |
|------|----------------|-----|
| GATE-01 | "Debug port unavailable" | Add `recover=True` |
| GATE-02 | "No current" | Check power rails, GPIO 0+1 LOW |
| GATE-03 | "Shell not responding" | Retry faster, check UART timing |
| GATE-04 | "No check-in" | Check SIM, LTE coverage |
| GATE-05 | "FUOTA stuck" | Check target strings, device registration |
| GATE-06 | "No boot" | FUOTA failed, check bootloader |

**Cleanup on failure**: Always disable FUOTA assignment even if test fails:
```python
import atexit
atexit.register(lambda: fuota_client.disable_device(device_id, plan_id))
```

---

## 8. Running

### CI (automatic on every PR)

```yaml
# K8s Job (created by validation pipeline)
spec:
  activeDeadlineSeconds: 900  # 15 min hard limit
  template:
    spec:
      containers:
        - name: gate
          command: ["pytest", "/app/validation/alpha/tests/stage5/", "-v", "--timeout=900"]
```

### Local

```bash
cd apps/validation/alpha
PIPELINE_ID=xxx pytest tests/stage5/ -v --timeout=900
```

---

## 9. Key Files

| File | Purpose |
|------|---------|
| `apps/validation/alpha/tests/stage5/test_gate.py` | Test implementation |
| `libs/python/corekinect/test/fuota_client.py` | FUOTA API |
| `libs/python/corekinect/test/artifact_resolver.py` | Firmware artifact resolution |
| `libs/python/corekinect/test/device_personalizer.py` | Key provisioning |

---

## 10. Related Documents

- [Stages Overview](../../architecture/validation/stages-overview.md) — All 5 stages
- [Stage 5 Implementation](../../architecture/validation/stage5-fuota-tests.md) — Full spec
- [Stage 4 Regression](../../architecture/validation/stage4-product-tests.md) — Comprehensive tests
- [FUOTA API Workflow](../../reference/fuota-api.md) — API details
- [MTIB Hardware Rules](../../../.claude/rules/mtib-hardware.md) — Power/GPIO
