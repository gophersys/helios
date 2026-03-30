# Stage 5 Gate Tests — PR Validation + FUOTA

> Implementation blueprint for Stage 5 (Gate) — the fast validation gate that runs on every PR.
> Includes FUOTA verification to ensure OTA updates work before code is merged.
> **Hard limit: < 15 minutes total.**

---

## 1. Purpose

Stage 5 Gate is the **merge blocker**. Every PR that touches firmware must pass Gate before merging.

**Why FUOTA is here**: FUOTA is the highest-risk operation — a broken OTA can brick devices in the field. By running FUOTA on every PR, we catch packaging issues, version mismatches, and bootloader problems before they ship.

---

## 2. Timing Budget

**Total: < 15 minutes** (hard limit — pipeline will timeout and fail)

| Step | Max Duration | Typical | Notes |
|------|--------------|---------|-------|
| Setup (connect MTIB) | 10s | 5s | gRPC connection |
| **Flash nRF52840** | 35s | 30s | J-Link via MTIB |
| **Flash modem** | 50s | 45s | nRF9151 baseband |
| **Flash nRF9151** | 35s | 30s | Comms firmware |
| Boot verification | 15s | 10s | Power check |
| **Personalization** | 90s | 60s | Shell lock + EC keygen + upload |
| CoreCloud check-in | 120s | 90s | Wait for uplink |
| **CFW upload** | 30s | 15s | 2 files to server |
| **FUOTA plan create** | 10s | 5s | API call |
| **FUOTA assign** | 10s | 5s | API call |
| **FUOTA delivery** | 480s | 300s | Device download + apply |
| Post-FUOTA boot | 15s | 10s | Power check |
| Cleanup | 10s | 5s | Disable FUOTA |
| **TOTAL** | **900s (15 min)** | ~600s (10 min) | — |

---

## 3. Test Sequence

### 3.1 Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 5 GATE                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. FLASH (< 2 min)                                         │
│     └── nRF52840 → modem → nRF9151                          │
│                                                             │
│  2. BOOT CHECK (< 30s)                                      │
│     └── Power cycle, verify >5mA current                    │
│                                                             │
│  3. PERSONALIZE (< 2 min)                                   │
│     └── Lock shell → generate keys → upload to CoreCloud    │
│                                                             │
│  4. CLOUD CHECK-IN (< 2 min)                                │
│     └── Wait for device to report to CoreCloud              │
│                                                             │
│  5. FUOTA (< 8 min)                                         │
│     ├── Upload CFW files                                    │
│     ├── Create plan (source → target)                       │
│     ├── Assign device                                       │
│     ├── Monitor progress until complete                     │
│     └── Cleanup (disable FUOTA)                             │
│                                                             │
│  6. POST-FUOTA BOOT (< 30s)                                 │
│     └── Power cycle, verify device boots                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Test Implementation

