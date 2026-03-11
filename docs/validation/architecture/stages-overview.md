# Validation Stages Overview

Quick reference for all 5 validation stages. Each stage has a dedicated implementation doc (linked below) with full details.

---

## Stage Summary

| Stage | Name | Hardware | Where It Runs | Trigger | Duration |
|-------|------|----------|---------------|---------|----------|
| 1 | **Smoke** | None | CI container (amd64) | Every commit | 1-2 min |
| 2 | **Silicon** | Dev kit + MTIB | K8s pod → MTIB | PR/nightly | 5-15 min |
| 3 | **Integration** | Product board + MTIB | K8s pod → MTIB | PR/weekly | 15-30 min |
| 4 | **Nightly** | Product board + MTIB + CoreCloud | K8s pod → MTIB → Cloud | Nightly/release | 30-60 min |
| 5 | **Gate** | Product board + MTIB + CoreCloud + FUOTA | K8s pod → MTIB → Cloud | Every PR | < 15 min |

---

## Stage 1 — Smoke (Software Tests)

**Purpose**: Verify application logic works given known inputs. Fast feedback on every commit.

| Property | Value |
|----------|-------|
| Hardware Required | None |
| Execution Environment | `native_sim` (Zephyr POSIX simulator) in CI container |
| Runner | GitHub Actions / GitLab CI |
| Firmware Build | `native_sim` with stub drivers |
| Trigger | Every commit, every PR |
| Duration | 1-2 minutes |
| Pass/Fail Source | Zephyr ztest assertions |

**What It Tests**:
- State machine transitions (heat stress, motion, on-body)
- Threshold logic (alert conditions, mode switches)
- Sensor data processing (filtering, fusion, calibration math)
- IPC message generation (given known sensor values)
- Power state decisions (sleep/wake based on activity)

**What It Cannot Test**:
- Real hardware interaction (buses, interrupts, timing)
- Actual sensor behavior
- Radio communication
- Real power consumption

**Key Files**:
- Stub drivers: `accel_drv/stubs/`, `vsm_drv/stubs/`
- Test overlays: `alpha_fw/tests/app/boards/native_sim.overlay`
- Implementation doc: [stage1-software-tests.md](./stage1-software-tests.md)

---

## Stage 2 — Silicon (Driver Hardware Tests)

**Purpose**: Verify individual drivers work correctly on real silicon.

| Property | Value |
|----------|-------|
| Hardware Required | Dev kit (nRF52840-DK, nRF9160-DK) + MTIB |
| Execution Environment | K8s pod → gRPC → MTIB → J-Link → Dev kit |
| Runner | Concord validation pipeline |
| Firmware Build | Single-driver test firmware |
| Trigger | PR affecting driver, nightly |
| Duration | 5-15 minutes per driver |
| Pass/Fail Source | MTIB power measurements, UART assertions, test pass/fail |

**What It Tests**:
- Bus communication (SPI/I2C transactions succeed)
- Driver initialization (reset, WHO_AM_I, register config)
- Interrupt behavior (GPIO wiring, polarity, edge detection)
- FIFO hardware (batching, watermark, data ordering)
- Power consumption (sleep current, active current vs datasheet)

**What It Cannot Test**:
- Multi-component integration
- Application-level behavior
- Device-cloud communication
- Product-level specifications

**Key Files**:
- Test firmware: `accel_drv/tests/hw/`
- Fixture profiles: Dev kit fixtures (isolated driver access)
- Implementation doc: [stage2-driver-hw-tests.md](./stage2-driver-hw-tests.md)

---

## Stage 3 — Integration (Subsystem Tests)

**Purpose**: Verify firmware subsystems integrate correctly on real hardware.

| Property | Value |
|----------|-------|
| Hardware Required | Product board (Alpha B0) + MTIB |
| Execution Environment | K8s pod → gRPC → MTIB → Product board |
| Runner | Concord validation pipeline |
| Firmware Build | Instrumented firmware (`CONFIG_CONCORD_HARNESS=y`) |
| Trigger | PR affecting firmware, weekly |
| Duration | 15-30 minutes |
| Pass/Fail Source | Harness state queries + MTIB measurements |

**What It Tests**:
- State machine transitions driven by real sensor events
- IPC between MCUs (serialize, transmit, deserialize, dispatch)
- Sensor orchestration timing (warm-up, sampling cadence, coordination)
- Configuration propagation (runtime config → subsystems)
- Power-state transitions (system-level current draw changes)

**What It Cannot Test**:
- Shipping binary behavior (harness adds overhead)
- Device-cloud communication (instrumented firmware, not production)
- Real-world timing without instrumentation bias

