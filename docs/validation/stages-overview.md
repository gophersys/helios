---
min_role: DEVELOPER
---
# Stages Overview

Five stages, ordered by cost and scope. Early stages catch bugs cheaply in software. Later stages exercise real hardware, cloud connectivity, and over-the-air updates.

| Stage | Name | Hardware | Runner | Trigger | Time |
|-------|------|----------|--------|---------|------|
| 1 | Smoke | None | CI container (amd64) | Every commit | 1-2 min |
| 2 | Driver | Dev kit + MTIB | K8s pod | PR / regression | 5-15 min |
| 3 | Integration | Product board + MTIB | K8s pod | PR / weekly | 15-30 min |
| 4 | Regression | Product board + MTIB + CoreCloud | K8s pod | Nightly cron | 30-60 min |
| 5 | FUOTA | Product board + MTIB + CoreCloud | K8s pod | Every PR | < 15 min |

---

## Stage 1 -- Smoke

Fast feedback on every commit. Runs application logic on `native_sim` (Zephyr POSIX simulator) with stub drivers -- no hardware needed.

| Property | Value |
|----------|-------|
| Hardware | None |
| Firmware build | `native_sim` with stub drivers |
| Pass/fail source | Zephyr ztest assertions |

**Tests:** State machine transitions (heat stress, motion, on-body). Threshold logic for alerts and mode switches. Sensor data processing -- filtering, fusion, calibration math. IPC message generation from known sensor values. Sleep/wake decisions based on activity state.

**Out of scope:** Real bus transactions, interrupt timing, radio, actual power consumption.

**Key files:** Stub drivers in `accel_drv/stubs/`, `vsm_drv/stubs/`. Test overlays at `alpha_fw/tests/app/boards/native_sim.overlay`. Full details in stage1-software-tests.md (internal).

---

## Stage 2 -- Driver

Verifies individual drivers on real silicon using dev kits (nRF52840-DK, nRF9160-DK) wired to an MTIB.

| Property | Value |
|----------|-------|
| Hardware | Dev kit + MTIB |
| Execution path | K8s pod -> gRPC -> MTIB -> J-Link -> dev kit |
| Firmware build | Single-driver test firmware |
| Pass/fail source | MTIB power measurements, UART assertions |

**Tests:** Bus communication (SPI/I2C transactions succeed). Driver init (reset, WHO_AM_I, register config). Interrupt wiring (polarity, edge detection). FIFO hardware (batching, watermark, data ordering). Power draw vs. datasheet (sleep current, active current).

**Out of scope:** Multi-component integration, application behavior, cloud communication.

**Key files:** Test firmware in `accel_drv/tests/hw/`. Full details in stage2-driver-hw-tests.md (internal).

---

## Stage 3 -- Integration

Exercises firmware subsystems working together on a real product board (Alpha B0). Uses instrumented firmware (`CONFIG_CONCORD_HARNESS=y`) to query internal state.

| Property | Value |
|----------|-------|
| Hardware | Product board (Alpha B0) + MTIB |
| Firmware build | Instrumented (`CONFIG_CONCORD_HARNESS=y`) |
| Pass/fail source | Harness state queries + MTIB measurements |

**Tests:** State machine transitions driven by real sensor events. IPC between nRF52840 and nRF9151 (serialize, transmit, deserialize, dispatch). Sensor orchestration timing -- warm-up sequences, sampling cadence. Configuration propagation from runtime config into subsystems. System-level power-state transitions.

**Out of scope:** Shipping binary behavior (harness adds overhead), cloud communication, uninstrumented timing.

**Key files:** Harness module in `concord_harness/`. Product declarations in `alpha_fw/src/concord_harness.c`. Tests in `apps/validation/alpha/tests/stage3/`. Full details in stage3-integration-tests.md (internal).

---

## Stage 4 -- Regression

Comprehensive product validation. Runs everything including slow tests -- GPS cold start, full charge cycles, 4-hour heartbeat waits. Triggered nightly, does not block merges.

| Property | Value |
|----------|-------|
| Hardware | Product board + MTIB + full fixture (Peltier, linear rail, photodiodes) |
| Firmware build | Production firmware (debug + release variants) |
| Pass/fail source | CoreCloud messages + MTIB power + fixture sensors |

**Tests and timing budget:**

| Category | Budget | What |
|----------|--------|------|
| Boot verification | 30s | Power cycle + current check |
| Power profiling | 5 min | Multiple sleep/wake cycles |
| Sensor sweep | 10 min | All sensors, all modes |
| Cloud connectivity | 5 min | Heartbeat + position messages |
| GPS acquisition | 15 min | Cold start + warm start |
| Charger cycle | 10 min | Plug/unplug transitions |
| State machine | 5 min | All stimulus combinations |

