# Stage 3 & 4 Proof — Status Tracker

> Last updated: 2026-03-02 (night, Run 5 in progress)

## Current Phase: **Phase 4 — Stage 4 Test Execution (hardware runs active)**

Phase 1-2 infrastructure is complete. Phase 4-5 test modules are written with
mock mode support. **Validation container deployed to K8s** — runs as a one-shot
Job on concordagent01. Run 5 is executing now with all framework fixes deployed.

**Latest hardware run (Run 5, REV 1.2 — 10.4.45.33):**
- **23 failed, 24 passed, 67 skipped in 869s (14:28)**
- Re-personalization succeeds on debug build; release build has no mfg shell (by design)
- Flash caching: 2 total flash cycles (down from ~70 in Run 3)
- GPIO permission errors: **0** (was ~8 in Run 4 — FIXED)
- Stimulus GPIOs auto-configured as OUTPUT successfully

**Run 5 vs Run 4 delta:** GPIO permission errors eliminated (+1 pass), but power
measurement on ch0 is now correctly ~0mA (charger takeover), exposing that
`verify_dut_powered()` and multiple power tests check ch0 alone.

**Root cause of most failures:** After BQ25180 charger takeover (~4s post-boot),
ch0 (battery sim) drops to ~0mA and ch1 (charger) rises to 17-33mA. Tests
checking ch0 alone see "no power" even though the DUT is running fine on ch1.
**Fix: `verify_dut_powered()` must use `read_total_current()` (ch0+ch1).
Power budget tests must also measure ch0+ch1 combined.**

**Two engineers are active:**
- **Engineer 1 (primary):** Infrastructure, firmware builds, MTIB deploy, build tooling
- **Engineer 2 (CoreCloud):** Test framework, CoreCloud integration, validation tests

---

## Stream Status

| Stream | Phase | Status | Owner | Notes |
|--------|-------|--------|-------|-------|
| **D** MTIB server | 1 | **Deployed + ALL RPCs verified** | Eng 1 | 3 image rebuilds. 24/27 RPCs PASS both boards. V2 RPCs (PowerStream, AdcStream, GpioWatch, GetSnapshot) all working. J-Link mux fixed. Firmware upload+flash pipeline verified. |
| **G** Stage 4 Python infra | 1 | **COMPLETE** | Eng 2 | CloudClient, TestContext, FixtureController, UartDemuxer, PowerProfiler |
| **F** Python test framework | 2 | **COMPLETE** | Eng 2 | conftest.py, session fixtures, firmware_build parametrization |
| **J** Stage 4 test modules | 4-5 | **WRITTEN (112 tests)** | Eng 2 | 9 modules: boot, motion, biometric, button, env, power, nfc, corecloud_integration, smoke_mtib |
| **A** concord_harness | 1 | Not started | — | Stage 3 scope — deferred |
| **B** alpha_fw changes | 1 | Not started | — | Stage 3 scope — deferred |
| **C** fixture wiring | 1 | Not started | — | Hardware work, not yet started |
| **E** FW harness integration | 2 | Not started | — | Stage 3 scope — blocked on A, B, D |
| **H** Stage 3 tests | 3 | Not started | — | Stage 3 scope — blocked on E, F |

### Infrastructure (not in original plan)

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Container registry HTTPS + CA certs | **COMPLETE** | Eng 1 | `.devcontainer/ctl.sh` auto-extracts from TLS handshake |
| BuildKit CA cert injection | **COMPLETE** | Eng 1 | Appends to buildkit's `/etc/ssl/certs/ca-certificates.crt` |
| Firmware build tooling (`ctl.sh`) | **COMPLETE** | Eng 1 | Docker path translation, NCS image resolution, build matrix |
| MTIB server ARM64 image | **3 rebuilds deployed** | Eng 1 | Fix 1: PYTHONPATH `/libs/protocols`. Fix 2: J-Link mux inversion. Fix 3: nrfjprog family flags + chiperase. |
| MTIB server K8s deployment | **COMPLETE** | Eng 1 | Both pods running on correct nodes (REV 1.2→15005665, REV 1.1→15702161) |
| V2 RPCs verified | **COMPLETE** | Eng 1 | PowerEnable/Read/Measure/Stream, AdcStream, GpioWatch, GetSnapshot — all PASS on both boards |
| Firmware upload via RPC | **COMPLETE** | Eng 1 | UploadFwFile streaming works. SHA256 verified. ListFwFiles returns uploaded files. |
| J-Link flash via RPC | **COMPLETE** | Eng 1 | nRF52840: ~11s (NRF52, --verify --chiperase --reset). nRF9151: ~8s (NRF91, --chiperase --reset, no verify due to APPROTECT). Both chips flash on both boards. |
| Full flash pipeline | **COMPLETE** | Eng 1 | Upload → Flash nRF52840 → Flash nRF9151 → Power cycle → Boot verify → UART capture. End-to-end working on both REVs. |
| All firmware variants built | **COMPLETE** | Eng 2 | 6 builds: mfg×alpha_b0, debug×alpha_b0, release×alpha_b0 — each with app+comms hex. Collected to validation assets. |
| DUT power-on verified | **COMPLETE** | Eng 1 | Both DUTs boot at 28-34mA. **Requires GPIO 0+1 LOW** — see hardware rules. |
| UART comms verified | **COMPLETE** | Eng 1 | All 4 UARTs work on both REVs. Full boot logs captured. Mfg shell lock+commands verified. REV 1.1 nRF9151 has garbled MCUboot bytes (DTS overlay not yet active), app output clean. |
| ADC verified | **COMPLETE** | Eng 1 | 8 channels read on both boards. Ch7=3.3V (reference). Ch0/2=~4.5V (power rails). Ch3-6=0V (unused). |
| LTE modem verified | **PARTIAL** | Eng 1 | Modem FW v2.0.2 running, IPC working, boot msgs generated. No confirmed LTE attach in 60s — needs re-personalization or longer capture. |
| Motion RPC | **NOT AVAILABLE** | Eng 1 | `MOTION_ENABLED=False` — FluidNC linear rail not connected. Server streaming bug fixed (yield vs return). |
| ListProgrammers bug | **FIXED + DEPLOYED** | Eng 1 | Was returning empty. Fixed + redeployed. Now detects 2 J-Link probes per board. |
| MotionStart streaming bug | **FIXED + DEPLOYED** | Eng 1 | Returned non-iterator when disabled. Fixed + redeployed. |
| J-Link mux inversion (REV 1.2) | **FIXED + DEPLOYED** | Eng 1 | P0=LOW→nRF9151, P0=HIGH→nRF52840 (opposite of original assumption). Firmware handler + TCA9534A driver corrected. |
| nrfjprog family flags | **FIXED + DEPLOYED** | Eng 1 | Added `-f NRF52`/`NRF91`/`NRF53` to flash, recover, and erase commands. Also added `--chiperase --reset`. |
| nRF91 verify skip | **FIXED + DEPLOYED** | Eng 1 | nRF91 secure firmware enables APPROTECT after programming → readback fails. Skip `--verify` for NRF91 targets. |
| NCS Docker images pulled | **COMPLETE** | Eng 1 | 2.7.0 (alpha) and 2.4.2 (sigma5) |
| Sigma5 app firmware build | **COMPLETE** | Eng 1 | nRF52840 + nRF9160 hex files generated |
| Alpha firmware builds (all 6) | **COMPLETE** | Eng 2 | mfg, debug, release × alpha_b0. All artifacts collected to validation assets dir. |
| Integrated real-world test | **COMPLETE** | Eng 1 | 10/10 tests pass on both REVs: power cycle, GPIO, boot current, ADC, UART, charge power, shutdown |
| Mfg shell interaction | **COMPLETE** | Eng 1 | lock_shell, debug_enable, kernel version, device eui all work on both boards via UART |
| Device personalization status | **IDENTIFIED** | Eng 1 | REV 1.1 (`097D`): STILL PERSONALIZED (EUI matches `70B3D584C01E20A2`). REV 1.2 (`0964`): WIPED (default EUI `70B3D584C02003B4`). |
| Firmware version confirmed | **COMPLETE** | Eng 1 | Both: NCS v2.7.0, Zephyr v3.6.99. REV 1.2: MCUboot v2.1.0. Both have mfg FW pre-loaded. |
| I2C sensor status | **IDENTIFIED** | Eng 1 | LSM6DSO accel: OK on both. BME280 env: FAIL on both (I2C -5). LP5814 LED: FAIL on REV 1.1. PPG: missing on REV 1.2. |

