# Stage 4 Proof — Status Tracker

> Last updated: 2026-03-03

## Current Phase: **Phase 3 — Smoke Tests PASSING, Full Suite Pending Live Run**

Phase 0.5 (Manufacturing Tests): **REV 1.2 FULLY VERIFIED** — fw_flash 3/3 PASS, POST 11/11 PASS (including CoreOps personalization + IPC rekey). Containerized and deployed to K8s.
Phase 1 (MTIB Server): **M1-M10 COMPLETE** — deployed, 24/27 RPCs verified on both boards (3 expected fails: motion disabled, altimeter absent).
Phase 0.5 (Firmware Build Tooling): `ctl.sh` done, builds pending Docker image pull. Pre-built hex files available.
Phase 2A (Python Test Framework): **Code complete + smoke verified.** 13/13 MTIB smoke tests PASS on BOTH REV 1.1 and REV 1.2. Dual-rail power (ch0+ch1) confirmed required for cold boot.
Phase 3 (Test Modules): All 8 modules written (112 tests collected). Pending full live run with firmware + CoreCloud.
Phase 6 (Orchestration & Visibility): **6A-6E complete** (backend API + pytest reporter + frontend pages + trigger endpoint + comparison dashboard). 381 backend tests passing.
Deploy Infrastructure: Helm chart v0.2.0 with Prisma migration init container, ctl.sh diff/status commands, staging/production values aligned.

---

## Progress Scorecard

| Phase | Weight | Progress | Notes |
|-------|--------|----------|-------|
| **Phase 0** Prerequisites | 10% | **~90%** | K8s nodes, devices, personalization all done. Firmware builds blocked on Docker image pull. LTE connectivity not yet verified. |
| **Phase 1** MTIB Server | 15% | **100%** | M1-M10 complete. 24/27 RPCs PASS both boards. Server deployed. |
| **Phase 2A** Test Framework | 20% | **~85%** | Code complete. 13/13 smoke PASS both boards. FixtureController dual-rail power verified. PowerProfiler verified. CloudClient + UartDemuxer untested (need CoreCloud creds + flashed firmware). |
| **Phase 2B** CoreCloud Integration | 10% | **~15%** | 22 tests written, 0 executed (blocked on CoreCloud credentials from Jarred). |
| **Phase 3** Product Test Proof | 25% | **~50%** | All 8 modules written (112 tests collected via pytest). Pending full live run with firmware + CoreCloud. |
| **Phase 4** Comparison | 5% | **0%** | Blocked on Phase 3 completion. |
| **Phase 5** FUOTA | 5% | **~10%** | Mechanism confirmed (DB + Azure). Blocked on DB write access + Azure creds. |
| **Phase 6** Orchestration & Visibility | 10% | **100%** | 6A-6E complete. 381 backend tests passing. Trigger + comparison dashboard done. |
| **Deploy** Infrastructure | — | **100%** | Helm v0.2.0, init container, ctl.sh diff/status, validation manifests deployed. |
| **Overall** | | **~70%** | Code-complete for all written phases. Blocked on: CoreCloud creds, firmware builds, LTE verification. |

---

## Stream Status

| Stream | Phase | Status | Blocked By | Notes |
|--------|-------|--------|-----------|-------|
| **F** Firmware assets | 0.5 | **Tooling complete** | Docker image pull + build run | `ctl.sh` + `build.sh` + overlays done. Need to run `ctl.sh build-all alpha`. |
| **M** MTIB server updates | 1 | **M1-M10 COMPLETE** | — | Proto, handlers, wiring, client, deploy all done. 24/27 RPCs PASS both boards. |
| **A** Python test framework | 2 | **Code complete + smoke verified** | CoreCloud creds for integration test | CloudClient, FixtureController, UartDemuxer, PowerProfiler, TestContext, DevicePersonalizer, ConcordReporter — all written at `libs/python/corekinect/test/validation/`, imports verified. 112 tests collected (99 Stage 4 parametrized + 13 smoke). Smoke 13/13 PASS both boards. |
| **B** Fixture wiring | 2 | Partially done | Parts for Stage 4 stimulus | Manufacturing baseline wired; need button/charger relays, photodiode, Peltier, NFC, motion |
| **C** Stage 4 test modules + E2E | 3 | **Code complete** | Firmware + CoreCloud creds for E2E run | 8 modules written, 112 tests collected (99 Stage 4 parametrized debug+release + 13 smoke). NFC skipped (B6 not wired). E2E runs need firmware flashed + CoreCloud connected. |

---

## Phase Checklist

### Phase 0: Prerequisites

**K8s Node Onboarding:**
- [x] REV 1.2 Verdin board flashed — `verdin-imx8mm-15005665` at 10.4.45.33
- [x] REV 1.1 Verdin board flashed — `verdin-imx8mm-15702161` at 10.4.45.32
- [x] Both nodes joined K3s cluster
- [x] Both nodes labeled (`role=edge`, `purpose=validation`, `mtib-revision`)
- [x] K8s roles assigned to edge nodes (`node-role.kubernetes.io/edge`)
- [x] `00-labels-taints.sh` updated (stale mfg nodes removed, MTIB revision labels added)
- [x] `validation-rev11.yaml` created and deployed
- [x] `validation-rev12.yaml` created and deployed
- [x] Old `mtib-server-validation` deployment cleaned up (not present in cluster)

**Infrastructure Verification:**
- [x] K3s cluster access verified (`kubectl get nodes`)
- [x] V1 MTIB server operational on REV 1.1 node — HealthCheck `ready: true`, DutPowerRead OK
- [x] V1 MTIB server operational on REV 1.2 node — HealthCheck `ready: true`, DutPowerRead OK
- [x] Alpha B0 board sourced — two devices: SNR 0964 (REV 1.2) and SNR 097D (REV 1.1)
- [ ] Motion scaffold status confirmed (existing or need to build)
- [x] CoreCloud VAL_1_0 environment URL obtained — Auth: 2013, REST: 2018, DB: 5432, Session: 2018, Data: 2017, Time: 2016
- [ ] Hardware parts ordered (relays, photodiodes, thermistor, etc.)

**Device Personalization:**
- [x] REV 1.2 (SNR 0964) re-personalized — POST step_9 personalize + step_10 rekey IPC PASS (via K8s pod, CoreOps at `http://10.4.45.30:8001`)
- [x] REV 1.1 (SNR 097D) still personalized from manufacturing batch 9 — EUI `70B3D584C01E20A2` confirmed
- [ ] LTE connectivity verified (device boots, connects to CoreCloud)
- [ ] BootMsgV2 received at CoreCloud from personalized device

**Firmware Assets (Phase 0.5):**
- [x] Pin swap overlays created at repo level (`overlays/nrf52840_pinswap.overlay`, `nrf9151_ns_pinswap.overlay`)
- [x] Default pin correction overlays created (`overlays/nrf52840_default_pins.overlay`, `nrf9151_ns_default_pins.overlay`)
- [x] `build.sh` updated with `--mtib-rev 1.1|1.2` and `--variant debug` flags
- [x] `mergehex` wrapper installed (Python intelhex → drop-in replacement)
- [x] `ctl.sh` Docker build orchestrator created (`apps/firmware/products/ctl.sh`)
- [x] Nx targets updated for Docker builds (`build:docker`, `build:all-variants`, `collect`)
- [x] MCUboot encryption key issue fixed — `ctl.sh` pre-build step auto-generates keys via `imgtool.py` in Docker + fixes app sysbuild.conf paths for monorepo mount layout
- [ ] All 12 firmware assets built (3 variants × 2 MCUs × 2 MTIB revs) — via `ctl.sh build-all alpha`
- [ ] Mfg firmware UART verified on REV 1.1 (fw_flash 3/3 PASS, but POST step_0 lock_shell timeout — UART not responding after boot)
- [x] Mfg firmware UART verified on REV 1.2 (shell commands work — all 11 POST steps PASS)
- [x] POST tests pass on REV 1.2 (11/11 PASS including CoreOps personalization + IPC rekey)
- [ ] POST tests pass on REV 1.1 (step_0 lock_shell timeout — needs UART investigation)
- [ ] Debug firmware logs visible on both MTIB revisions
- [ ] Release firmware silent on both MTIB revisions
- [ ] Artifacts stored in `libs/corekinect/test/validation/assets/firmware/` with `manifest.json`

### Phase 1: MTIB Server Updates