The regression fixture has a button actuator, charger relay, Peltier heater (skin temp sim), PPG servo (on-skin detection), linear motion stage (accelerometer stimulus), LED photodiodes, and an NFC reader.

**Key files:** Tests in `apps/validation/alpha/tests/stage4/`. Fixture profile at `apps/validation/alpha/fixtures/alpha_b0.json`. Full details in stage4-product-tests.md (internal).

---

## Stage 5 -- FUOTA

The PR gate. Every pull request that touches firmware must pass Stage 5 within 15 minutes or the merge is blocked. The core test: flash MFG firmware, personalize, push a CFW over the air, and confirm the device boots on the new image.

| Property | Value |
|----------|-------|
| Hardware | Product board + MTIB + CoreCloud |
| Firmware build | Production firmware from PR pipeline |
| Pass/fail source | Boot + power + cloud check-in + FUOTA completion |

**FUOTA flow:**

1. Flash MFG firmware via J-Link (3 targets, 2 min max)
2. Personalize -- EC keypair + CoreCloud registration (1 min)
3. Upload CFW to CoreCloud
4. Create FUOTA plan (source -> target), assign device
5. Poll until `isComplete: true` (8 min max)
6. Power cycle + verify post-FUOTA boot (30s)

Total budget: under 15 minutes.

FUOTA is the highest-risk firmware operation -- a bad OTA can brick devices in the field. Running it on every PR catches CFW packaging errors, version string mismatches, and bootloader regressions before they merge.

**Key files:** Tests in `apps/validation/alpha/tests/stage5/`. FUOTA client at `libs/python/corekinect/test/fuota_client.py`. Artifact resolver at `libs/python/corekinect/test/artifact_resolver.py`. Full details in the FUOTA tests source under `apps/validation/alpha/tests/stage5/`.

---

## Comparison Matrix

| Capability | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 |
|------------|---------|---------|---------|---------|---------|
| Real hardware | No | Yes | Yes | Yes | Yes |
| Production firmware | No | No | No | Yes | Yes |
| Internal visibility | Stub values | Driver state | Harness queries | None | None |
| Cloud backend | No | No | No | Yes | Yes |
| Physical stimulus | No | Limited | Yes | Full | Minimal |
| FUOTA verification | No | No | No | No | Yes |
| Max duration | 2 min | 15 min | 30 min | 60 min | 15 min |
| Blocks merge | Yes | Yes | Yes | No | Yes |

---

## Pipeline Flow

```
Commit ──► Stage 1 (Smoke, 2 min) ──► Pass? ──► No: block merge

PR ──► Stage 2+3 (Driver + Integration, 30 min) ──► Stage 5 (FUOTA, 15 min) ──► Pass? ──► No: block merge

Nightly cron ──► Stage 4 (Regression, 60 min) ──► Pass? ──► No: alert + investigate
```

## Test Case IDs

Each test has a unique ID linking back to requirements:

| Stage | Format | Example | Traces to |
|-------|--------|---------|-----------|
| 1 | `SMOKE-{product}-{subsystem}-{seq}` | `SMOKE-ALPHA-VSM-001` | Code coverage |
| 2 | `DRIVER-{driver}-{test}` | `DRIVER-LSM6DSO-FIFO` | Datasheet spec |
| 3 | `INTEG-{product}-{feature}` | `INTEG-ALPHA-IPC-MSG` | Integration spec |
| 4 | `REGRESSION-{product}-{seq}` | `REGRESSION-ALPHA-001` | Product requirements |
| 5 | `FUOTA-{product}-{seq}` | `FUOTA-ALPHA-001` | OTA requirements |

## CI Configuration

```yaml
# .github/workflows/validation.yml (simplified)
stages:
  - name: stage1-smoke
    trigger: [push, pull_request]
    runner: ubuntu-latest
    timeout: 5m

  - name: stage2-driver
    trigger: [pull_request]
    runner: self-hosted-mtib
    requires: [stage1-smoke]
    timeout: 20m

  - name: stage3-integration
    trigger: [pull_request]
    runner: self-hosted-mtib
    requires: [stage2-driver]
    timeout: 30m

  - name: stage5-fuota
    trigger: [pull_request]
    runner: self-hosted-mtib
    requires: [stage3-integration]
    timeout: 15m

  - name: stage4-regression
    trigger: [schedule: "0 2 * * *"]  # 2 AM daily
    runner: self-hosted-mtib
    timeout: 90m
```

---

## Related

- [Validation System Design](../platform/validation-system/system-design.md)
- [Test Runner](../platform/validation-system/test-runner.md)
- [Stages & Errors Reference](../reference/stages-and-errors.md)
