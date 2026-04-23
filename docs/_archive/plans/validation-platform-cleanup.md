# Validation Platform Cleanup & Runtime Plan

**Date:** 2026-03-07
**Status:** In Progress

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  JARED'S TESTS (per-product, untouched)             │
│  test_boot.py, test_button.py, test_power.py ...    │
│  Uses: ctx.fixture.*, ctx.cloud.*, ctx.power.*      │
└──────────────────────┬──────────────────────────────┘
                       │ calls
┌──────────────────────▼──────────────────────────────┐
│  HARNESS LAYER (product-agnostic)                   │
│  FixtureController ← FixtureProfile (JSON)          │
│  CloudClient, PowerProfiler, UartDemuxer            │
│  Abstracts: MTIB rev, board rev, GPIO mapping       │
└──────────────────────┬──────────────────────────────┘
                       │ orchestrated by
┌──────────────────────▼──────────────────────────────┐
│  SESSION RUNTIME                                    │
│  • Continuous UART capture (all ports, full session) │
│  • Continuous power capture (INA219 + Joulescope)   │
│  • All timestamped to common clock                  │
│  • Per-test event markers (test start/end)          │
│  • Artifact packaging (zip per run)                 │
└──────────────────────┬──────────────────────────────┘
                       │ runs inside
┌──────────────────────▼──────────────────────────────┐
│  K8S ORCHESTRATION                                  │
│  • Job per (product, device, firmware_variant)      │
│  • Node selector → MTIB host                        │
│  • Reporter → Concord API (real-time)               │
│  • Artifacts → MinIO                                │
│  • Logs → Loki                                      │
└─────────────────────────────────────────────────────┘
```

## Principles

1. **Jared's tests are sacred** — test logic is product-specific and untouched
2. **Harness abstracts hardware** — MTIB rev, board rev, GPIO mapping invisible to tests
3. **Fixture profile is the contract** — JSON defines physical ↔ software mapping
4. **Captures are continuous** — UART + power run for entire session, not per-test
5. **Everything is timestamped** — common wall clock across all data streams
6. **Product-agnostic runtime** — Alpha, Sigma, ICLE use same infrastructure

## Phase 1: Interface Blockers (IMMEDIATE)

### 1A. CloudClient.wait_for_biometric() — NotImplementedError
- **File:** `libs/python/corekinect/test/validation/cloud_client.py`
- **Problem:** 6 tests crash in hardware mode
- **Fix:** Implement via REST API `_poll_status_change("biometricInfo", ...)` or graceful skip

### 1B. MockCloudClient return type mismatch
- **File:** `libs/python/corekinect/test/validation/mock_cloud.py`
- **Problem:** `check_hw_failures()` returns `List` but tests call `.get("hasFailures")`
- **Fix:** Return `Dict[str, Any]` matching CloudClient interface

### 1C. Direct _mtib access in test_environmental.py
- **File:** `libs/python/corekinect/test/validation/fixture_controller.py`
- **Problem:** Tests bypass public API for peltier control
- **Fix:** Add `set_peltier(on: bool)` method to FixtureController + mock

## Phase 2: Security

### 2A. TLS verification disabled everywhere
- 10+ `verify=False` across device_personalizer, fuota_client, test_corecloud_integration
- **Fix:** Centralize into shared session helper with `CORECLOUD_VERIFY_TLS` env var

### 2B. .gitignore defense-in-depth
- Add explicit patterns for `.env`, `*.pem`, `*.key`

### 2C. Credential documentation
- Document rotation procedures for API keys, SSH keys, DB passwords

## Phase 3: Code Quality & Traceability

### 3A. PRDTST IDs in all test docstrings
- Government traceability: every test maps to PRD requirement
- Format: `"""PRDTST-XXX: Description."""`

### 3B. Fixture profile schema formalization
- JSON Schema or Pydantic model for fixture profiles
- Validate on load, document all fields

### 3C. MockFixtureProfile alignment
- Add all FixtureProfile fields to MockFixtureProfile
- Prevent AttributeError in mock mode

### 3D. Power channel abstraction
- Add `primary_power_channel` property to FixtureController
- Remove duplicated `ch = 1 if battery_installed else 0` from 7 test locations

### 3E. time.sleep mock improvement
- Replace global patch with `unittest.mock.patch` (reversible, standard)

## Phase 4: Session Runtime (NEW)

### 4A. SessionCapture class
- **File:** `libs/python/corekinect/test/validation/session_capture.py`
- Continuous UART + power recording with timestamped event markers
- Background threads started in TestContext.connect()
- Per-test markers inserted by setup_test() / teardown_test()

### 4B. Artifact packaging
- Session bundle: full UART log + power CSV + event timeline JSON
- Upload to MinIO as zip per run

### 4C. Reporter integration
- Fix `last_measurement` (PowerProfiler needs per-test snapshot)
- Include artifact URLs in test results

## Phase 5: Missing Test Coverage

### 5A. Software-implementable tests
- PRDTST-346: 7x press hard reset
- PRDTST-382: SOS entry (3-6s hold)
- PRDTST-376: FUOTA end-to-end (new test_fuota.py)
- PRDTST-410: VSM power cutoff

### 5B. Hardware-blocked (document only)
- Charging/BMS (29 tests) — battery fixture
- Config Values (18 tests) — IPC capability
- GNSS (7 tests) — GPS simulator
- Motion (5 tests) — FluidNC rail
- Haptic (4 tests) — vibration sensor
- NFC (2 tests) — I2C reader wiring

## Phase 6: Documentation

- Test execution runbook
- PRDTST traceability matrix (all 89 PRD tests → implementation status)
- Fixture profile schema documentation
- Credential rotation guide
- Architecture doc updates

## Alpha B0 Fixture Pinout

See `apps/validation/alpha/fixtures/PINOUT.md` for the complete
MTIB ↔ DUT signal mapping that must match the physical fixture wiring.