- [x] M1: Proto updated — 34 RPCs (26 old kept as aliases + 8 new V2), bindings regenerated, backward compat verified
- [x] M2: Power handler — unified channel-based API, PowerMeasure (stats over duration), PowerStream (~100Hz server-streaming), legacy V1 aliases preserved
- [x] M3: GPIO handler — GpioWatch streaming via gpiod edge detection, get_snapshot_data()
- [x] M4: ADC handler — AdcStream at configurable interval, get_snapshot_data()
- [x] M5: UART handler — no changes needed (already clean)
- [x] M6: Flash handler — J-Link speed fixed to 4000, REV 1.2 J-Link mux via TCA9534A P0
- [x] M7: Motion handler — REV 1.2 motor power switch (VMM_EN via TCA9534A P2) with error handling
- [x] M8: Observability + wiring — HealthCheck extended (hw_revision, capabilities), GetSnapshot aggregates power/gpio/adc, all 8 V2 RPCs wired, TCA9534A init on REV 1.2
- [x] M8b: Error handling pass — _read_ina219 returns (err, v, mA, mW), _set_motor_power returns Optional[str], _select_jlink_target returns Optional[str], all callers check errors, TCA9534A driver created at src/hardware/tca9534a.py
- [x] M9: V1 client updated — 9 new methods (PowerEnable/Disable/Read/Measure/Stream, GpioWatch, AdcStream, HealthCheckExtended, GetSnapshot), client-side dataclasses (PowerReadResult, PowerMeasureResult, SnapshotResult, HealthCheckExtendedResponse), backward compat preserved (HealthCheck returns same 3-tuple)
- [x] M10: Server deployed to K3s — 24/27 RPCs PASS (both V1 and V2), 3 expected fails (motion disabled, altimeter absent). Both REV 1.1 and REV 1.2 verified.
- [x] Manufacturing backward compatibility confirmed — Alpha mfg app migrated to V1 RPCs, fw_flash 3/3 + POST 11/11 PASS on REV 1.2. Container deployed to K8s: `containers.ad.corekinect.com/concord-manufacturing-alpha:latest`

### Phase 2: Test Infrastructure

- [x] Stream A: CloudClient code written (`cloud_client.py`) — polling over MsgBase.since_server_time(), sync pattern
- [x] Stream A: FixtureController code written (`fixture_controller.py`) — wraps MTIB V1 PowerEnable/GpioWrite/etc, FixtureProfile from JSON
- [x] Stream A: UartDemuxer code written (`uart_demuxer.py`) — background thread captures UartStream, timestamped log buffer
- [x] Stream A: PowerProfiler code written (`power_profiler.py`) — PowerMeasure + PowerStream wrappers, PowerTrace stats
- [x] Stream A: TestContext + conftest code written (`test_context.py`, `conftest.py`) — from_env(), session fixture, firmware_build parametrization
- [x] Stream A: Fixture profile JSON created (`fixtures/alpha_b0.json`) — pin mappings TBD pending schematic verification
- [x] Stream A: All imports verified (PYTHONPATH=libs/python:libs:libs/protocols)
- [x] Stream A: DevicePersonalizer added (`device_personalizer.py`) — wraps V1 client shell commands + CoreOps API for auto re-personalization after flash
- [x] Stream A: firmware_build fixture auto-repersonalizes after each flash (opt-in via PROXY_SERVER_URL + DEVICE_SNR)
- [ ] Stream A: CloudClient queries return real data from CoreCloud DEV_1_0 (needs SSH tunnel + DB creds)
- [x] Stream A: FixtureController drives GPIO, reads ADC via MTIB V1 — **13/13 smoke tests PASS on both boards** (dual-rail power, GPIO config, ADC reads all verified)
- [ ] Stream A: UartDemuxer captures UART logs from debug build (needs MTIB + flashed firmware)
- [x] Stream A: PowerProfiler records measurements via MTIB V1 — ch0+ch1 reads working, REV 1.1: 23mA total, REV 1.2: 8mA total (no FW)
- [x] Stream A: TestContext.from_env() works end-to-end on validation network — smoke test used it successfully
- [ ] Stream B: All fixture channels wired and verified (acceptance test)

### Phase 2B: CoreCloud Integration Tests

- [x] Comprehensive CoreCloud reference document written (`corecloud-complete-reference.md`) — 18+ Confluence pages extracted
- [x] CoreCloud integration test suite written (`test_corecloud_integration.py`) — 22 tests in 7 groups
  - Group 1: Authentication & connectivity (auth server, REST server, CoreOps proxy)
  - Group 2: Database connectivity (query all message types via SDK)
  - Group 3: Device registration & identity (device ID determinism, type/variant, active status)
  - Group 4: Message history (boot, network, position, hw failures — read-only)
  - Group 5: FUOTA table access (FuotaTbl, FuotaListsTbl, progress — Phase 5 prerequisite)
  - Group 6: Re-personalization flow (full end-to-end with MTIB + DUT)
  - Group 7: Webhook verification (optional, for data forwarding)
- [ ] All Group 1 tests pass (auth + connectivity) — needs credentials from Jarred
- [ ] All Group 2 tests pass (DB queries) — needs SSH tunnel + DB creds
- [ ] All Group 3 tests pass (device identity) — needs REST API creds
- [ ] All Group 4 tests pass (message history) — needs DB connection
- [ ] All Group 5 tests pass (FUOTA tables) — needs DB write access
- [ ] All Group 6 tests pass (re-personalization) — needs MTIB + DUT + CoreOps + LTE
- [ ] All Group 7 tests pass (webhooks) — optional

### Phase 3: Product Test Proof

- [x] Stream C: All 8 test modules written (112 tests collected: 99 Stage 4 parametrized debug+release + 13 smoke; GNSS deferred, NFC skipped until wired)
  - `test_boot.py` — 5 tests (boot msg, FW version, current budget, HW failures, comms failures)
  - `test_motion.py` — 5 tests (shake detection, stationary, accel data, motion stops, repeated cycles)
  - `test_biometric.py` — 3 tests (on-skin, off-skin, temperature field)
  - `test_button.py` — 9 tests (short press, long press, very long press, LED, double press, etc.)
  - `test_environmental.py` — 7 tests (temp, pressure, humidity, Peltier, power rails, updates)
  - `test_power.py` — 7 tests (active, boot spike, idle, on-skin impact, motion impact, trace, anomalies)
  - `test_nfc.py` — 1 test (skipped until B6 wiring)
  - `test_corecloud_integration.py` — 22 tests in 7 groups (auth, DB, identity, messages, FUOTA, re-personalization, webhooks)
- [ ] Stream C: Debug build — all tests pass
- [ ] Stream C: Release build — all tests pass
- [ ] Stream C: CoreCloud receives expected messages for all tests
- [ ] Stream C: Power measurements recorded for all power tests

### Phase 4: Comparison

- [ ] All 112 tests compared across debug + release builds
- [ ] Power measurements compared (debug vs release)
- [ ] Discrepancies documented as bug reports
- [ ] Final recommendation written (which tests are release-authoritative)

### Phase 6: Orchestration, Visibility & CI/CD

- [x] 6A: Backend validation run API — **13 routes implemented, 381 total backend tests passing**
  - Public: POST/GET `/validation/runs`, GET `/runs/<id>`, POST `/runs/<id>/cancel`
  - Sub-resources: GET `/runs/<id>/executions`, GET `/runs/<id>/executions/<eid>/results`
  - Artifacts: GET `/runs/<id>/artifacts`, GET `/runs/<id>/artifacts/<name>` (MinIO presigned URLs)
  - Reporter callbacks: POST `/runs/<id>/report/{start,test-start,test-result,finish}`
  - Permissions: `Concord.Admin.Validation.View` / `Concord.Admin.Validation.Manage`
  - Storage: `validation/artifacts` prefix added to MinIO StoragePrefixes
  - Auto-creates Test definitions on first reporter call (no pre-seeding needed)
  - Files: `src/api/v2/validation/runs/{types,runs,executions,artifacts,reporter}.py`
  - Tests: `tests/unit/types/test_validation_runs_types.py`, `tests/api/validation/test_runs.py`