**Key Files**:
- Harness module: `concord_harness/` (Zephyr module)
- Product declarations: `alpha_fw/src/concord_harness.c`
- Test runner: `apps/validation/alpha/tests/stage3/`
- Implementation doc: [stage3-integration-tests.md](./stage3-integration-tests.md)

---

## Stage 4 — Nightly (Long-Running Product Validation)

**Purpose**: Comprehensive product validation — runs all tests including slow ones.

| Property | Value |
|----------|-------|
| Hardware Required | Product board (Alpha B0) + MTIB + Fixture |
| Execution Environment | K8s pod → gRPC → MTIB → Product board; Cloud backend in loop |
| Runner | Concord validation pipeline |
| Firmware Build | Production firmware (Debug + Release variants) |
| Trigger | Nightly, release candidate |
| Duration | **30-60 minutes** |
| Pass/Fail Source | CoreCloud messages + MTIB power + Fixture sensors |

**What It Tests** (includes everything from Stage 5 plus):
- Full sensor characterization (all channels, all modes)
- Extended power profiling (multiple sleep/wake cycles)
- GPS acquisition under various conditions
- Full heartbeat cycle verification (wait for actual 4-hour heartbeat)
- Multi-mode state machine transitions
- Charger behavior (full charge cycle monitoring)
- Temperature response curves (peltier heating/cooling)
- Motion detection accuracy (linear rail stimulus)
- LED color verification (photodiode array)
- NFC tag read/write cycles

**Test Timing Budget**:
| Test Category | Max Duration | Notes |
|---------------|--------------|-------|
| Boot verification | 30s | Power cycle + current check |
| Power profiling | 5 min | Multiple sleep/wake cycles |
| Sensor sweep | 10 min | All sensors, all modes |
| Cloud connectivity | 5 min | Heartbeat + position messages |
| GPS acquisition | 15 min | Cold start + warm start |
| Charger cycle | 10 min | Plug/unplug transitions |
| State machine | 5 min | All stimulus combinations |

**Fixture Capabilities**:
- Button actuator (GPIO drives membrane)
- Charger relay (simulate plug/unplug)
- Peltier heater (skin temperature simulation)
- PPG servo (on-skin detection simulation)
- Motion stage (accelerometer stimulus)
- LED sensors (photodiodes over status LEDs)
- NFC reader (device ID verification)

**Key Files**:
- Test runner: `apps/validation/alpha/tests/stage4/`
- Fixture profiles: `apps/validation/alpha/fixtures/alpha_b0.json`
- Implementation doc: [stage4-product-tests.md](./stage4-product-tests.md)

---

## Stage 5 — Gate (PR Validation + FUOTA)

**Purpose**: Fast validation gate for every PR — must pass before merge. Includes FUOTA verification.

| Property | Value |
|----------|-------|
| Hardware Required | Product board (Alpha B0) + MTIB + Fixture + CoreCloud |
| Execution Environment | K8s pod → gRPC → MTIB → Product board → CoreCloud FUOTA |
| Runner | Concord validation pipeline |
| Firmware Build | Production firmware from PR pipeline |
| Trigger | **Every PR** (blocking) |
| Duration | **< 15 minutes** (hard limit) |
| Pass/Fail Source | Boot + Power + Cloud check-in + FUOTA completion |

**What It Tests**:
- Device boots after flash (< 30s)
- Power consumption in normal range (< 30s)
- Device checks into CoreCloud (< 2 min)
- **FUOTA delivery completes** (< 10 min)
- Device boots after FUOTA (< 30s)

**FUOTA Flow** (the core of Stage 5):
1. Flash MFG firmware via J-Link
2. Personalize device (EC keypair + CoreCloud registration)
3. Upload CFW files to CoreCloud
4. Create FUOTA plan (source → target)
5. Assign device to plan
6. Monitor until `isComplete: true`
7. Verify post-FUOTA boot

**Test Timing Budget**:
| Step | Max Duration | Timeout Action |
|------|--------------|----------------|
| J-Link flash (3 targets) | 2 min | Fail |
| Boot verification | 30s | Fail |
| Personalization | 1 min | Fail |
| Cloud check-in | 2 min | Fail |
| FUOTA delivery | 8 min | Fail |
| Post-FUOTA boot | 30s | Fail |
| **Total** | **< 15 min** | — |

**Why FUOTA is in Stage 5**:
- FUOTA is the highest-risk operation (can brick devices)
- Every PR that changes firmware MUST prove FUOTA works
- Catches CFW packaging issues, version string mismatches, bootloader problems
- Fast feedback — developers know within 15 min if their change breaks OTA

**Key Files**:
- Test runner: `apps/validation/alpha/tests/stage5/`
- FUOTA client: `libs/python/corekinect/test/validation/fuota_client.py`
- Pipeline assets: `libs/python/corekinect/test/validation/pipeline_assets.py`
- Implementation doc: [stage5-gate-tests.md](./stage5-gate-tests.md)