---

## Validation Device Registry

See [device-registry.md](device-registry.md) for full details.

| J-Link SNR | MTIB Rev | MTIB Node IP | Device ID | IMEI |
|------------|----------|-------------|-----------|------|
| **0964** | REV 1.2 | 10.4.45.33 | `70B3D584C01E1FCC` | 355025931735979 |
| **097D** | REV 1.1 | 10.4.45.32 | `70B3D584C01E20A2` | 355025937661526 |

Both devices: manufactured, personalized, SIMs activated (Verizon + Onomondo),
CoreCloud server: `dev.office.corekinect.cloud`, firmware v0.8.

**Rule:** Device ID and SNR are permanent. IMEI is permanent (SIM hardware).
Public key CHANGES on every re-flash + re-personalization (new EC keypair
generated on device). See [Re-personalization Workflow](#re-personalization-workflow).

---

## Phase Checklist

### Phase 0: Prerequisites

- [x] Alpha B0 boards sourced — **2 units** (SNR 0964 batch-7, SNR 097D batch-9)
- [ ] Motion scaffold status confirmed (existing or need to build)
- [x] K3s cluster nodes identified (10.4.45.33 REV 1.2, 10.4.45.32 REV 1.1)
- [x] Container registry accessible (HTTPS + auto CA cert extraction)
- [x] Repos cloned, branch `v2/init` checked out
- [x] CoreCloud server identified: `dev.office.corekinect.cloud`
- [x] Devices personalized from manufacturing (device IDs + keys recorded)
- [ ] LTE connectivity verified on validation setup (modem FW v2.0.2 running, IPC working, boot msgs generated — need re-personalization for LTE attach + CoreCloud checkin)
- [ ] Hardware parts ordered (relays, photodiodes, thermistor, Peltier, NFC reader)

### Phase 1: Parallel Foundation

- [ ] Stream A: concord_harness builds on native_sim (Stage 3 — deferred)
- [ ] Stream B: All 3 firmware overlays compile (Stage 3 — deferred)
- [ ] Stream C: All fixture channels verified (C10 acceptance test)
- [x] Stream D: MTIB server image built and pushed to registry
- [x] Stream D: MTIB server deployed to K3s validation nodes
- [x] Stream D: 24/27 RPCs PASS on both boards. V1+V2 power/GPIO/UART/ADC/accel/flash all verified. Motion N/A (hardware). AltimeterRead N/A (BME280 absent).
- [x] Stream G: CloudClient, TestContext, FixtureController built
- [ ] Stream G: CloudClient verified against real CoreCloud data

### Phase 2: Framework Integration

- [x] Stream F: TestContext composes MTIB + Cloud + Fixture + UART + Power
- [x] Stream F: conftest.py with session scope, firmware_build fixture, auto lifecycle
- [ ] Stream F: End-to-end dry run on real hardware (connect → flash → test → report)

### Phase 4-5: Stage 4 Proof

- [x] 9 test modules written (112 tests total)
- [x] Mock mode: 60 pass, 0 fail (no hardware required)
- [x] Smoke tests pass on debug build (REV 1.2)
- [x] Smoke tests pass on release build (REV 1.2)
- [x] Both firmware variants flashed + modem FW (REV 1.2)
- [ ] Stage 4 tests pass on debug build — **blocked on CoreCloud DB creds**
- [ ] Stage 4 tests pass on release build — **blocked on CoreCloud DB creds**
- [ ] All tests pass on REV 1.1 hardware — not yet attempted
- [x] MockCloudClient + 69 unit tests
- [x] Mock hardware stubs (FixtureController, PowerProfiler, UartDemuxer)
- [x] `HOST_TYPE_NRF9151_MODEM` added to proto + MTIB server + FixtureController

### Phase 6: Comparison

- [x] Debug vs release power profile compared (ch0: both ~50mA avg; ch1: release has 158mA peak from modem TX)
- [ ] Full power budget comparison after CoreCloud tests pass
- [ ] REV 1.1 vs REV 1.2 behavior comparison documented

---

## Test Module Inventory

### Product App Location: `apps/validation/alpha/`

Tests moved from `libs/` to product app pattern (matches `apps/manufacturing/alpha/`, `apps/validation/sigma5/`).

| Module | Functions | Executions | Mock Mode | HW Mode | Notes |
|--------|-----------|------------|-----------|---------|-------|
| `test_smoke_mtib.py` | 13 | 13 | Skip (HW only) | **13/13 PASS** | MTIB connection, GPIO, power, ADC, snapshot |
| `test_boot.py` | 5 | 10 (×2 fw) | **8 pass, 2 xfail** | Needs CoreCloud | fw_version xfail (BootMsgV2 lacks field — PRD gap) |
| `test_button.py` | 9 | 18 (×2 fw) | **18/18 PASS** | Needs CoreCloud | Short/long/very-long press, LED, SOS, power off |
| `test_biometric.py` | 3 | 6 (×2 fw) | **6/6 PASS** | Needs CoreCloud | On-skin, off-skin, temperature |
| `test_environmental.py` | 7 | 14 (×2 fw) | **14/14 PASS** | Needs CoreCloud | Temp, pressure, humidity, peltier, power rails |
| `test_power.py` | 7 | 14 (×2 fw) | **14/14 PASS** | Needs CoreCloud | Active/idle current, boot spike, trace stability |
| `test_motion.py` | 5 | 10 (×2 fw) | Skip (no motion HW) | Skip (no motion HW) | Needs FluidNC wired (MOTION_ENABLED=False) |
| `test_nfc.py` | 1 | 2 (×2 fw) | Skip (no NFC HW) | Skip (no NFC HW) | NFC reader not wired |
| `test_corecloud_integration.py` | 25 | 25 | Skip (no DB) | **Blocked on Jarred** | Auth, DB, messages, FUOTA, re-personalization |
| **Total** | **75** | **112** | **60 pass, 50 skip, 2 xfail** | **13 pass (smoke only)** | |

### Mock Mode Infrastructure

- **MockCloudClient**: Drop-in replacement for CloudClient with in-memory message store, same interface
- **MockFixtureController**: No-op hardware stubs returning plausible values (power, LED, temperature, ADC)
- **MockPowerProfiler**: Returns plausible power measurements within Stage 4 budget limits
- **MockUartDemuxer**: No-op UART capture
- **ScenarioEngine**: Prebuilt scenarios (happy_boot, network_registered, full_device_activity)
- **Auto-reinject**: Active scenario re-injected on `mark_test_start()` (handles mid-test resets)
- **time.sleep patch**: Capped at 0.01s in mock mode (Stage 4 tests have 30-60s hardware settle waits)
- **69 MockCloudClient unit tests** (`libs/python/corekinect/test/validation/tests/test_mock_cloud.py`)

### Firmware Flash Flow (updated)

Full flash cycle for Alpha B0 validation now supports modem firmware:

```
1. Flash nRF52840 app firmware      (--recover --chiperase, ~11s)
2. Flash nRF9151 modem firmware      (--sector_erase --recover, ~44s)  ← NEW
3. Flash nRF9151 comms app firmware  (--recover --chiperase, ~10s)
4. Power cycle + boot                (~5s)
5. Re-personalize                    (CoreOps proxy, ~6s)
6. Verify boot via CoreCloud         (wait_for_boot, ~120s timeout)
```

Env vars for `firmware_build` fixture:
- `FW_DEBUG_HEX` / `FW_RELEASE_HEX`: nRF52840 app firmware (required)
- `FW_DEBUG_COMMS_HEX` / `FW_RELEASE_COMMS_HEX`: nRF9151 comms firmware (optional)
- `FW_MODEM_ZIP`: nRF9151 modem firmware zip (optional, e.g., `mfw_nrf91x1_2.0.2.zip`)

### Hardware Runs (today, REV 1.2 — 10.4.45.33)

| Run | What Changed | Result | Duration |
|-----|-------------|--------|----------|
| Run 1 | Initial smoke only | 13/13 PASS (smoke) | ~2 min |
| Run 2 | Smoke + Stage 4 (first deploy) | Cloud tests blocked 120s each | ~3 hours |
| Run 3 | + corecloud markers + poll fix | 24F 23P 67S, firmware reflash every test | ~3 hours |
| Run 4 | + test reordering + flash cache | 24F 23P 67S in 826s (13:46) | 14 min |
| Run 5 | + GPIO fix + base64 parser + repersonalize | **23F 24P 67S** in 869s (14:28) | 14.5 min |

**Run 5 failure analysis (23 failures):**

| Category | Count | Root Cause | Fix |
|----------|-------|-----------|-----|
| `verify_dut_powered()` ch0-only | 6 | Checks ch0 current (~0mA after charger takeover) — DUT actually alive on ch1 | **Code: use `read_total_current()` (ch0+ch1)** |
| Power budget ch0-only | 5 | `PowerMeasure(channel=0)` reads ~0mA — same charger takeover issue | **Code: measure ch0+ch1 combined** |
| LED/photodiode not wired | 2 | ADC reads 0.0117V (baseline == active) — no photodiode on fixture | **Hardware: wire photodiode to ADC** |
| Motion stimulus absent | 2 | `MOTION_ENABLED=False` — FluidNC rail not connected | **Hardware: wire FluidNC rail** |
| Peltier temperature delta | 2 | Delta 0.001V — peltier not wired or insufficient power | **Hardware: verify peltier wiring** |
| Power rails mismatch | 2 | ADC channel labels differ from expected (SYS=ch3 reads 0.01V) | **Code: update ADC→rail mapping** |
| Power anomaly (min_current) | 2 | `min_current_ma > 0.5` assertion — ch0 reads -1 to 0mA (normal with charger) | **Code: use total current** |
| Smoke power_measure | 1 | `PowerMeasure(ch0)` avg=0mA — same charger takeover | **Code: use total current** |
| **GPIO permission** | **0** | **FIXED** — `configure_stimulus_gpios()` | N/A |
| **Re-personalization** | **0** | **FIXED** — base64 parser regex | N/A |

**Key insight:** 14 of 23 failures (61%) are caused by a single issue:
**power measurement/verification checks ch0 alone, but after BQ25180 charger
takeover ch0 drops to ~0mA while ch1 carries all DUT current.** Fixing
`verify_dut_powered()` and power tests to use `read_total_current()` (ch0+ch1)
should resolve the majority of failures with a code-only fix.

**Infrastructure milestones:**

| Action | Result |
|--------|--------|
| Smoke tests (mfg FW) | 12/13 PASS (power_on_and_read FAIL — FW wiped, low current) |
| Flash debug nRF52840 | OK (11.7s, 831KB) |
| Flash debug nRF9151 | OK (8.9s, 1MB) |
| Flash modem FW (v2.0.2) | OK (44.4s, 8.1MB) |
| Re-flash comms after modem | OK (10.1s) |
| Smoke tests (debug FW) | **13/13 PASS** |
| Flash release nRF52840 | OK (9.1s, 831KB) |
| Flash release nRF9151 | OK (10.1s, 1MB) |
| Re-flash modem + comms (correct order) | OK (modem 44.4s + comms 10.1s) |
| Smoke tests (release FW) | **13/13 PASS** |
| Debug FW power profile | Ch0: avg=50mA peak=99mA, Ch1: avg=4mA |
| Release FW power profile | Ch0: avg=50mA peak=72mA, Ch1: avg=4mA peak=158mA (modem TX) |
| Re-personalization (debug) | **PASS** — device_id=70B3D584C01E1FCC, keys uploaded |
| Re-personalization (release) | SKIP — release has no mfg shell (by design) |

---

## Re-personalization Workflow

**This is a standard process that MUST be followed every time firmware is flashed.**

When any firmware (manufacturing or production) is flashed via J-Link `--chiperase`:
1. AP protect requires full chip erase — personalization space is wiped
2. The device loses its EC keypair, server config, and device association
3. After flashing, the device must be re-personalized before it can talk to CoreCloud

**Standard sequence (automated in manufacturing, must be automated for validation):**

```
1. Flash firmware (J-Link --recover → --chiperase --program)
2. Power cycle + boot
3. Lock manufacturing shell (both UARTs, ~2s window)
4. Personalize via UART:
   a. CoreOps assigns device ID: POST /v1/devices/ids/assign {snr}
   b. Device generates new EC keypair on-device
   c. Upload public key: POST /v1/devices/keys/upload {deviceId, pubKey}
   d. Save SIM info: POST /v1/devices/iccids/save {iccid, carrier, snr, imei}
5. Rekey IPC (replace hardcoded keys with device-specific keys)
6. Enable AP protect
7. Power cycle — device is now ready for CoreCloud communication
```

**Permanent identifiers (survive re-flash):**
- J-Link SNR (hardware probe serial)
- IMEI (SIM hardware)
- Device ID (CoreOps assigns same ID for same SNR every time)

**Identifiers that CHANGE on re-flash + re-personalization:**
- EC public key (new keypair generated on device each time)

**CoreOps proxy:** `https://10.4.45.3:443` (manufacturing proxy server)
**Server URL:** `dev.office.corekinect.cloud` (session port 2022, data port 2023, time port 2024)
**Coproc FW app ID:** 108

**Validation implication:** Every time we flash different firmware variants
(mfg, debug, release) for testing, we must re-personalize. This adds ~30-60s
per flash cycle. The test framework's `fixture.flash_firmware()` must be
extended to include automatic re-personalization, or a separate
`repersonalize()` step must be called after each flash.

---

## Phase 6B: Concord Platform Integration (UI, Live Results, Artifacts)

This phase connects the validation test runner to the Concord web platform,
enabling live result viewing, run history, debug/release comparison, and
artifact downloads. The backend API and frontend pages are **already built** —
they need to be wired to the validation runner and verified end-to-end.

### What Already Exists

**Backend API (`apps/backend/http-api/src/api/v2/validation/`):**

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/v2/validation/runs` | GET | List runs with pagination + filters | Built |
| `/v2/validation/runs` | POST | Create a new validation run | Built |
| `/v2/validation/runs/<id>` | GET | Run detail with executions + results | Built |
| `/v2/validation/runs/<id>/cancel` | POST | Cancel an active run | Built |
| `/v2/validation/runs/<id>/trigger` | POST | Create K8s Job for a run | Built |
| `/v2/validation/runs/<id>/executions` | GET | List test executions (paginated) | Built |
| `/v2/validation/runs/<id>/executions/<eid>/results` | GET | Results for one execution | Built |
| `/v2/validation/runs/<id>/artifacts` | GET | List artifacts from MinIO | Built |
| `/v2/validation/runs/<id>/artifacts/<name>` | GET | Download artifact (presigned URL) | Built |
| `/v2/validation/runs/<id>/report/start` | POST | Reporter callback: session started | Built |
| `/v2/validation/runs/<id>/report/test-start` | POST | Reporter callback: test started | Built |
| `/v2/validation/runs/<id>/report/test-result` | POST | Reporter callback: test result | Built |
| `/v2/validation/runs/<id>/report/finish` | POST | Reporter callback: session finished | Built |

**Frontend pages (`apps/frontend/concord-app-svelte/src/routes/validation/`):**

| Page | Route | Features | Status |
|------|-------|----------|--------|
| Run List | `/validation/runs` | Paginated list, status filter, create form, multi-select for compare | Built |
| Run Detail | `/validation/runs/[id]` | Progress bar, execution table, auto-poll for active runs, trigger/cancel buttons | Built |
| Run Compare | `/validation/runs/compare?a=X&b=Y` | Side-by-side test comparison, status/duration/power deltas, diff highlighting | Built |

**pytest Reporter plugin (`libs/python/corekinect/test/validation/reporter.py`):**

| Feature | Status |
|---------|--------|
| Opt-in via `CONCORD_RUN_ID` + `CONCORD_API_URL` + `CONCORD_API_KEY` | Built |
| Fire-and-forget HTTP calls (never fails tests) | Built |
| Reports: session start, test start, test result (with measurements), session finish | Built |
| Power measurement extraction from TestContext | Built |

### What Needs to Be Done (Phase 6B Tasks)

#### 6B-1: Wire Reporter to K8s Job (LOW effort, ~2h)

The K8s Job manifest needs to:
1. Call `POST /v2/validation/runs` to create a run **before** launching the Job
2. Inject `CONCORD_RUN_ID`, `CONCORD_API_URL`, `CONCORD_API_KEY` as env vars
3. The trigger endpoint (`POST /runs/<id>/trigger`) already does most of this

**Decision needed:** Should run creation happen from:
- **(A) Frontend** — user clicks "New Run" in UI, fills in product/node/serial, then "Trigger" creates the K8s Job with env vars injected. (Recommended — trigger.py already generates API keys and sets env vars.)
- **(B) CLI** — `ctl.sh validation run alpha` creates run + launches Job
- **(C) Both** — API-first, CLI wraps API

#### 6B-2: Live Result Streaming (MEDIUM effort, ~4h)

The run detail page already auto-polls when `isActive`. Need to verify:
1. Reporter callbacks fire correctly from inside K8s pod
2. Test-level results appear in real-time on the detail page
3. Progress bar updates as tests complete
4. Power measurements are visible in result details

**Potential issue:** The reporter currently sends test results one at a time.
With 112 tests × 2 builds, that's 224 HTTP calls in ~15 minutes. Should be
fine (1 call every 4s), but verify latency doesn't affect test timing.

#### 6B-3: Artifact Upload + Download (MEDIUM effort, ~4h)

After each test, the framework saves UART logs to `ARTIFACTS_DIR` (currently
`/var/log/validation/`). These need to be uploaded to MinIO so users can
download them from the UI.

**Implementation:**
1. Add artifact upload to `teardown_test()` in TestContext or reporter
2. Upload to `validation-artifacts/{run_id}/{test_name}_uart.log`
3. Optionally upload power trace CSVs for power tests
4. Frontend artifact listing already works (presigned MinIO URLs)

**What artifacts to upload:**
- UART logs (per-test, always)
- Power traces (per-test, when PowerProfiler is used)
- Full pytest output log (per-run, once at finish)
- Firmware hex SHA256 hashes (per-run, once at start)

#### 6B-4: Run History + Trend Analysis (MEDIUM effort, ~8h)

The list page exists but needs:
1. **Product filter** — currently filters by status only, needs product dropdown
2. **Time range filter** — last 24h, 7d, 30d
3. **Trend sparklines** — pass rate over last N runs (optional, nice-to-have)
4. **Duration tracking** — total run time displayed on list page
5. **Firmware version column** — which FW was tested (from session config)

#### 6B-5: Debug vs Release Comparison (LOW effort, ~2h)

The compare page is already built. Usage flow:
1. User runs debug build → creates Run A
2. User runs release build → creates Run B
3. User selects both on list page → clicks "Compare" → `/runs/compare?a=A&b=B`
4. Side-by-side table shows: test name, category, status A vs B, duration A vs B, power A vs B

**What's needed:** Verify the compare page works correctly with real data.
May need to adjust how firmware variant is stored in session config vs
displayed in comparison headers.

#### 6B-6: Test Definition Management (LOW effort, ~4h)

Tests are auto-created in the DB when the reporter first encounters them
(see `report_test_start` → auto-creates Test record if not found). Need to
verify:
1. Test categories map correctly (module name → category)
2. Tests can be enabled/disabled per product
3. Sort order is preserved across runs

### Summary of Human Input Needed for Phase 6B

| Item | Who | What | Priority |
|------|-----|------|----------|
| Run creation UX | Mateo | Decide: frontend-only vs CLI vs both for triggering runs | HIGH |
| Artifact retention policy | Mateo | How long to keep UART logs + power traces in MinIO? | MEDIUM |
| Trend analysis scope | Mateo | What metrics matter for trend view? Pass rate? Duration? Power? | LOW |
| Comparison view features | Mateo | Any additional columns needed beyond status/duration/power? | LOW |

---

## Blockers

| Blocker | Affects | Status | Resolution |
|---------|---------|--------|-----------|
| ~~CoreCloud URL unknown~~ | ~~Stream G~~ | **RESOLVED** | `dev.office.corekinect.cloud` |
| ~~Alpha B0 availability~~ | ~~All on-device work~~ | **RESOLVED** | 2 boards: SNR 0964 (REV 1.2) + SNR 097D (REV 1.1) |
| ~~Device personalization~~ | ~~Stage 4 tests~~ | **RESOLVED** | Both devices personalized during manufacturing |
| ~~DEVICE_ID unknown~~ | ~~CloudClient~~ | **RESOLVED** | 0964→`70B3D584C01E1FCC`, 097D→`70B3D584C01E20A2` |
| ~~Container registry HTTPS~~ | ~~Docker builds~~ | **RESOLVED** | CA cert auto-extraction in devcontainer + buildkit |
| ~~Alpha mfg firmware `encryption_key.pem`~~ | ~~Firmware builds~~ | **RESOLVED** | `_ensure_encryption_keys()` + `_fix_app_sysbuild_key_path()` in ctl.sh |
| ~~MTIB server not yet deployed to K3s~~ | ~~On-hardware testing~~ | **RESOLVED** | Both pods running, power/GPIO/UART verified on real hardware |
| ~~LTE connectivity not verified~~ | ~~CoreCloud tests~~ | **RESOLVED** | Re-personalization working on debug build. Modem FW v2.0.2, IPC active, device boots to CoreCloud |
| ~~CoreCloud API exploration needed~~ | ~~Re-personalization~~ | **RESOLVED** | DB, REST, UART shell mapped. DevicePersonalizer built. V1↔V2 bridge done |
| ~~Re-personalization not automated~~ | ~~Firmware variant switching~~ | **RESOLVED** | DevicePersonalizer integrated into conftest.py firmware_build fixture |
| ~~MTIB server needs redeploy~~ | ~~ListProgrammers fix~~ | **RESOLVED** | 3 rebuilds deployed: PYTHONPATH fix, mux fix, family flag fix |
| ~~GPIO permission errors~~ | ~~Stimulus tests~~ | **RESOLVED** | `configure_stimulus_gpios()` auto-configures pins as OUTPUT |
| ~~Cloud test 120s timeouts~~ | ~~Test speed~~ | **RESOLVED** | `_poll()` fail-fast on non-transient errors + `@pytest.mark.corecloud` auto-skip |
| ~~Test run too slow (3+ hours)~~ | ~~Iteration speed~~ | **RESOLVED** | Test reordering + flash caching → ~15 min per full run |
| ~~Base64 key parser truncation~~ | ~~Re-personalization~~ | **RESOLVED** | Regex-based extraction waits for full key values |
| Fixture hardware not wired | Physical stimulus tests | **Open** | LED photodiode, motion rail, NFC reader, Peltier — all need wiring |
| DEV_1_0 DB/API creds needed | CloudClient E2E (42 tests) | **Blocked on Jarred** | Need PostgreSQL + SSH tunnel creds for `dmz-pg02.dmz.corekinect.com` |
| FUOTA REST API — zero endpoints | Phase 5 | **Firmly blocked** | 11 ORM tables exist but no REST endpoints. C# server may have them |
| Power budget specs unrealistic | Power test pass/fail | **Needs firmware team** | Idle: 5mA budget vs 36mA actual (includes active modem). Boot peak needs total current check |
| Release FW has no mfg shell | Release re-personalization | **By design** | Release build disables mfg shell. Option: personalize on debug, then flash release without re-personalization |
| Concord Reporter not yet wired | Live result streaming | **Ready to integrate** | Backend API + frontend pages built. Need to set env vars in K8s Job |

---

## Parallel Work Plan — Engineer 2

### Completed (2026-03-02)

1. ~~**CoreCloud API exploration**~~ — **DONE.** CloudClient switched to DEV_1_0 (devices personalized against dev, not val). Added `--db-env` CLI option. SSH tunnel env var template updated.
2. ~~**Re-personalization automation**~~ — **DONE.** `DevicePersonalizer` class built at `libs/python/corekinect/test/validation/device_personalizer.py`. Bridges V1/V2 gap. Integrated into conftest.py `firmware_build` fixture for auto re-personalization after each flash.
3. ~~**FUOTA API investigation**~~ — **DONE.** 11 ORM tables exist, zero REST endpoints in Python SDK. Phase 5 firmly blocked — workaround is direct DB writes via ORM. C# server likely has endpoints but undocumented.

### Completed (2026-03-02, continued)

4. ~~**Fix `encryption_key.pem` path issue**~~ — **DONE.** `_ensure_encryption_keys()` + `_fix_app_sysbuild_key_path()` in ctl.sh.
5. ~~**Build alpha firmware variants**~~ — **DONE.** All 6 builds (mfg, debug, release × alpha_b0). Artifacts collected.
6. ~~**Rebuild + deploy MTIB server**~~ — **DONE.** 3 rebuilds: PYTHONPATH fix, J-Link mux fix, nrfjprog family flags.
7. ~~**J-Link flash end-to-end**~~ — **DONE.** Upload + flash both chips on both boards. Full pipeline verified.

### Completed (2026-03-02, evening)

8. ~~**Flash all firmware variants + verify**~~ — **DONE.** Debug + release flashed to both nRF52840 + nRF9151 on REV 1.2. Modem FW v2.0.2 flashed. All smoke tests 13/13 PASS.
9. ~~**Mock mode infrastructure**~~ — **DONE.** MockCloudClient (69 unit tests), MockFixtureController, MockPowerProfiler, MockUartDemuxer. ScenarioEngine + auto-reinject. 60/112 tests pass with MOCK_CLOUD=1.
10. ~~**Product app pattern**~~ — **DONE.** Tests moved to `apps/validation/alpha/`. conftest.py adapted. pytest.ini, setup.py, project.json, Dockerfile scaffolded.
11. ~~**HOST_TYPE_NRF9151_MODEM**~~ — **DONE.** Proto + stubs regenerated. MTIB server handler updated. FixtureController supports `target='nrf9151_modem'`. Firmware_build fixture handles modem flash before comms app flash.

### Completed (2026-03-02, night)

12. ~~**Build + deploy validation container**~~ — **DONE.** `concord-validation-alpha` Docker image built, pushed to `containers.ad.corekinect.com`, deployed as K8s Job on concordagent01. Full flow: flash → modem FW → re-personalize → smoke + Stage 4. 5 runs completed.
13. ~~**Modem FW mandatory in flash flow**~~ — **DONE.** `FW_MODEM_ZIP` env var → flashed before comms app if set. Comms flash uses `--chiperase` which wipes modem → modem must go first.
14. ~~**CloudClient fail-fast on non-transient errors**~~ — **DONE.** `_poll()` now raises immediately on TypeError/AttributeError/ImportError instead of retrying for 120s. Prevents corecloud tests from blocking 2 minutes each.
15. ~~**@pytest.mark.corecloud auto-skip**~~ — **DONE.** `pytest_collection_modifyitems` detects missing DB creds and skips corecloud-marked tests. 42 tests auto-skipped when DB not configured.
16. ~~**Test reordering by firmware variant**~~ — **DONE.** Groups all [debug] first, then [release]. Reduces flash cycles from 2×N to 2. Flash caching via `_current_variant` skips redundant reflashes.
17. ~~**GPIO permission fix (stimulus pins)**~~ — **DONE.** `configure_stimulus_gpios()` configures button(2), on_skin(3), peltier(4), charger_relay(5) as OUTPUT before writes. Called from `power_on()` and each stimulus method.
18. ~~**Base64 key parser fix**~~ — **DONE.** UART stream now waits for BOTH hex (≥100 chars) and base64 (≥40 chars) values before breaking. Regex-based extraction. Re-personalization now succeeds on debug firmware.
19. ~~**Re-personalization from K8s pod**~~ — **DONE.** Pod on concordagent01 reaches CoreOps at `http://10.4.45.30:8001`. No SSH tunnel needed.

### In Progress

20. **NFC MTIB server extension** — In progress:
    - Add NFC RPCs to `mtib.proto` (NfcPoll, NfcReadNdef)
    - Implement handlers in MTIB server
    - Unblocks `test_nfc.py` when NFC reader is wired

21. **Rebuild + deploy MTIB server** — Pending:
    - NRF9151_MODEM proto change + NFC RPCs need server rebuild + deploy to both nodes

### Next

22. **Validate CloudClient end-to-end** — Blocked on Jarred (DEV_1_0 DB creds):
    - Power cycle device → check BootMsgV2 appears at CoreCloud
    - Verify message polling works with real data
    - Tune timeouts and poll intervals

23. **REV 1.1 hardware runs** — Same smoke + flash cycle on 10.4.45.32

24. **Motion hardware** — Mateo connecting FluidNC linear rail:
    - When connected: set `MOTION_ENABLED=true` in validation MTIB server
    - Unblocks 10 motion tests in `test_motion.py`

25. **Concord Reporter integration** — Wire pytest reporter to backend API:
    - Set `CONCORD_RUN_ID`, `CONCORD_API_URL`, `CONCORD_API_KEY` in K8s Job
    - Test results stream to Concord API in real-time
    - Frontend shows live progress (already built, see Phase 6B)

26. **Artifact upload** — Upload UART logs + power traces to MinIO:
    - Upload artifacts at `teardown_test()` to `validation-artifacts/{run_id}/`
    - Backend already has `GET /artifacts` + presigned download URLs

27. **LED photodiode fixture wiring** — LED color tests fail (ADC reads ~0V):
    - Needs photodiode wired to ADC channel
    - Unblocks `test_led_color_on_status`, `test_short_press_led_response`

28. **Power budget recalibration** — Current limits may be too tight:
    - Idle: 5mA budget vs 36mA actual (DUT includes active modem)
    - Boot peak: 200mA budget vs actual TBD
    - Need firmware team input on realistic budgets

### Blocked on humans

- **Jarred:** DEV_1_0 DB/API creds + SSH tunnel access to `dmz-pg02.dmz.corekinect.com`
- **Jarred:** FUOTA REST endpoint documentation (C# server)
- **Jarred:** Realistic power budget numbers for Alpha B0 (current specs may be design targets, not operational limits)
- **Mateo:** Motion hardware wiring (FluidNC linear rail)
- **Mateo:** NFC reader wiring (I2C bus on fixture)
- **Mateo:** LED photodiode wiring (ADC channel on fixture board)

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-25 | MTIB server redesign: v1 style + v2 observability | v2 is overcomplicated; v1 pattern is clean and sufficient |
| 2026-02-25 | UART parsing client-side (not in MTIB) | Keeps MTIB generic; concord protocol is a test framework concern |
| 2026-02-25 | Async gRPC (grpcio-aio) for MTIB server | Needed for parallel observability + real-time UART streaming |
| 2026-02-25 | 29 charging tests deferred | DUT + CHG share same MTIB power source; no battery sync |
| 2026-02-25 | No BLE in this POC | Focus on core validation path first |
| 2026-02-26 | 7 GNSS tests deferred | Indoor scaffold, no GPS signal source |
| 2026-02-26 | Test count 71 → 64 | Charging (29) + Config (18) + GNSS (7) deferred = 54 deferred total |
| 2026-03-01 | 2 Alpha B0 boards for validation | SNR 0964 (REV 1.2) + SNR 097D (REV 1.1) — enables parallel rev testing |
| 2026-03-01 | CoreCloud server: dev.office.corekinect.cloud | Obtained from manufacturing personalization records |
| 2026-03-01 | Re-personalization mandatory after every flash | AP protect requires chip erase → personalization wiped → must re-personalize |
| 2026-03-01 | Public key changes, SNR/IMEI/DeviceID permanent | EC keypair regenerated on device during personalization; hardware IDs are immutable |
| 2026-03-01 | NFC test skipped until hardware wired | test_nfc.py written but marked @pytest.mark.skip |
| 2026-03-01 | Stage 3 work deferred | Focus on Stage 4 product validation first; Stage 3 (harness) can come later |
| 2026-03-01 | Actual test count: 37 (36 active + 1 skipped) | 7 modules × debug/release = 72 test executions per device |
| 2026-03-02 | GPIO 0+1 must be OUTPUT LOW for DUT boot | Without this, INA219 shows 4.5V but 0mA. Manufacturing code had this in step_0.py. |
| 2026-03-02 | DUT power verified on both boards | REV 1.2: 34mA@4.46V, REV 1.1: 33mA@4.5V. Charger takes over at ~24-39mA@5V. |
| 2026-03-02 | UART verified on both boards | nRF52840: battery/watchdog/IPC logs. nRF9151: modem checkin. Both have mfg FW pre-loaded. |
| 2026-03-02 | ListProgrammers bug found and fixed | _assign_jlinks() not called during ListProgrammers — always returned empty list. |
| 2026-03-02 | MTIB server has both V1 and V2 RPCs | Server implements DutPowerEnable (V1) AND PowerEnable (V2). No proto mismatch — both work. |
| 2026-03-02 | CloudClient switched to DEV_1_0 | Devices personalized against dev.office, not val. DB requires SSH tunnel via dmz-pg02. |
| 2026-03-02 | DevicePersonalizer complete | V1/V2 bridge built. Auto re-personalization in conftest.py firmware_build fixture. |
| 2026-03-02 | FUOTA: zero REST endpoints | 11 ORM tables, firmware-side client exists, but no Python REST API. Phase 5 firmly blocked. |
| 2026-03-02 | GPIO 0+1 is Alpha-fixture-specific | Client/test framework must configure these before boot. NOT a server concern — MTIB stays generic. |
| 2026-03-02 | Engineer 2 pivoted to firmware work | Blocked on Jarred for DB creds. Picking up: encryption_key.pem fix, firmware builds, MTIB redeploy. |
| 2026-03-02 | ADC verified on both boards | 8 channels: Ch7=3.3V ref, Ch0/2=~4.5V power rails, Ch1=2.5V (divider?), Ch3-6=0V (unused/unconnected). |
| 2026-03-02 | UART boot capture shows full boot sequence | MCUboot→nRF52840 app→nRF9151 comms all captured. Mfg shell prompt visible. Shell auto-locks after ~8s. |
| 2026-03-02 | Device personalization may be wiped | nRF9151 shows "No EUI in flash - using default". EUI `70B3D584C02003B4` doesn't match assigned device IDs. Re-personalization needed. |
| 2026-03-02 | Modem FW v2.0.2 confirmed | nRF9151 modem firmware version identified. FUOTA coproc app ID=111 v0.1.1. |
| 2026-03-02 | Motion hardware not connected | `MOTION_ENABLED=False` on both MTIBs. FluidNC linear rail not wired. Stream C dependency. |
| 2026-03-02 | MotionStart streaming bug fixed | Server returned non-iterator when motion disabled. Fixed to use yield/yield-from. Needs redeploy. |
| 2026-03-02 | REV 1.1 UART1 (nRF52840) garbled output | ~~Initially reported garbled~~ — **CORRECTED: works fine.** 28KB, 431 lines, 97% readable. Previous run was connection issue. |
| 2026-03-02 | REV 1.1 nRF9151 initial bytes garbled | MCUboot output before DTS overlay kicks in uses wrong pin config (REV 1.1 HW pin swap). App output is clean. |
| 2026-03-02 | Integrated real-world test: 10/10 both boards | Power cycle, GPIO config, boot current (66-67mA peak, 33-38mA steady), ADC, UART, charge power, shutdown all pass. |
| 2026-03-02 | Mfg shell interaction verified | lock_shell + debug_enable + kernel version + device eui all work via UART on both boards. Shell locks within 1.5s of boot. |
| 2026-03-02 | REV 1.1 still personalized, REV 1.2 wiped | REV 1.1 EUI=`70B3D584C01E20A2` (matches assigned). REV 1.2 EUI=`70B3D584C02003B4` (default — was re-flashed). |
| 2026-03-02 | I2C sensor status on test fixtures | LSM6DSO accel: OK both. BME280: FAIL both (error -5, likely not present). LP5814 LED: FAIL REV 1.1. PPG: missing REV 1.2. |
| 2026-03-02 | encryption_key.pem fix complete | Eng 2: `_ensure_encryption_keys()` + `_fix_app_sysbuild_key_path()` in ctl.sh. Auto-generates + fixes paths. |
| 2026-03-02 | Boot power profile consistent | Both REVs: ~27-37mA initial, dip to 2-4mA (sleep?), ramp to 51-67mA (modem init?), settle to 33-38mA steady state. |
| 2026-03-02 | PYTHONPATH fix in Dockerfile | Added `/libs/protocols` to PYTHONPATH. Generated `mtib_pb2_grpc.py` does `from mtib import mtib_pb2` which needs protocols dir on path. |
| 2026-03-02 | J-Link mux polarity inverted in hardware | REV 1.2: P0=LOW→nRF9151, P0=HIGH→nRF52840. Opposite of original design assumption. Firmware handler + TCA9534A comment corrected. |
| 2026-03-02 | REV 1.1 has 2 J-Link probes too | Probes: 821009546→nRF52840, 821009537→nRF9151. REV 1.2 probes: 821009543→nRF52840, 821009541→nRF9151. |
| 2026-03-02 | nRF91 flash cannot verify | Secure firmware enables APPROTECT immediately after programming — flash readback returns all zeros. Skip `--verify` for NRF91 family. |
| 2026-03-02 | nrfjprog needs explicit family flag | `-f NRF52` for nRF52840, `-f NRF91` for nRF9151. Also needs `--chiperase --reset` for clean flash. |
| 2026-03-02 | Full flash pipeline working | Upload (0.2s) → Flash nRF52840 (~11s) → Flash nRF9151 (~8s) → Power cycle → Boot (4-5s) → UART verified. Both REVs. |
| 2026-03-02 | All 6 alpha firmware variants built | Eng 2: mfg, debug, release × alpha_b0. Collected to `libs/corekinect/test/validation/assets/firmware/`. Parallel build support added to ctl.sh. |
| 2026-03-02 | Validation container deployed as K8s Job | One-shot job on concordagent01. `backoffLimit: 0`, `restartPolicy: Never`. Direct network access to MTIB + CoreOps. |
| 2026-03-02 | CloudClient `_poll()` fail-fast | Non-transient errors (TypeError, AttributeError, ImportError) raise immediately instead of retrying for timeout_s. Prevents 120s stalls. |
| 2026-03-02 | `@pytest.mark.corecloud` auto-skip pattern | `pytest_collection_modifyitems` checks for DB creds and auto-skips corecloud-marked tests. Zero manual skip decorators needed on individual tests. |
| 2026-03-02 | Test reordering by firmware variant | `pytest_collection_modifyitems` sorts all [debug] first, then [release]. Combined with `_current_variant` flash caching → 2 flash cycles per run instead of ~70. |
| 2026-03-02 | GPIO stimulus auto-configuration | `configure_stimulus_gpios()` configures button/on_skin/peltier/charger_relay as OUTPUT before any write. Called from `power_on()` and each stimulus method as safety net. |
| 2026-03-02 | UART base64 parser uses regex | Stream loop break condition checks both hex (≥100 chars) and base64 (≥40 chars) via regex before breaking. Prevents truncation when UART data arrives in fragments. |
| 2026-03-02 | Release FW re-personalization not possible | Release build has no mfg shell (by design — SHELL=n). Can only personalize on debug/mfg build. Strategy: personalize once on debug, then flash release. |
| 2026-03-02 | Power budget numbers need review | Idle 5mA budget unrealistic with active modem (actual ~36mA). Boot peak test reads ch0 only (~0mA after charger takeover). Need firmware team to clarify operational vs sleep budgets. |
| 2026-03-02 | Concord backend API for validation complete | 14 endpoints covering CRUD, trigger, reporter callbacks, executions, results, artifacts. Frontend pages for list/detail/compare built. Reporter plugin built. Only wiring remains. |