- [x] 6B: pytest reporter plugin — **ConcordReporter class at `libs/python/corekinect/test/validation/reporter.py`**
  - Opt-in via `CONCORD_RUN_ID` + `CONCORD_API_URL` + `CONCORD_API_KEY` env vars
  - Hooks: `pytest_sessionstart`, `pytest_runtest_logstart`, `pytest_runtest_makereport` (hookwrapper), `pytest_sessionfinish`
  - Fire-and-forget HTTP: never causes test failures, logs warnings on error
  - Auto-registered via `pytest_plugins` in validation `conftest.py`
  - Extracts power measurements from `ctx.power.last_measurement` (if available)
  - 13 tests passing at `tests/lib/test_reporter.py` (importlib-based to bypass broken parent `__init__.py`)
- [x] 6C: Frontend validation pages — **list + detail at `/validation/runs`**
  - List page: paginated table with status filter, progress display (passed/failed/total)
  - Detail page: stats cards (progress bar, passed, failed, duration), devices, execution table
  - TypeScript types added to `models.ts` (ValidationRun, ValidationExecution, ValidationDevice, etc.)
  - StatusBadge updated with QUEUED, PASSED, COMPLETED, CANCELLED colors
  - Sidebar nav entry added (Validation, gated by `Concord.Admin.Validation.View`)
  - 5s polling for active runs (Socket.IO deferred to 6E)
  - Cancel button with confirmation dialog (requires `Concord.Admin.Validation.Manage`)
  - Trigger Run button on detail page (inline form, firmware version input, gated on ACTIVE + Manage)
  - Notes section on detail page (shows `run.notes` if present)
  - Validation permissions added to `prisma/seed.py` (ALL_PERMISSIONS + ADMIN_PERMISSIONS)
  - OpenAPI docs added for all 12 validation endpoints in `src/api/v2/docs.py` (4 schemas + 12 paths)
- [x] 6D: Build-server integration + simulator — **trigger endpoint + simulator script implemented, 6 integration tests + 6 unit tests passing**
  - `POST /v2/validation/runs/<run_id>/trigger` — creates K8s Job from existing `validation_job.yaml` template
  - `RunTriggerRequest` type with `from_json()` validation (firmwareVersion required, firmwarePath + config optional)
  - Handler: validates session is ACTIVE, generates API key, calls `create_kubernetes_job()`, updates session config with trigger metadata, audit logs
  - Simulator: `scripts/simulate-build-trigger.py` — mimics TeamCity: creates validation run, triggers it, optionally polls for completion
  - OpenAPI docs added for trigger endpoint (request body + 200/400/404/500 responses)
  - Files: `src/api/v2/validation/runs/trigger.py`, `tests/api/validation/test_trigger.py`, `tests/unit/types/test_validation_runs_types.py` (appended), `scripts/simulate-build-trigger.py`
- [x] 6E: Comparison dashboard — **side-by-side run comparison at `/validation/runs/compare`**
  - Route: `/validation/runs/compare?a=<run_id>&b=<run_id>`
  - Side-by-side summary cards (total, passed, failed, duration)
  - Test result comparison table with diff highlighting (pass→fail = red, fail→pass = green)
  - Power measurement CSS bar charts (current_ma side-by-side per test)
  - Compare selection on runs list page (checkbox + Compare button)
  - "Compare with..." button on run detail page
  - Uses existing 6A API endpoints — no backend changes needed
  - Files: `src/routes/validation/runs/compare/+page.svelte` (new), `src/routes/validation/runs/+page.svelte` (modified), `src/routes/validation/runs/[id]/+page.svelte` (modified)

> Full proposal: `docs/validation/plans/stage4-proof/phases/phase-6-orchestration-and-visibility.md`
> Does NOT modify any Phase 0-5 code.

### Manufacturing Alpha Migration (V2 → V1) — VERIFIED

Manufacturing alpha app (`apps/manufacturing/alpha/`) was migrated from V2 MTIB client (port 50052, NOT deployed) to V1 MTIB server (port 50053, deployed and working). 20 files modified. Tests run from K8s pods on `concordagent03` with `hostNetwork: true`.

**REV 1.2 (10.4.45.33) — FULLY VERIFIED:**
- fw_flash: 3/3 PASS (nRF52840 flash ~11s, nRF9151 flash ~5.5s, AP protect both)
- POST: 11/11 PASS (lock shells, chip IDs, BMS, charger, GPS, modem FW, IMEI/ICCID, ext flash, personalize via CoreOps, rekey IPC)
- AP protect verified via `nrfjprog --deviceversion` from MTIB container
- CoreOps proxy: `http://10.4.45.30:8001` (old `https://10.4.45.3:443` is dead)
- Container image: `containers.ad.corekinect.com/concord-manufacturing-alpha:latest`
- K8s manifest: `deploy/manufacturing/alpha/deployment.yaml`

**REV 1.1 (10.4.45.32) — fw_flash PASS, POST NEEDS WORK:**
- fw_flash: 3/3 PASS (with `fw_flash_step2_recover=False` config override — REV 1.1 has no J-Link mux)
- POST: step_0 (lock_shell) times out — zero UART bytes after boot. Root cause: needs further investigation (pin-swap firmware + UART timing)

**Key changes:**
- `fw_flash_step2_recover` config flag: `True` (default, REV 1.2 with mux), `False` (REV 1.1 without mux)
- Personalize response parser: handles variable whitespace in key labels
- Dockerfile: fixed paths (was referencing theta_fixture) + PYTHONPATH (added `/libs/protocols`)
- UART timeouts: lock_shell 120s, debug_uart_disable 60s

### Phase 5: FUOTA Flow (Designed, Not Executed)

- [ ] FUOTA flow design reviewed and approved
- [ ] `.cfw` file upload to Azure `cc-smb-fs` storage (confirmed mechanism — no REST API)
- [ ] Direct DB INSERT into `FuotaTbl` with plan/stage JSON (confirmed mechanism — no CRUD API)
- [ ] FUOTA plan stage JSON authored (targets, isSkippable, maxStage per device)
- [ ] Device enablement record created (deviceId, planId, enableUpdates, maxStage)
- [ ] 12-step flow execution (deferred until DB + Azure access available)

---

## Firmware Build Architecture

```
apps/firmware/products/
├── ctl.sh                          # Top-level orchestrator (Docker builds)
├── alpha/
│   ├── project.json                # Nx targets (build:docker, build:all-variants, collect)
│   ├── scripts/build.sh            # Actual build logic (west, cmake, overlay chaining)
│   ├── overlays/                   # Repo-level DTS overlays (4 files, pin swap + default)
│   ├── artifacts/                  # Build output (created by build.sh)
│   ├── alpha_fw/                   # Submodule → ncs-fw-dev:2.7.0
│   └── alpha_mfg_fw/              # Submodule → ncs-fw-dev:2.7.0
└── sigma5/
    ├── project.json
    ├── scripts/build.sh
    ├── artifacts/
    ├── sigma5_fw/                  # Submodule → ncs-fw-dev:2.4.2
    └── sigma5_mfg_fw/             # Submodule → ncs-fw-dev:2.7.0
```

**Build flow:** `ctl.sh build alpha --target mfg --mtib-rev 1.2`
1. Reads `alpha/alpha_mfg_fw/.devcontainer/devcontainer.json` → extracts Docker image
2. `ctl.sh` pre-build: auto-generates encryption keys if missing (`imgtool.py keygen` in Docker)
3. `ctl.sh` pre-build: fixes app sysbuild.conf key path for monorepo mount (`/workspaces/alpha/alpha_mfg_fw/`)
4. `docker run --rm -v ... ncs-fw-dev:2.7.0 bash scripts/build.sh mfg --mtib-rev 1.2`
5. `build.sh` fixes comms sysbuild.conf path, resolves overlays, runs `west build`
6. Artifacts land in `alpha/artifacts/alpha_mfg_fw/alpha_b0/`

**Alpha build matrix** (12 hex files):
| Target | Variant | MTIB Rev | nRF52840 hex | nRF9151 hex |
|--------|---------|----------|-------------|-------------|
| mfg | — | 1.1 | yes | yes |
| mfg | — | 1.2 | yes | yes |
| app | debug | 1.1 | yes | yes |
| app | debug | 1.2 | yes | yes |
| app | release | 1.1 | yes | yes |
| app | release | 1.2 | yes | yes |

**Next step:** `./apps/firmware/products/ctl.sh build-all alpha` (requires Docker image pull from registry)

---

## Blockers