---

## Stage Comparison Matrix

| Capability | Stage 1 (Smoke) | Stage 2 (Silicon) | Stage 3 (Integration) | Stage 4 (Nightly) | Stage 5 (Gate) |
|------------|-----------------|-------------------|----------------------|-------------------|----------------|
| Real hardware | No | Yes | Yes | Yes | Yes |
| Production firmware | No | No | No | Yes | Yes |
| Internal visibility | Stub values | Driver state | Harness queries | None | None |
| Cloud backend | No | No | No | Yes | Yes |
| Physical stimulus | No | Limited | Yes | Full | Minimal |
| FUOTA verification | No | No | No | No | **Yes** |
| Max duration | 2 min | 15 min | 30 min | 60 min | **15 min** |
| Trigger | Every commit | PR/nightly | PR/weekly | Nightly | **Every PR** |
| Blocks merge | Yes | Yes | Yes | No | **Yes** |

---

## Tracking and Traceability

### Test Case IDs

Each test has a unique ID linking to requirements:

| Stage | Name | ID Format | Example | Links To |
|-------|------|-----------|---------|----------|
| 1 | Smoke | `SMOKE-{product}-{subsystem}-{seq}` | `SMOKE-ALPHA-VSM-001` | Code coverage |
| 2 | Silicon | `SILICON-{driver}-{test}` | `SILICON-LSM6DSO-FIFO` | Datasheet spec |
| 3 | Integration | `INTEG-{product}-{feature}` | `INTEG-ALPHA-IPC-MSG` | Integration spec |
| 4 | Nightly | `NIGHTLY-{product}-{seq}` | `NIGHTLY-ALPHA-001` | Product requirements |
| 5 | Gate | `GATE-{product}-{seq}` | `GATE-ALPHA-FUOTA-001` | OTA requirements |

### Pipeline Integration

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Commit    │────►│  Stage 1    │────►│    Pass?    │
│             │     │  (Smoke)    │     └──────┬──────┘
│             │     │   2 min     │            │
└─────────────┘     └─────────────┘            ▼ No → Block merge

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│     PR      │────►│  Stage 2+3  │────►│  Stage 5    │────►│    Pass?    │
│             │     │  (Silicon + │     │  (Gate)     │     └──────┬──────┘
│             │     │ Integration)│     │  + FUOTA    │            │
│             │     │   30 min    │     │   15 min    │            ▼ No → Block merge
└─────────────┘     └─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nightly   │────►│  Stage 4    │────►│    Pass?    │
│   (cron)    │     │  (Nightly)  │     └──────┬──────┘
│             │     │   60 min    │            │
└─────────────┘     └─────────────┘            ▼ No → Alert + investigate
```

**Key insight**: Stage 5 (Gate) runs on every PR and includes FUOTA. This ensures OTA updates work before code is merged. Stage 4 (Nightly) runs comprehensive tests overnight but doesn't block merges.

### CI/CD Configuration

```yaml
# .github/workflows/validation.yml (simplified)
stages:
  - name: stage1-smoke
    trigger: [push, pull_request]
    runner: ubuntu-latest
    timeout: 5m

  - name: stage2-silicon
    trigger: [pull_request]
    runner: self-hosted-mtib
    requires: [stage1-smoke]
    timeout: 20m

  - name: stage3-integration
    trigger: [pull_request]
    runner: self-hosted-mtib
    requires: [stage2-silicon]
    timeout: 30m

  - name: stage5-gate
    trigger: [pull_request]
    runner: self-hosted-mtib
    requires: [stage3-integration]
    timeout: 15m
    includes: [fuota]  # FUOTA is part of gate

  - name: stage4-nightly
    trigger: [schedule: "0 2 * * *"]  # 2 AM daily
    runner: self-hosted-mtib
    timeout: 90m
```

---

## Related Documents

- [Validation Philosophy](./00-validation-philosophy.md) — Why we validate this way
- [Final Architecture](./09-final-architecture.md) — System-level architecture
- [Stage 1 Smoke](./stage1-software-tests.md) — Stub drivers, native_sim, CI
- [Stage 2 Silicon](./stage2-driver-hw-tests.md) — Driver HW tests, dev kits
- [Stage 3 Integration](./stage3-integration-tests.md) — concord_harness, integration
- [Stage 4 Nightly](./stage4-product-tests.md) — Comprehensive black-box validation
- [Stage 5 Gate](./stage5-gate-tests.md) — PR validation + FUOTA
- [PRDTST Reference](../reference/alpha-prdtst-reference.md) — Product test case catalog