```python
# apps/validation/alpha/tests/stage5/test_gate.py

import pytest
import time

class TestGate:
    """Stage 5 Gate — PR validation + FUOTA.

    TIMING: Each test has a timeout annotation. Total must be < 15 min.
    """

    # ─────────────────────────────────────────────────────────
    # FLASH (< 2 min)
    # ─────────────────────────────────────────────────────────

    @pytest.mark.timeout(120)
    def test_01_flash_firmware(self, ctx, pipeline_assets):
        """GATE-01: Flash all 3 targets via J-Link."""
        # Flash order: nRF52840 → modem → nRF9151
        # See stage4-alpha-example.md for detailed flash code
        pass

    # ─────────────────────────────────────────────────────────
    # BOOT CHECK (< 30s)
    # ─────────────────────────────────────────────────────────

    @pytest.mark.timeout(30)
    def test_02_verify_boot(self, ctx):
        """GATE-02: Verify device boots after flash."""
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.fixture.power_on()
        time.sleep(10)
        assert ctx.fixture.verify_dut_powered(min_current_ma=5.0)

    # ─────────────────────────────────────────────────────────
    # PERSONALIZE (< 2 min)
    # ─────────────────────────────────────────────────────────

    @pytest.mark.timeout(120)
    def test_03_personalize(self, ctx, stage5_config):
        """GATE-03: Personalize device (shell lock + EC keygen + upload)."""
        from corekinect.test.device_personalizer import DevicePersonalizer

        personalizer = DevicePersonalizer(
            mtib=ctx.mtib,
            snr=stage5_config.device_snr,
            known_device_id=stage5_config.device_id,
        )
        result = personalizer.personalize()
        assert result.success, f"Personalization failed: {result.error}"

    # ─────────────────────────────────────────────────────────
    # CLOUD CHECK-IN (< 2 min)
    # ─────────────────────────────────────────────────────────

    @pytest.mark.timeout(120)
    def test_04_cloud_checkin(self, ctx, fuota_client, stage5_config):
        """GATE-04: Verify device checks into CoreCloud."""
        # Power cycle to trigger fresh check-in
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.fixture.power_on()
        time.sleep(15)

        # Poll for new recordId
        device_id = stage5_config.device_id
        initial = fuota_client.get_record_id(device_id)

        deadline = time.time() + 90
        while time.time() < deadline:
            current = fuota_client.get_record_id(device_id)
            if current > initial:
                return  # Success!
            time.sleep(10)

        pytest.fail("Device did not check into CoreCloud")

    # ─────────────────────────────────────────────────────────
    # FUOTA (< 8 min)
    # ─────────────────────────────────────────────────────────

    @pytest.mark.timeout(480)
    def test_05_fuota_delivery(self, ctx, fuota_client, pipeline_assets, stage5_config):
        """GATE-05: Execute FUOTA transition and verify completion."""
        device_id = stage5_config.device_id

        # Upload CFW files
        for cfw_path in pipeline_assets.get_cfw_files("MFG_BASE"):
            fuota_client.upload_cfw(cfw_path)
        for cfw_path in pipeline_assets.get_cfw_files("MFG_BUMP"):
            fuota_client.upload_cfw(cfw_path)

        # Create plan
        plan_id = fuota_client.create_plan(
            stages=[
                {"targets": stage5_config.source_targets},
                {"targets": stage5_config.target_targets},
            ],
            device_type_id=2,
            device_variant_id=3,
        )

        # Assign device
        fuota_client.assign_device(plan_id, [device_id], max_stage=1, enable=True)

        # Power cycle to trigger FUOTA
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.fixture.power_on()
        time.sleep(10)

        # Monitor progress (max 7 min)
        deadline = time.time() + 420
        while time.time() < deadline:
            progress = fuota_client.get_progress(device_id)
            if progress and progress.get("isComplete"):
                break
            time.sleep(10)
        else:
            pytest.fail("FUOTA did not complete within timeout")

        # Cleanup
        fuota_client.disable_device(device_id, plan_id)

    # ─────────────────────────────────────────────────────────
    # POST-FUOTA BOOT (< 30s)
    # ─────────────────────────────────────────────────────────

    @pytest.mark.timeout(30)
    def test_06_post_fuota_boot(self, ctx):
        """GATE-06: Verify device boots after FUOTA."""
        ctx.fixture.power_off()
        time.sleep(2)
        ctx.fixture.power_on()
        time.sleep(10)
        assert ctx.fixture.verify_dut_powered(min_current_ma=5.0)
```

---

## 4. FUOTA Details

### 4.1 CFW Files

The pipeline produces CFW files for both source and target:

| Build | CFW Files | Version String |
|-------|-----------|----------------|
| MFG_BASE | 108.0.5.0-BM.cfw, 109.0.5.0-BM.cfw | v0.5.0 |
| MFG_BUMP | 108.0.5.1-BM.cfw, 109.0.5.1-BM.cfw | v0.5.1 |

**CFW naming**: `{appId}.{major}.{minor}.{build}-{track}.cfw`
- AppId 108 = nRF9151 comms
- AppId 109 = nRF52840 app
- Track: B=Bench, M=Mfg, D=Debug

### 4.2 FUOTA Plan Structure