| Blocker | Affects | Status | Resolution |
|---------|---------|--------|-----------|
| ~~CoreCloud VAL_1_0 URL unknown~~ | ~~Stream A (CloudClient)~~ | **Resolved → corrected to DEV_1_0** | Devices personalized against `dev.office.corekinect.cloud`, NOT val. REST: `https://dev.office.corekinect.cloud:2022/api`, Auth: `https://auth.office.corekinect.cloud:2013`. Ports: Session=2022, Data=2023, Time=2024. DB requires SSH tunnel via `dmz-pg02.dmz.corekinect.com`. CloudClient default changed from VAL_1_0 to DEV_1_0. |
| **CoreCloud DB credentials** | **CloudClient (live testing)** | **Open — ask Jarred** | Need `DEV_1_0_DB_USERNAME`, `DEV_1_0_DB_PASSWORD`, `DEV_1_0_DB_DATABASE_NAME`. DB host is `127.0.0.1` via SSH tunnel to `dmz-pg02.dmz.corekinect.com`. Also need SSH creds or key. Template at `libs/python/corekinect/core_cloud/.env.example` (DEV_1_0 section). |
| **CoreCloud API credentials** | **CloudClient REST calls** | **Open — ask Jarred** | Need `DEV_1_0_API_AUTH_USERNAME`, `DEV_1_0_API_AUTH_PASSWORD`, `DEV_1_0_API_KEY`. Same creds as manufacturing. |
| **Docker image pull from registry** | **Firmware builds** | **Open — need registry access** | `ctl.sh build-all alpha` needs `containers.ad.corekinect.com/ncs-fw-dev:2.7.0`. Devcontainer can't reach internal registry. Run from a machine with registry access. |
| ~~M10 deploy~~ | ~~Live hardware testing~~ | **Resolved** | Server with M1-M9 changes deployed. 24/27 RPCs PASS on both boards (V1 + V2). 3 expected fails: MotionStart (disabled), AltimeterRead (BME280 absent), AccelRead (intermittent). Manufacturing 14/14 tests PASS on REV 1.2. |
| ~~Alpha B0 availability~~ | ~~All on-device work~~ | **Resolved** | Two devices sourced from mfg batches: SNR 0964 (batch 7) and SNR 097D (batch 9). See `apps/firmware/products/results.json`. |
| ~~Device personalization~~ | ~~Stage 4 (LTE/CoreCloud)~~ | **Resolved** | REV 1.2 re-personalized (2026-03-02) via manufacturing POST step_9/10 from K8s pod. REV 1.1 still personalized from mfg batch 9. Server: `dev.office.corekinect.cloud`. Automated re-personalization via `DevicePersonalizer` class after each flash. |
| ~~DEVICE_ID unknown~~ | ~~CloudClient, all tests~~ | **Resolved** | SNR 0964 → `70B3D584C01E1FCC`, SNR 097D → `70B3D584C01E20A2`. Both have EC keypairs, activated SIMs (Verizon + Onomondo). |
| `.cfw` file upload to Azure | Phase 5 (FUOTA) | **Mechanism confirmed** | No REST endpoint — upload `.cfw` to Azure `cc-smb-fs` storage, files land at `C:\CoreCloud\CoreCloud.SocketServer\fuota` on cc-winsrv-01/02. Need Azure storage creds or SMB access. |
| FUOTA plan DB records | Phase 5 (FUOTA) | **Mechanism confirmed** | No CRUD API — direct INSERT into `FuotaTbl` + `FuotaListsTbl`. Plan uses Stages JSON with targets, isSkippable, maxStage. Device enablement JSON per device. Need DB write access (DEV_1_0 creds from Jarred). |
| ~~Edge nodes need K8s roles assigned~~ | ~~Infra consistency~~ | **Resolved** | `00-labels-taints.sh` updated + run on live cluster. Both Verdins show `edge` role + `mtib-revision` labels. |
| ~~NCS/Zephyr version mismatch in devcontainer~~ | ~~Firmware builds (Phase 0.5)~~ | **Resolved** | Docker-based builds via `ctl.sh` — each firmware submodule's `.devcontainer` image provides the correct NCS version. See `apps/firmware/products/ctl.sh`. |

---

## Action Items — Ask Tomorrow

These are the things that need human action. Ask about these when people are in:

### Ask Jarred (CoreCloud)
1. **CoreCloud DEV_1_0 credentials** — Devices are personalized against `dev.office.corekinect.cloud` (DEV_1_0 namespace, not VAL_1_0). We need:
   - DB: `DEV_1_0_DB_USERNAME`, `DEV_1_0_DB_PASSWORD`, `DEV_1_0_DB_DATABASE_NAME`
   - SSH tunnel: `DEV_1_0_SSH_USERNAME`, `DEV_1_0_SSH_PASSWORD` (or key path) for `dmz-pg02.dmz.corekinect.com`
   - API: `DEV_1_0_API_AUTH_USERNAME`, `DEV_1_0_API_AUTH_PASSWORD`, `DEV_1_0_API_KEY`
2. **Verify device 70B3D584C01E1FCC is visible in DEV CoreCloud** — This device (SNR 0964) was personalized in mfg batch 7. Confirm we can query its BootMsgV2 / BiometricDataMsg etc.
3. ~~**CoreOps proxy URL**~~ — **RESOLVED**: `http://10.4.45.30:8001` (old `https://10.4.45.3:443` is dead). Verified working from K8s cluster — returns device IDs, accepts key uploads. Updated in `.env.example` and K8s deployment manifest.

### Ask Main Engineer (MTIB)
4. ~~**M10 deploy status**~~ — **RESOLVED**: Server with M1-M9 changes deployed. 24/27 RPCs verified (V1 + V2). Manufacturing 14/14 tests PASS on REV 1.2.
5. **Docker image registry access** — Can he pull `containers.ad.corekinect.com/ncs-fw-dev:2.7.0` and run `ctl.sh build-all alpha` from a machine with registry access? The devcontainer can't reach the internal registry. **Note**: Pre-built firmware hex files exist at `libs/corekinect/test/validation/assets/firmware/` — sufficient for initial Stage 4 runs.

### Hardware / Inventory
6. ~~**Alpha B0 board**~~ — **RESOLVED**: Two devices sourced from manufacturing: SNR 0964 (device_id `70B3D584C01E1FCC`, batch 7) and SNR 097D (device_id `70B3D584C01E20A2`, batch 9). Both have activated SIMs (Verizon + Onomondo). Details in `apps/firmware/products/results.json`.
7. ~~**Device personalization**~~ — **RESOLVED**: Both devices personalized during manufacturing. EC keypairs generated, keys uploaded to CoreOps. Auto re-personalization after each J-Link flash handled by `DevicePersonalizer` class.
8. **Stage 4 fixture parts** — Button relay, charger relay, photodiodes, Peltier, NFC reader, motion scaffold — are any of these ordered?

### Validation Devices (from manufacturing records)

| Field | Device 1 (SNR 0964) | Device 2 (SNR 097D) |
|-------|---------------------|---------------------|
| Device ID | `70B3D584C01E1FCC` | `70B3D584C01E20A2` |
| J-Link SNR | 0964 | 097D |
| IMEI | 355025931735979 | 355025937661526 |
| Verizon ICCID | 89148000009808558441 | 89148000009808567699 |
| Onomondo ICCID | 89457300000037582833 | 89457300000037574012 |
| Mfg Batch | 7 (2026-02-04) | 9 (2026-02-18) |
| FW Version | 0.8 | 0.8 |
| Server | dev.office.corekinect.cloud | dev.office.corekinect.cloud |
| Coproc App ID | 108 | 108 |

### Environment Setup (Validation .env)
The test framework needs these env vars set at runtime. Template below:

```
# MTIB Connection
MTIB_HOST=10.4.45.33
MTIB_PORT=50053
DEVICE_ID=70B3D584C01E1FCC
DEVICE_SNR=0964
DEVICE_IMEI=355025931735979
DEVICE_ICCIDS=89148000009808558441,89457300000037582833
FIXTURE_PROFILE_PATH=libs/python/corekinect/test/validation/fixtures/alpha_b0.json
CORECLOUD_DB_ENV=DEV_1_0

# CoreOps re-personalization (RESOLVED)
PROXY_SERVER_URL=http://10.4.45.30:8001

# CoreCloud DEV_1_0 (ask Jarred for actual values)
DEV_1_0_DB_DRIVER=postgresql+psycopg2
DEV_1_0_DB_USERNAME=<from Jarred>
DEV_1_0_DB_PASSWORD=<from Jarred>
DEV_1_0_DB_HOST=127.0.0.1
DEV_1_0_DB_PORT=5432
DEV_1_0_DB_DATABASE_NAME=<from Jarred>
DEV_1_0_DB_CONNECT_TIMEOUT=5
DEV_1_0_SSH_HOST=dmz-pg02.dmz.corekinect.com
DEV_1_0_SSH_PORT=22
DEV_1_0_SSH_USERNAME=<from Jarred>
DEV_1_0_SSH_PASSWORD=<from Jarred>
DEV_1_0_SSH_REMOTE_HOST=127.0.0.1
DEV_1_0_SSH_REMOTE_PORT=5432
DEV_1_0_API_AUTH_SERVER_HOST_NAME=https://auth.office.corekinect.cloud:2013
DEV_1_0_API_REST_SERVER_HOST_NAME=https://dev.office.corekinect.cloud:2022/api
DEV_1_0_API_AUTH_USERNAME=<from Jarred>
DEV_1_0_API_AUTH_PASSWORD=<from Jarred>
DEV_1_0_API_KEY=<from Jarred>

# Firmware paths (pre-built hex files — must be uploaded to MTIB first)
FW_DEBUG_HEX=libs/corekinect/test/validation/assets/firmware/alpha_debug_nrf52840.hex
FW_RELEASE_HEX=libs/corekinect/test/validation/assets/firmware/alpha_release_nrf52840.hex
```

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-01 | Update V1 server, do not use V2 | V2 is overcomplicated (77 RPCs, 19 handlers); V1 is simple and proven in manufacturing |
| 2026-03-01 | Peripheral-by-peripheral approach for MTIB updates | User works with Claude one handler at a time; independent work units |
| 2026-03-01 | Keep old power RPCs as aliases for manufacturing compat | Avoids breaking manufacturing code; migrate later |
| 2026-03-01 | Separate Stage 4 from Stage 3 | Stage 4 needs zero harness infrastructure; can prove independently |
| 2026-03-01 | Defer FUOTA flow to Phase 5 | Blocked on `.cfw` upload + FUOTA plan API; product tests prove core value first |
| 2026-03-01 | Design TestContext for Stage 3 extensibility | Adding `harness: HarnessTransport` later is a single-field addition |
| 2026-03-01 | 29 charging tests deferred | DUT + CHG share same MTIB power source; no battery sync |
| 2026-03-01 | 7 GNSS tests deferred | Indoor scaffold, no GPS signal source |
| 2026-03-01 | 18 config value tests deferred | GroundModeConfigV2 endpoint unavailable |
| 2026-03-01 | Split validation.yaml into per-revision manifests | REV 1.1 and REV 1.2 need different HARDWARE_VERSION env var; consolidate after Phase 1 auto-detection |
| 2026-03-01 | Add `mtib-revision` node label | Enables nodeAffinity targeting per MTIB hardware revision |
| 2026-03-01 | 2 new Verdin boards for validation | Need dedicated validation nodes separate from manufacturing fleet |
| 2026-03-01 | Alpha B0 already connected on both nodes (mfg fixture config) | TDD from Day 1: power, ADC, UART, SWD, GPIO all available. Fixture wiring reduced 32h → 20h. |
| 2026-03-01 | Bootstrap fixture profile from manufacturing RPCs | `apps/manufacturing/alpha/src/tests/shared/rpcs.py` has proven pin maps, ADC channels, shell commands |
| 2026-03-01 | M1: Keep all 26 existing RPCs in proto, add 8 new V2 RPCs (34 total) | Original plan said "remove 7" but backward compat requires keeping them. Old RPCs become server-side aliases delegating to new handlers. Proto is additive-only. |
| 2026-03-01 | M2-M8: Implement all handler updates in single session | Power unified with channel enum, GPIO watch via gpiod, ADC streaming, J-Link mux + motor power via TCA9534A, GetSnapshot aggregation |
| 2026-03-01 | _read_ina219 returns (err, v, mA, mW) instead of raising | Consistent error-value pattern across all sysfs reads; callers check err before using values. Prevents gRPC INTERNAL errors reaching clients. |
| 2026-03-01 | TCA9534A driver copied from V2 to V1 as src/hardware/tca9534a.py | V1 server needs same I2C GPIO expander driver; simplified version without unused features |
| 2026-03-01 | _set_motor_power and _select_jlink_target return Optional[str] | Error-value pattern for all TCA9534A operations; callers propagate errors as success=False responses |
| 2026-03-01 | nRF9151 also needs per-revision builds (12 assets total, not 9) | Both nRF52840 UART0 (P0.23↔P0.25) and nRF9151 UART0 (P0.21↔P0.22) are swapped on REV 1.1 carrier board. Verified by reading mfg overlay files. |
| 2026-03-01 | Overlays live at repo level (`overlays/`), not in submodules | Submodule repos (alpha_fw, alpha_mfg_fw) must not be modified. Repo-level overlays combine with submodule overlays via `-DDTC_OVERLAY_FILE` semicolon chaining. |
| 2026-03-01 | Docker-based firmware builds via `ctl.sh` | Devcontainer has Zephyr 4.0.0 but firmware needs NCS 2.7.0 (Partition Manager symbols undefined in vanilla Zephyr). Solution: use each submodule's `.devcontainer` Docker image (`ncs-fw-dev:2.7.0` / `ncs-fw-dev:2.4.2`) for builds. `ctl.sh` reads `devcontainer.json` dynamically, runs `scripts/build.sh` inside the correct container. Zero submodule modifications. |
| 2026-03-01 | Production overlay has NO pin swap; mfg overlay DOES | `alpha_fw/boards/alpha_b0_nrf52840.overlay` = I2C sensors only. `alpha_mfg_fw/boards/alpha_b0_nrf52840.overlay` = I2C + pin swap. For prod REV 1.1, pin swap is added via repo-level overlay. For mfg REV 1.2, pin swap is corrected via repo-level overlay. |
| 2026-03-01 | M9: Keep HealthCheck 3-tuple, add HealthCheckExtended | Changing HealthCheck return from `(ready, errors, err)` to 5-tuple would break `connect()` and all manufacturing code. New `HealthCheckExtended` returns full V2 response as dataclass. |
| 2026-03-01 | M9: Client streaming methods yield proto objects directly | PowerStream/GpioWatch/AdcStream yield raw proto response objects (not dataclasses). Callers iterate and consume `.samples`, `.state`, etc. directly. Consistent with existing MotionStart/UartStream patterns. |
| 2026-03-01 | Phase 2A: Sync (not async) for all test framework code | Existing CoreCloud SDK is sync (SQLAlchemy), MTIB client is sync, manufacturing tests are sync. Using async would add complexity (pytest-asyncio, event loops) with no benefit. `time.sleep` polling matches proven manufacturing patterns. |
| 2026-03-01 | Phase 2A: Framework at `libs/python/corekinect/test/validation/` | Under existing `corekinect.test` package. Parent `__init__.py` has broken `mtib_runner` import — validation subpackage works independently when imported with correct PYTHONPATH. Does not modify parent package. |
| 2026-03-01 | Phase 2A: FixtureProfile loaded from JSON, not hardcoded | Fixture pin assignments are TBD pending schematic verification. JSON file (`fixtures/alpha_b0.json`) decouples test logic from wiring. Updated during Stream B (fixture wiring) without code changes. |
| 2026-03-01 | CoreCloud connectivity: REST reachable, DB not from devcontainer | `auth.office.corekinect.cloud:2013` and `val.office.corekinect.cloud:2018` reachable. `validation.ad.corekinect.com:5432` is internal-only — accessible from K8s pods but not devcontainer. Integration testing requires deployment to validation network. |
| 2026-03-01 | Phase 3 test modules written in parallel with M10 deploy | All 8 test modules (62 test functions) written at `tests/stage4/`. Code can't run until M10 + credentials + firmware are ready, but writing tests now means we can do a full E2E run immediately once unblocked. |
| 2026-03-01 | Test modules use sync pattern (no async/await) | Matches Phase 2A framework decision. Tests use `time.sleep` for waits, `ctx.cloud.wait_for_*` for polling. No pytest-asyncio dependency. |
| 2026-03-01 | CoreCloud credentials: same as manufacturing | User confirmed manufacturing app creds work for VAL_1_0. Need to get actual values from Jarred (they're not committed to git — runtime env vars only). |
| 2026-03-01 | NFC test skipped until fixture wired | `test_nfc.py` has 1 test with `@pytest.mark.skip` — NFC I2C reader is Stream B task B6, not yet wired. |
| 2026-03-01 | Infra cleanup: labels script updated + run on live cluster | Removed 5 stale mfg nodes, added both Verdins with mtib-revision labels, added edge K8s role. Script run on cluster — `kubectl get nodes` shows correct labels. |
| 2026-03-01 | Phase 6 proposed: Orchestration, Visibility & CI/CD | Extends Stage 4 with backend API (wire Prisma Session/Execution/Result), pytest reporter plugin (opt-in), frontend validation pages (live Socket.IO progress), Bitbucket pipeline (build → upload → trigger), comparison dashboard. 88h total. Does not modify Phases 0-5. See `phase-6-orchestration-and-visibility.md`. |
| 2026-03-01 | Phase 6: Pipeline-initiated CI (Option B) over webhooks | Lower complexity for Stage 4 proof. Pipeline runs `ctl.sh build-all`, calls Concord API to upload + trigger. No webhook infra. |
| 2026-03-01 | Phase 6: Reporter plugin opt-in via CONCORD_RUN_ID env var | Zero impact on existing pytest flow. Local dev = pure terminal. K8s Job = env var injected. |
| 2026-03-01 | Phase 6: Reuse existing Socket.IO `/kubernetes` namespace | Add `subscribe_validation_run` event alongside existing 6 patterns. One connection per client. |
| 2026-03-01 | Phase 6: Write to existing Prisma schema, no migrations | Session/TestExecution/TestResult/Log already modeled. Just start writing rows. |
| 2026-03-02 | CoreCloud environment corrected: DEV_1_0, not VAL_1_0 | Devices (0964, 097D) personalized against `dev.office.corekinect.cloud`. DEV_1_0 DB requires SSH tunnel via `dmz-pg02.dmz.corekinect.com`. CloudClient default changed to DEV_1_0. Ports: session=2022, data=2023, time=2024. |
| 2026-03-02 | Two validation devices sourced from manufacturing | SNR 0964 → `70B3D584C01E1FCC` (batch 7), SNR 097D → `70B3D584C01E20A2` (batch 9). Both have activated SIMs (Verizon + Onomondo), EC keypairs, FW 0.8. Full records in `apps/firmware/products/results.json`. |
| 2026-03-02 | DevicePersonalizer bridges V1/V2 client gap | Manufacturing uses V2 client (`boot_and_lock_shells`); validation uses V1 client (different proto). `DevicePersonalizer` wraps V1 client's `cmd_comms_coproc_lock_shell`, `alpha_cmd_personalize`, `cmd_comms_coproc_rekey_ipc` + CoreOps API calls into a single `repersonalize()` flow. |
| 2026-03-02 | Auto re-personalization in firmware_build fixture | `conftest.py` firmware_build fixture now calls `DevicePersonalizer.repersonalize()` after each flash. Opt-in via `PROXY_SERVER_URL` + `DEVICE_SNR` env vars. Without them, power cycle only (no re-personalization). |
| 2026-03-02 | FUOTA: no REST API exists, 11 DB ORM tables available | CoreCloud Python SDK has zero FUOTA REST endpoints. C# server endpoints undocumented. DB ORM has full schema (`Fuotaplanstbl`, `Fuotaprogresstbl`, etc.). Phase 5 workaround: direct DB writes via ORM, bypassing server-side validation. |
| 2026-03-02 | Pre-known IMEI/ICCIDs via env vars | `DEVICE_IMEI` and `DEVICE_ICCIDS` env vars skip modem read during re-personalization. Values from manufacturing records are stable (hardware identifiers don't change). |
| 2026-03-02 | MCUboot encryption key fix in `ctl.sh` | Two bugs found: (1) `encryption_key.pem` and `comms_encryption_key.pem` don't exist (in `.gitignore`, must be generated per-developer). (2) App processor `sysbuild.conf` hardcodes `/workspaces/alpha_fw/` paths from standalone dev, but monorepo Docker mounts at `/workspaces/alpha/alpha_fw/`. Fix lives in `ctl.sh` (not submodule's `build.sh`): `_ensure_encryption_keys()` auto-generates via `imgtool.py` inside Docker; `_fix_app_sysbuild_key_path()` fixes app sysbuild.conf path pre-build. Comms path was already handled by `build.sh`'s `fix_sysbuild_key_path()`. Keys are for development/validation — production builds need shared production keys. |
| 2026-03-02 | FUOTA mechanism confirmed from Confluence: DB + Azure, no REST | Searched 10 Confluence pages. FUOTA uses direct DB INSERT into `FuotaTbl` + Azure file upload (`cc-smb-fs`). Server middleware processes FUOTA on every uplink. Plans use Stages JSON (targets, isSkippable, maxStage). No REST API for FUOTA management exists — confirmed by both Python SDK and Confluence docs. Phase 5 workaround: direct DB writes + Azure file upload. Need DB write access + Azure/SMB creds. |
| 2026-03-02 | Firmware versioning spec documented | Binary: AppId(2)+Flags(1)+Major(1)+Minor(1)+Build(2)=7 bytes. Flags: debug[3], track[2:1] (Bench/Eng/Prod), mfg[0]. Artifacts: `.hex` (plaintext, J-Link), `.hex` (encrypted), `.cfw` (encrypted, no bootloader, OTA). Mfg FW shares App ID with production. |
| 2026-03-02 | Device Management REST API found | `/System/Devices/{Register,Search,Update,Set-Account}` — requires privileged API key. Useful for Phase 5 device registration/status queries. |
| 2026-03-02 | Phase 6A: Backend validation run API implemented | 12 endpoints (8 public + 4 reporter callbacks) at `src/api/v2/validation/runs/`. Wires existing Prisma Session/Device/Test/TestExecution/TestResult models. Reporter callbacks auto-create Test definitions on first call (no pre-seeding). Artifacts served from MinIO `validation/artifacts` prefix. Permissions: `Concord.Admin.Validation.{View,Manage}`. 354 total tests pass (21 new type tests + 14 new integration tests + 319 existing). |
| 2026-03-02 | Phase 6A: Reporter auto-creates Test definitions | Reporter `test-start` callback creates Test records on-the-fly if they don't exist for the product. This means no manual test seeding is needed — first pytest run populates the test catalog. |
| 2026-03-02 | Phase 6A: `update_many` not in MockModelClient | Test conftest `MockModelClient` has `create_many` and `delete_many` but not `update_many`. Cancel endpoint test needs explicit `MagicMock()` for it. Not worth modifying conftest for one use. |
| 2026-03-02 | CoreCloud complete reference doc written | 18+ Confluence pages distilled into `corecloud-complete-reference.md`. Covers: system architecture (4 server components), auth flow (API key + JWT), device lifecycle (registration → personalization → production), firmware versioning (7-byte binary format, App IDs), FUOTA mechanism (DB + Azure, no REST), Socket Server protocol (AES-256 + HMAC-SHA-256), CoreOps manufacturing pipeline, IPC personalization commands, full REST API reference, environment map. Single source of truth — no need to search Confluence again. |
| 2026-03-02 | CoreCloud integration test suite written | 22 tests in 7 groups at `test_corecloud_integration.py`. Tests auth connectivity, DB queries, device registration/identity, message history, FUOTA table access (Phase 5 prerequisite), full re-personalization flow, and webhook management. Run as: `pytest test_corecloud_integration.py -v -m corecloud`. |
| 2026-03-02 | Alpha B0 CoreCloud identifiers confirmed | App IDs: 108 (nRF9151 comms), 109 (nRF52840 app). CoreCloud: DeviceType=2, Variant=3. From Confluence App ID table (page 1855127553). |
| 2026-03-02 | Phase 6B: Reporter tests in backend suite, not validation package | Reporter tests can't live under `corekinect/test/validation/tests/` because the parent `__init__.py` has a broken `mtib_runner` import chain. Tests moved to `apps/backend/http-api/tests/lib/test_reporter.py` and use `importlib.util.spec_from_file_location` to load the reporter module directly, bypassing the package chain. 13 tests pass. |
| 2026-03-02 | Phase 6B: Reporter uses `@hookimpl(hookwrapper=True)` for test results | `pytest_runtest_makereport` needs hookwrapper to intercept the TestReport for each test phase. Only reports on `when="call"` phase (not setup/teardown). Extracts error message, power measurements, and duration for each test. |
| 2026-03-02 | Phase 6C: Validation permissions + OpenAPI convention compliance | Added `Concord.Admin.Validation.View` and `Manage` to `prisma/seed.py` (ALL_PERMISSIONS + ADMIN_PERMISSIONS). Added 4 schemas (ValidationRun, ValidationDevice, ValidationExecution, ValidationResult) + 12 endpoint paths to `src/api/v2/docs.py`. OpenAPI spec builds: 102 paths, 34 schemas. 367 tests pass. |
| 2026-03-02 | Phase 6D: CI is TeamCity, not Bitbucket Pipelines | Build server is TeamCity. Pipeline config lives in TeamCity UI, not in repo YAML. No `bitbucket-pipelines.yml` needed. |
| 2026-03-02 | Phase 6D: Build-server artifact format confirmed from real theta builds | Real TeamCity output at `build-server/0.1.11/` and `0.1.12/`: `<version>/debug/{app,comm_coproc_mfg}/` with `.hex` + `.hex.sha1` + `signed.encrypted/` variants, plus `.cfw` FUOTA package and `commit.log`. Alpha and theta are identical boards — same artifact structure, different product prefix. |
| 2026-03-02 | Phase 6D+6E: Neither is externally blocked | 6D needs a `trigger` endpoint + simulator script (pure code, no infra). 6E is pure frontend (existing API provides all data). Both can be built now. |
| 2026-03-02 | Phase 6D: Trigger reuses `create_kubernetes_job()` from validation/tests/run.py | Avoids duplicating K8s Job creation logic. Import path: `src.api.v2.validation.tests.run`. Handler generates per-run API key (`secrets.token_urlsafe`), injects `CONCORD_RUN_ID` + `CONCORD_API_URL` + `CONCORD_API_KEY` into session config. |
| 2026-03-02 | Phase 6D: Mock paths use `api.v2.` prefix, not `src.api.v2.` | Conftest imports router as `api.v2.router` (PYTHONPATH includes `src`), so all modules load under `api.v2.*` namespace. Using `src.api.v2.*` in `@patch()` creates a separate module object in `sys.modules` — mock doesn't intercept the real call. |
| 2026-03-02 | Phase 6D: Simulator is standalone `requests`-based script | `scripts/simulate-build-trigger.py` mimics TeamCity flow: create run → trigger → optional poll. Uses `requests` (already in requirements). No new dependencies. |
| 2026-03-02 | Phase 6E: Comparison dashboard is pure frontend, CSS bar charts | No charting library — uses styled `<div>` bars for power measurement comparison, consistent with existing design patterns. Page reads from existing 6A API endpoints. |
| 2026-03-02 | Manufacturing alpha migrated V2 → V1 | fw_flash and POST tests rewritten from V2 MTIB client (port 50052, not deployed) to V1 server (port 50053, deployed). `ThetaMtibServers` singleton wraps all V1 gRPC calls. 20 files modified. REV 1.2: 14/14 PASS. REV 1.1: fw_flash 3/3 PASS, POST pending. |
| 2026-03-02 | CoreOps proxy URL corrected | Old: `https://10.4.45.3:443` (dead). New: `http://10.4.45.30:8001` (working). Discovered from sigma5 deployment configs. Verified from K8s cluster. Updated in `.env.example`, Dockerfile, K8s manifest. |
| 2026-03-02 | REV 1.1 J-Link mux workaround | REV 1.1 has no J-Link mux — both probes always visible. `_assign_jlinks(force_recovery=True)` chip-erases ALL connected devices. Fix: `fw_flash_step2_recover` config flag — `True` for REV 1.2 (mux isolates probes), `False` for REV 1.1 (skip recovery on step 2, step 1 recovery covers both). |
| 2026-03-02 | Manufacturing alpha containerized and deployed | Dockerfile fixed (was referencing theta_fixture), PYTHONPATH fixed (added `/libs/protocols`). Image: `containers.ad.corekinect.com/concord-manufacturing-alpha:latest`. K8s manifest at `deploy/manufacturing/alpha/deployment.yaml`. Runs on `concordagent01` with hostNetwork for CoreOps access. |
| 2026-03-02 | Personalize response parser hardened | Firmware outputs `Public key (hex)   :` with variable whitespace. Parser changed from exact `response.find()` to line-by-line matching with `"Public key (hex)" in stripped`. Pattern changed from `"Personalization complete"` to `"Public key (base64)"`. |
| 2026-03-03 | M10 confirmed deployed | V2 RPCs (PowerMeasure, PowerStream, GpioWatch, AdcStream, etc.) all verified working on both boards. 24/27 RPCs PASS. M10 is effectively complete — both V1 and V2 client methods work against the deployed server. |
| 2026-03-03 | GPIO 0+1 config added to FixtureController + DevicePersonalizer | `power_on()` and `_power_cycle()` now configure GPIO 0+1 as output LOW before enabling power. Critical for Alpha B0 — without this, DUT draws 0mA at 4.5V (SWD level shifter disabled). Extracted into `_configure_swd_gpios()` helper in FixtureController. |
| 2026-03-03 | PROXY_SERVER_URL updated in all validation code | Changed from dead `https://10.4.45.3:443` to working `http://10.4.45.30:8001` in conftest.py, device_personalizer.py, status.md env template. Manufacturing code already updated in prior session. |
| 2026-03-03 | Pre-built firmware hex files available | All 6 variants (mfg/debug/release × nRF52840/nRF9151) pre-built and collected at `libs/corekinect/test/validation/assets/firmware/` with SHA256 manifest. No need to run `ctl.sh build-all` for initial Stage 4 testing. |
| 2026-03-03 | Phase 6: 381 backend tests passing, trigger button added | Other engineer completed: Trigger Run button on detail page (inline form, firmware version, gated on ACTIVE + Manage permission), Notes section on detail page, 381 total backend tests passing. Phase 6A-6E fully complete. |
| 2026-03-03 | Validation tests stay in library for now, move to `apps/validation/alpha/` when second product arrives | Tests at `libs/python/corekinect/test/validation/tests/stage4/` are Alpha-specific but framework is reusable. Refactoring to `apps/validation/alpha/` when Sigma5 validation added is a file-move + import fix — no logic changes. |
| 2026-03-03 | Recommend merging Jarred's `feature/test-automation` branch | Zero conflicts with Stage 4 work. Adds MessageBase (Active Record DB queries), ConfigMessageBase (REST API push), MessageCodec (binary packing), GroundModeConfigV2 (unblocks 18 deferred config tests), discharge_windows.py, event_time_pairs.py. All additions to Layer 2 (CoreCloud SDK). |
| 2026-03-03 | Validation architecture documented | Three-pattern codebase (manufacturing gRPC, sigma5 CLI, Stage 4 pytest). Four-layer dependency chain (MTIB client → CoreCloud SDK → Validation framework → Product tests). Requirements traceability via naming + docstrings, not DB model. See Architecture section below. |
| 2026-03-03 | Alpha B0 requires DUAL-RAIL power for cold boot | BQ25180 charger IC requires both ch0 (battery 4.5V) and ch1 (charger 5.0V) to enable system rail. Without ch1, ch0 shows 4.5V but 0mA — DUT does not boot. After ~4s charger takes over: ch0 drops to ~0mA, ch1 draws 17-33mA. Must check total current (ch0+ch1) for reliable "DUT alive" verification. FixtureController.power_on() updated to enable both rails by default. Smoke test uses read_total_current() with 5mA threshold. `.claude/rules/mtib-hardware.md` updated with full boot power timeline and corrected common mistakes. |
| 2026-03-03 | MTIB smoke test 13/13 PASS on both boards | TestMtibConnection (2), TestGpio (2), TestPower (5), TestAdc (2), TestSnapshot (1), TestCleanup (1). REV 1.1: 23mA total (firmware present). REV 1.2: 8mA total (firmware wiped, BQ25180 quiescent). Both boards pass same test suite — threshold at 5mA total accommodates both states. |
| 2026-03-03 | PowerProfiler + FixtureController attribute fixes verified live | PowerMeasureResult: `average_ma`/`max_ma`/`min_ma`/`average_mv`/`duration_s`/`sample_count` (not `avg_current_ma`/`peak_current_ma`). PowerReadResult: `voltage_v`/`current_ma`/`power_mw`/`enabled` (not `voltage_mv`). Both classes confirmed working against live MTIB hardware on both boards. |
| 2026-03-03 | 112 tests collected via pytest --collect-only | 99 Stage 4 tests (parametrized debug+release across 8 modules) + 13 smoke tests = 112 total. 9 test modules discovered. All imports resolve cleanly with PYTHONPATH=libs/python:libs:libs/protocols. |

---

## Validation Architecture

### How the Pieces Fit Together

```
┌───────────────────────────────────────────────────────────────────────┐
│  LAYER 4: PRODUCT TEST CASES                                         │
│  libs/python/corekinect/test/validation/tests/stage4/                │
│  ├── test_boot.py, test_motion.py, test_power.py, ...               │
│  └── 62 test functions, 8 modules, Alpha B0 specific                │
│  Future: apps/validation/alpha/tests/stage4/ (when multi-product)    │
├───────────────────────────────────────────────────────────────────────┤
│  LAYER 3: VALIDATION FRAMEWORK (product-agnostic)                    │
│  libs/python/corekinect/test/validation/                             │
│  ├── TestContext (session-scoped, connects once)                     │
│  ├── FixtureController (GPIO/ADC/motion/power via MTIB)             │
│  ├── CloudClient (CoreCloud DB polling: wait_for_boot, etc.)        │
│  ├── PowerProfiler (PowerMeasure + PowerStream wrappers)            │
│  ├── UartDemuxer (background UART capture + log buffer)             │
│  ├── DevicePersonalizer (post-flash re-personalization)             │
│  ├── ConcordReporter (pytest plugin → Concord API, opt-in)         │
│  └── conftest.py (ctx fixture, firmware_build parametrization)      │
├───────────────────────────────────────────────────────────────────────┤
│  LAYER 2: CORECLOUD SDK (DB + REST + messages)                       │
│  libs/python/corekinect/core_cloud/                                  │
│  ├── CoreCloudDBInterface (SQLAlchemy, SSH tunnel to PostgreSQL)     │
│  ├── CoreCloudRestInterface (JWT auth, device management REST)       │
│  ├── messages/ (BootMsgV2, PositionMsgV6, BiometricDataMsg, ...)    │
│  ├── unified_core/message_base.py (Jarred: Active Record queries)   │
│  ├── unified_core/conf_message_base.py (Jarred: REST config push)   │
│  └── unified_core/message_codec.py (Jarred: binary pack/unpack)     │
├───────────────────────────────────────────────────────────────────────┤
│  LAYER 1: MTIB CLIENT (hardware control)                             │
│  libs/python/corekinect/mtib_client/v1/                              │
│  ├── MtibV1Client (gRPC, 34 RPCs)                                   │
│  ├── Power, GPIO, ADC, UART, Flash, Motion, Sensors, Snapshot       │
│  └── Shell commands: lock_shell, personalize, rekey_ipc, etc.       │
├───────────────────────────────────────────────────────────────────────┤
│  HARDWARE                                                             │
│  ├── MTIB V1 gRPC Server (K3s pod, port 50053)                      │
│  ├── Alpha B0 DUT (nRF52840 + nRF9151, 48-pin connector)           │
│  └── CoreCloud (dev.office.corekinect.cloud, PostgreSQL)            │
└───────────────────────────────────────────────────────────────────────┘
```

### Three Execution Patterns

| Pattern | Manufacturing | Sigma5 Validation | Stage 4 Validation |
|---------|--------------|-------------------|-------------------|
| **Location** | `apps/manufacturing/alpha/` | `apps/validation/sigma5/` | `libs/python/corekinect/test/validation/` |
| **Execution** | gRPC cluster, operator-driven | Standalone CLI, `run_X_test()` | pytest, engineer-triggered |
| **Multi-node** | Yes (ThreadPoolExecutor) | No (single MTIB) | No (single MTIB) |
| **Hardware API** | Raw proto stubs (`ThetaMtibServers`) | `MtibV1Client` | `MtibV1Client` via `FixtureController` |
| **CoreCloud** | CoreOps proxy only | None | `CloudClient` (DB polling) + REST |
| **Results** | gRPC streaming to operator UI | Return `Optional[str]` error | ConcordReporter → Concord API |
| **Test structure** | Test/TestStep classes, handler functions | `_init → _run → _deinit` functions | pytest fixtures + test methods |

### Requirements Traceability

```
Jira PRDTST-xxx (89 Alpha B0 test cases)
    │
    ├── docs/validation/reference/alpha-prdtst-reference.md
    │   (extracted reference, 35 active / 54 deferred)
    │
    ├── tests/stage4/test_<category>.py
    │   (test functions with descriptive names + docstrings)
    │   e.g., test_shake_triggers_motion → PRDTST-326
    │
    └── Concord API (via ConcordReporter)
        └── Session → TestExecution → TestResult
            (no explicit Requirement model — traceability is naming-based)
```

**Gap:** No machine-queryable requirement-to-test mapping. Traceability is human-readable via test names and docstrings. Adding a `Requirement` Prisma model + linking to TestResult would enable "which requirements passed?" queries in the Concord UI. This is a Phase 6+ enhancement, not a blocker.

### Where Product-Specific Tests Live (Current vs Future)

**Current (Alpha-only):**
```
libs/python/corekinect/test/validation/
├── [framework modules]          ← reusable across products
├── conftest.py                  ← Alpha-specific setup
├── fixtures/alpha_b0.json       ← Alpha-specific pin map
└── tests/stage4/test_*.py       ← Alpha-specific tests
```

**Future (multi-product):**
```
libs/python/corekinect/test/validation/     ← framework only
├── cloud_client.py, fixture_controller.py, ...

apps/validation/alpha/                       ← Alpha product app
├── conftest.py (imports framework, Alpha config)
├── fixtures/alpha_b0.json
├── tests/stage4/test_boot.py, test_motion.py, ...
└── .env.example

apps/validation/sigma5/                      ← Sigma5 product app
├── conftest.py (imports framework, Sigma5 config)
├── fixtures/sigma5.json
├── tests/stage4/test_boot.py, test_power.py, ...
└── .env.example
```

**Refactor cost:** Move 8 test files + conftest.py + fixtures/ → `apps/validation/alpha/`. Update imports. No logic changes. Do this when Sigma5 gets Stage 4 tests.

### Jarred's `feature/test-automation` Branch

**Assessment:** Fills Layer 2 gaps. Zero conflicts with Stage 4 framework. Recommend merge to main.

| Module | Layer | What It Adds | Stage 4 Impact |
|--------|-------|-------------|----------------|
| `MessageBase` | 2 | `.last()`, `.since_server_time()`, `.since_device_time()` | Already used by CloudClient internally |
| `ConfigMessageBase` | 2 | `.send_via_api()`, `.to_api_payload()` | Unblocks deferred config PRDTST tests (18) |
| `GroundModeConfigV2` | 2 | Ground mode config read/write/pack | Specifically unblocks 18 config PRDTST tests |
| `MessageCodec` | 2 | Binary packing for OTA payloads | Phase 5 (FUOTA) |
| `discharge_windows.py` | utility | Battery discharge interval detection | Deferred charging tests (29) |
| `event_time_pairs.py` | utility | Generic event interval extraction | Motion window + heartbeat interval tests |
| `DataStorageObject` | utility | JSON/CSV serialization base class | Test artifact persistence |
| `PositionMsgV6` refactor | 2 | Adds MessageBase + MessageCodec mixins | Active — CloudClient uses PositionMsgV6 |

### Development Cycle

```
1. Pick requirement        Jira PRDTST-xxx or alpha-prdtst-reference.md
                           ↓
2. Write test              tests/stage4/test_<category>.py
                           def test_<descriptive_name>(self, ctx, firmware_build):
                           ↓
3. Run locally             MTIB_HOST=10.4.45.33 DEVICE_ID=70B3D584C01E1FCC \
                           pytest tests/stage4/test_boot.py -v
                           ↓
4. Test executes           conftest creates TestContext (MTIB + CloudClient)
                           firmware_build fixture: flash → re-personalize → boot
                           Test: ctx.fixture.* (stimulus) → ctx.cloud.* (verify)
                           _test_lifecycle: UART capture + teardown
                           ↓
5. Results to Concord      CONCORD_RUN_ID=xxx pytest tests/stage4/ -v
   (opt-in)                Reporter → POST /v2/validation/runs/<id>/report/*
                           ↓
6. Concord UI              Pass/fail per test, per firmware variant
                           Power measurements, UART artifacts
                           Debug vs release comparison dashboard
```

**Full E2E run:**
```bash
# 112 tests collected (99 parametrized + 13 smoke)
pytest tests/stage4/ \
  --device-id=70B3D584C01E1FCC \
  --mtib-host=10.4.45.33 \
  --db-env=DEV_1_0
```

The `firmware_build` fixture parametrizes on `["debug", "release"]`, so every test runs twice automatically.