```json
{
  "stages": [
    {
      "targets": ["108.0.5.0-BM", "109.0.5.0-BM"],
      "description": "Stage 0: MFG_BASE",
      "isSkippable": false
    },
    {
      "targets": ["108.0.5.1-BM", "109.0.5.1-BM"],
      "description": "Stage 1: MFG_BUMP",
      "isSkippable": false
    }
  ],
  "deviceTypeId": 2,
  "deviceVariantId": 3
}
```

### 4.3 FUOTA Flow Timeline

```
t=0      Device boots with MFG_BASE (v0.5.0)
t=15s    Device connects to LTE
t=30s    Device sends heartbeat to CoreCloud
t=35s    CoreCloud responds with FUOTA download command
t=40s    Device starts downloading CFW fragments
t=3-5min Device finishes download, verifies checksum
t=5-6min Device writes to flash, reboots
t=6-7min Device boots with MFG_BUMP (v0.5.1)
t=7min   Device sends heartbeat confirming new version
```

---

## 5. Failure Modes

### 5.1 Flash Failures

| Error | Cause | Fix |
|-------|-------|-----|
| "Debug port unavailable" | APPROTECT enabled | Add `recover=True` to FlashFwFile |
| "Target not connected" | Power not on | Call `power_on()` before flash |
| "File not found" | Upload failed | Retry UploadFwFile |

### 5.2 Personalization Failures

| Error | Cause | Fix |
|-------|-------|-----|
| "Shell not responding" | Missed 2s window | Retry with faster UART open |
| "CoreOps unavailable" | Network issue | Use `known_device_id` fallback |
| "Key upload failed" | Wrong format | Use raw EC point, not DER |

### 5.3 FUOTA Failures

| Error | Cause | Fix |
|-------|-------|-----|
| "Device not found" | Not registered | Call `ensure_device_registered()` |
| "Invalid target" | Wrong version string | Check CFW header parsing |
| "Download stuck" | LTE connectivity | Check SIM data plan |
| "Apply failed" | Bootloader issue | Flash recovery firmware |

---

## 6. Environment Variables

```bash
# Required
MTIB_ADDRESS=10.4.45.33:50053
DEVICE_SNR=09J5
FIXTURE_PROFILE_PATH=/app/validation/alpha/fixtures/alpha_b0.json
PIPELINE_ID=cmmk9o8zh00008785xh9ltn0d

# Concord API
CONCORD_API_URL=http://concord-api:9001
CONCORD_API_KEY=ck_run_xxx

# MinIO
STORAGE_URL=http://minio:9000
STORAGE_ACCESS_KEY=xxx
STORAGE_SECRET_ACCESS_KEY=xxx

# CoreCloud
VAL_1_0_API_KEY=xxx
VAL_1_0_REST_SERVER_HOST_NAME=https://val.office.corekinect.cloud:2018/api

# Timeouts (defaults shown)
FUOTA_TIMEOUT_S=480
CLOUD_CHECKIN_TIMEOUT_S=120
```

---

## 7. Key Files

| File | Purpose |
|------|---------|
| `apps/validation/alpha/tests/stage5/test_gate.py` | Test implementation |
| `apps/validation/alpha/conftest.py` | pytest fixtures |
| `libs/python/corekinect/test/fuota_client.py` | FUOTA API wrapper |
| `libs/python/corekinect/test/artifact_resolver.py` | Firmware artifact resolution |
| `libs/python/corekinect/test/device_personalizer.py` | Key provisioning |

---

## 8. Running

### Local

```bash
cd apps/validation/alpha
PIPELINE_ID=xxx pytest tests/stage5/ -v --timeout=900
```

### CI (K8s Job)

The validation pipeline creates a K8s Job with 15-minute timeout:

```yaml
spec:
  activeDeadlineSeconds: 900  # 15 min hard limit
  template:
    spec:
      containers:
        - name: gate
          command: ["pytest", "/app/validation/alpha/tests/stage5/", "-v"]
```

---

## 9. Metrics

Track these to monitor Gate health:

| Metric | Target | Alert |
|--------|--------|-------|
| Gate pass rate | > 95% | < 90% |
| Gate duration p50 | < 10 min | > 12 min |
| Gate duration p95 | < 14 min | > 14 min |
| FUOTA success rate | > 99% | < 95% |
| Flash success rate | > 99% | < 95% |
