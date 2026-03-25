# Bill of Materials: Concord Validation Pipeline

> Complete inventory of every component that must be built, updated, or procured
> to deliver the 4-stage firmware validation system for CoreKinect Alpha.
>
> Generated: 2026-02-25
> Scope: Stages 1-4, all repositories, all infrastructure, all hardware
> Source documents: 00, 09, arch-stage1, arch-stage2, arch-stage3, alpha-prdtst-reference, cohesion-review
>
> **Companion**: [bom-system-implementation.md](bom-system-implementation.md) —
> system-level view organized by interface agreements, covering all domains
> (validation, manufacturing, FUOTA) collectively.

---

## 1. Overview

### 1.1 Purpose

This document is a complete, actionable inventory of every deliverable required
to bring the Concord validation pipeline from its current state (zero automated
firmware validation) to full 4-stage operation. It covers firmware components,
infrastructure services, hardware fixtures, and documentation -- everything an
engineering team needs to plan sprints and track progress.

### 1.2 How to Read the Tables

**Status Legend:**

| Status   | Meaning |
|----------|---------|
| `NEW`    | Does not exist. Must be created from scratch. |
| `UPDATE` | Exists in some form. Requires modification or restructuring. |
| `EXISTS` | Already present and functional. No changes needed (or minimal config). |
| `PROCURE`| Physical hardware that must be purchased or fabricated. |

**Effort Estimation Methodology:**

- Hours are engineering hours, not calendar time.
- Estimates derived from arch-stage1 Section 7 (116h detailed breakdown),
  arch-stage2 Section 8 (~160-200h estimated from 25+ work items),
  arch-stage3 Section 8 (~120-160h estimated from 5 phases),
  and cohesion-review Section 4.4 summary.
- Stage 4 estimates are new to this document, extrapolated from Stage 3
  complexity and the 89-test PRDTST suite scope.
- Infrastructure estimates include both coding and integration testing.
- "Blocks" = what cannot start until this item is done.
- "Blocked By" = what must be done before this item can start.

### 1.3 Repository Map

| Repo | Location (current) | Purpose |
|------|-------------------|---------|
| `accel_drv` | `/home/mateo/work/firmware/alpha_fw/accel_drv/` (submodule, legacy branch) | Driver repo -- clean nuke branch for LSM6DSO |
| `lsm6dso_drv` | `/home/mateo/work/firmware/alpha_fw/lsm6dso_drv/` (submodule) | Current LSM6DSO driver -- code reference only |
| `alpha_fw` | `/home/mateo/work/firmware/alpha_fw/` | Alpha firmware repo |
| `ck_boards` | `/home/mateo/work/firmware/alpha_fw/ck_boards/` (submodule) | Board definitions (Alpha, Sigma5, Theta, dev-kits) |
| Concord monorepo | `/home/mateo/work/concord/concord/` | Pipeline infra, HTTP API, frontend, MTIB libs, deploy |
| `concord_harness` | Does not exist | New Zephyr module for Stage 3 instrumentation |
| CoreCloud client | `/home/mateo/work/concord/concord/libs/python/corekinect/core_cloud/` | REST + DB interface to CoreKinect backend |
| MTIB client v2 | `/home/mateo/work/concord/concord/libs/python/corekinect/mtib_client/v2/` | gRPC wrapper for MTIB V2 RPCs |

### 1.4 POC Scope

This BOM represents the full pipeline. The **proof of concept** excludes items that
are blocked on missing CoreCloud infrastructure:

- **Deferred (I24a-c):** `GroundModeConfigV2` and `BiometricConfig` Python SDK classes
  and their corresponding REST endpoints. These don't exist in the CoreCloud C# server
  or the Python SDK (`msg_def_v1_0.py`) today. Blocked on a decision from the CoreCloud
  team (REST endpoint vs Socket Server downlink for UID 538/558 config delivery).
- **Impact:** 18 of 89 PRDTST Config Value tests are deferred. The POC covers
  **71 tests** using existing CoreCloud infrastructure (uplink message verification
  via `PositionMsgV6`, `BiometricDataMsg`, `BootMsgV2` + GPS config delivery via
  `GPSConfMsg.send_via_rest()`).
- Items marked **DEFERRED** in the tables below are not included in the POC effort
  totals.

---

## 2. Firmware Components

### 2.1 `accel_drv` Repository (Clean Nuke Branch)

The existing `accel_drv` repo at `/home/mateo/work/firmware/alpha_fw/accel_drv/`
contains legacy code: `unit_testing/` (Unity-based), `test/`, `zephyr/module.yml`
(outdated). The new branch nukes everything and implements the architecture from
arch-stage1 Section 2.1.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| F01 | Clean branch creation | `accel_drv/` (new branch) | NEW | 1, 2 | FW | 2 | F02-F14 | -- |
| F02 | Root `Kconfig` | `accel_drv/Kconfig` | NEW | 1, 2 | FW | 1 | F03, F06, F09 | F01 |
| F03 | Root `CMakeLists.txt` | `accel_drv/CMakeLists.txt` | NEW | 1, 2 | FW | 1 | F06, F09 | F01 |
| F04 | `zephyr/module.yml` | `accel_drv/zephyr/module.yml` | UPDATE | 1, 2 | FW | 0.5 | F06, F09, F10 | F01 |
| F05 | LSM6DSO driver implementation | `accel_drv/drivers/lsm6dso/src/lsm6dso.c`, `.h`, `lsm6dso_reg.h`, `lsm6dso_reg.c` | NEW | 2 | FW | 40 | F09, F10 | F01 |
| F06 | LSM6DSO driver Kconfig | `accel_drv/drivers/lsm6dso/Kconfig` | NEW | 1, 2 | FW | 1 | F05, F09 | F02 |
| F07 | DTS binding `ck,lsm6dso.yaml` | `accel_drv/dts/bindings/ck,lsm6dso.yaml` | NEW | 2 | FW | 3 | F05, F10 | F01 |
| F08 | DTS stub binding `ck,lsm6dso-stub.yaml` | `accel_drv/dts/bindings/ck,lsm6dso-stub.yaml` | NEW | 1 | FW | 1 | F09 | F01 |
| F09 | Stub driver `lsm6dso_stub.c` + `lsm6dso_stub.h` | `accel_drv/stubs/lsm6dso_stub.c`, `lsm6dso_stub.h` | NEW | 1 | FW | 6 | F10, F18 | F02, F03, F08 |
| F10 | Stub `Kconfig` + `CMakeLists.txt` | `accel_drv/stubs/Kconfig`, `stubs/CMakeLists.txt` | NEW | 1 | FW | 1 | F09 | F02, F03 |
| F11 | Interface contract tests | `accel_drv/tests/interface/src/main.c`, `testcase.yaml`, `boards/native_sim.overlay`, `prj.conf` | NEW | 1 | FW | 12 | I01 | F09, F10 |
| F12 | HW test firmware (Stage 2) | `accel_drv/tests/lsm6dso/src/main.c`, `test_helpers.h`, `testcase.yaml`, `prj.conf`, `CMakeLists.txt` | NEW | 2 | FW | 16 | I06 | F05, F07 |
| F13 | `test_spec.yaml` | `accel_drv/tests/lsm6dso/test_spec.yaml` | NEW | 2 | FW | 4 | I06 | F12 |
| F14 | `.concord/pipeline.yaml` | `accel_drv/.concord/pipeline.yaml` | NEW | 1, 2 | FW/Infra | 4 | I01, I04 | F01 |
| F15 | `.concord/build.yaml` | `accel_drv/.concord/build.yaml` | NEW | 1, 2 | FW/Infra | 3 | I01, I04 | F01 |
| F16 | `board_features.py` extraction script | `accel_drv/scripts/extract_board_features.py` | NEW | 2 | Infra | 4 | I06 | F12 |

**Subtotal: ~99.5h** (includes 40h for the driver itself, which is the dominant firmware effort)

**Note on F05:** The 40h estimate covers writing the LSM6DSO driver from scratch.
The existing driver at `lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/` (legacy
path in the current codebase) is a reference only. The target architecture uses a
flat path (`drivers/lsm6dso/src/`, not nested `drivers/corekinect/sensors/`), as
defined in arch-stage1 Section 2.1.

### 2.2 `alpha_fw` Repository Updates

The Alpha firmware at `/home/mateo/work/firmware/alpha_fw/` currently has no
test infrastructure, no `.concord/` directory, no harness support, and no `tests/`
directory.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| F17 | `#ifdef CONFIG_ZTEST` getter in `alpha_state_machine.c` | `alpha_fw/src/app/alpha_state_machine.c` | UPDATE | 1, 3 | FW | 2 | F18, F22 | -- |
| F18 | `#ifdef CONFIG_ZTEST` getter in `motion_state_machine.c` | `alpha_fw/src/app/motion_state_machine.c` | UPDATE | 1, 3 | FW | 1 | F19 | -- |
| F19 | Move `alpha_state_t` / `motion_state_t` to public headers | `alpha_fw/src/app/alpha_state_machine.h`, `motion_state_machine.h` | UPDATE | 1, 3 | FW | 2 | F17, F18, F22 | -- |
| F20 | App-level stub tests | `alpha_fw/tests/app/src/main.c`, `stubs.c`, `test_alpha_state_machine.c`, `test_motion_state_machine.c` | NEW | 1 | FW | 20 | I01 | F09, F17, F18, F19 |
| F21 | App test build files | `alpha_fw/tests/app/testcase.yaml`, `prj.conf`, `CMakeLists.txt`, `boards/native_sim.overlay` | NEW | 1 | FW | 4 | I01 | F09, F08 |
| F22 | `src/concord_harness.c` (harness declarations) | `alpha_fw/src/concord_harness.c` | NEW | 3 | FW/Infra | 16 | I11 | F28, F19 |
| F23 | `#ifdef CONFIG_CONCORD_HARNESS` guards | `alpha_fw/src/app/app.c` (UART0 RX kill), others | UPDATE | 3 | FW | 4 | F22 | F28 |
| F24 | `CONCORD_EMIT()` calls in state machines | `alpha_fw/src/app/alpha_state_machine.c`, `motion_state_machine.c` | UPDATE | 3 | FW | 3 | F22 | F28, F23 |
| F25 | Submodule pointer update for `accel_drv` | `alpha_fw/.gitmodules` | UPDATE | 1, 2 | FW | 0.5 | F20 | F01 |
| F26 | `.concord/pipeline.yaml` (Alpha product pipeline) | `alpha_fw/.concord/pipeline.yaml` | NEW | 1, 3, 4 | Infra | 4 | I01 | -- |
| F27 | `.concord/build.yaml` (Alpha builds) | `alpha_fw/.concord/build.yaml` | NEW | 1, 3, 4 | Infra | 3 | I01 | -- |
| F28a | `.concord/integration_spec.yaml` | `alpha_fw/.concord/integration_spec.yaml` | NEW | 3 | FW/Infra | 4 | I11 | -- |
| F28b | Integration test Python modules | `alpha_fw/.concord/tests/integration/test_vsm.py`, `test_state_machine.py`, etc. | NEW | 3 | FW/Infra | 24 | I11 | F22, I10, I12 |

**Subtotal: ~87.5h**

### 2.3 `concord_harness` Zephyr Module

This module does not exist anywhere in the codebase. It is entirely new.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| F28 | `concord_harness.h` (public API, macros) | `concord_harness/zephyr/include/concord_harness/concord_harness.h` | NEW | 3 | Infra | 8 | F22, F29-F34 | -- |
| F29 | `concord_harness_types.h` (registration structs) | `concord_harness/zephyr/include/concord_harness/concord_harness_types.h` | NEW | 3 | Infra | 2 | F30-F33 | F28 |
| F30 | `concord_shell.c` (shell command handlers) | `concord_harness/zephyr/src/concord_shell.c` | NEW | 3 | Infra | 8 | F22, I10 | F28, F29 |
| F31 | `concord_registry.c` (STRUCT_SECTION lookup) | `concord_harness/zephyr/src/concord_registry.c` | NEW | 3 | Infra | 4 | F30 | F28, F29 |
| F32 | `concord_emit.c` (event emission, k_msgq) | `concord_harness/zephyr/src/concord_emit.c` | NEW | 3 | Infra | 4 | F24, I10 | F28 |
| F33 | `concord_log_backend.c` (optional log backend) | `concord_harness/zephyr/src/concord_log_backend.c` | NEW | 3 | Infra | 4 | -- | F28 |
| F34 | `Kconfig` | `concord_harness/zephyr/Kconfig` | NEW | 3 | Infra | 2 | F30-F33 | -- |
| F35 | `CMakeLists.txt` | `concord_harness/zephyr/CMakeLists.txt` | NEW | 3 | Infra | 1 | F30-F33 | -- |
| F36 | `zephyr/module.yml` | `concord_harness/zephyr/module.yml` | NEW | 3 | Infra | 0.5 | F22 | -- |
| F37 | Unit tests for harness module | `concord_harness/tests/` | NEW | 3 | Infra | 8 | -- | F28-F32 |

**Subtotal: ~41.5h**

### 2.4 `ck_boards` Board Definitions

Board definitions at `/home/mateo/work/firmware/alpha_fw/ck_boards/current/boards/corekinect/`.
Alpha B0 exists (`alpha_b0/`). No dev-kit boards exist.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| F38 | Dev-kit board: `devkit_nrf52840_lsm6dso_spi` | `ck_boards/current/boards/corekinect/devkit_nrf52840_lsm6dso_spi/` | NEW | 2 | FW | 8 | F12, I06 | F07 |
| F39 | Dev-kit board DTS (`nrf52840.dts`, pinctrl, defconfig) | Inside F38 | NEW | 2 | FW | (incl. in F38) | F12 | F07 |
| F40 | Dev-kit `board.yml` | Inside F38 | NEW | 2 | FW | (incl. in F38) | F12 | -- |
| F41 | Alpha B0 harness overlay (if needed) | `ck_boards/.../alpha_b0/` overlays | UPDATE | 3 | FW | 2 | F22 | F28 |

**Subtotal: ~10h**

---

## 3. Concord Infrastructure Components

### 3.1 Pipeline Controller & Orchestration

The Concord monorepo at `/home/mateo/work/concord/concord/` has an existing
HTTP API (`apps/backend/http-api/`) with Flask, Prisma ORM, K8s client, and
a validation config service (`services/validation/config.py`). The pipeline
controller, build service, and stage gating logic do not exist.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I01 | Pipeline trigger API (`POST /v2/validation/pipelines/trigger`) | `concord/apps/backend/http-api/src/` | NEW | 1, 2, 3, 4 | Infra | 12 | I02, I04 | I03 |
| I02 | Pipeline controller (K8s Job watcher) | `concord/apps/backend/pipeline-controller/` | NEW | 1, 2, 3, 4 | Infra | 40 | All stages | I01, I03 |
| I03 | Prisma schema: ValidationPipeline, PipelineStage, PipelineJob, SubmoduleMapping | `concord/prisma/schema.prisma` | UPDATE | 1, 2, 3, 4 | Infra | 8 | I01, I02 | -- |
| I04 | Build service (gRPC, long-running Deployment) | `concord/apps/backend/build-service/` | NEW | 1, 2, 3, 4 | Infra | 32 | F11, F12, F20 | -- |
| I05 | Bitbucket commit status reporting | Inside I02 | NEW | 1, 2, 3, 4 | Infra | 4 | -- | I02 |
| I06 | Stage gating logic (Stage N pass -> Stage N+1 Jobs) | Inside I02 | NEW | 2, 3, 4 | Infra | 8 | I07, I11 | I02 |
| I07 | MTIB node capability matching / job scheduling | Inside I02 | NEW | 2, 3, 4 | Infra | 8 | I08, I11 | I02, H09, H10 |
| I08 | SubmoduleMapping sync (`pipeline.yaml` targets -> DB) | Inside I01/I02 | NEW | 2, 3, 4 | Infra | 4 | I07 | I01, I03 |
| I09 | `.concord/pipeline.yaml` parser | Inside I01 | NEW | 1, 2, 3, 4 | Infra | 8 | I01 | -- |
| I10a | `.concord/build.yaml` parser | Inside I04 | NEW | 1, 2, 3, 4 | Infra | 4 | I04 | -- |
| I10b | Webhook handler for Bitbucket repos | Inside I01 | NEW | 1, 2, 3, 4 | Infra | 4 | I01 | I09 |

**Subtotal: ~132h**

### 3.2 Test Runner Modules (Python)

The Concord monorepo has an existing MTIB client library at
`libs/python/corekinect/mtib_client/v2/`. The validation test_steps at
`apps/validation/test_steps/` is a basic manufacturing test framework, not
the validation test runner described in the architecture.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I10 | `mtib_client.py` (gRPC wrapper, thin layer) | `concord/libs/python/corekinect/mtib_client/v2/` | EXISTS/UPDATE | 2, 3, 4 | Infra | 4 | I11, I13, I14 | -- |
| I11 | `ztest_parser.py` (UART ztest marker parser) | `concord/apps/validation/test-runner/src/ztest_parser.py` | NEW | 2 | Infra | 8 | I13 | -- |
| I12 | `power_profiler.py` (power stream + per-test slicing) | `concord/apps/validation/test-runner/src/power_profiler.py` | NEW | 2, 3 | Infra | 12 | I13 | I10 |
| I13 | `test_spec_evaluator.py` (pass/fail vs test_spec.yaml) | `concord/apps/validation/test-runner/src/test_spec_evaluator.py` | NEW | 2 | Infra | 8 | -- | I11, I12 |
| I14 | `fixture_controller.py` (abstract action -> MTIB RPC mapping) | `concord/apps/validation/test-runner/src/fixture_controller.py` | NEW | 2, 3, 4 | Infra | 12 | I13 | I10 |
| I15 | `report_generator.py` (JUnit XML + summary + coverage) | `concord/apps/validation/test-runner/src/report_generator.py` | NEW | 2, 3, 4 | Infra | 8 | -- | I11, I13 |
| I16 | `artifact_manager.py` (MinIO upload, InfluxDB push) | `concord/apps/validation/test-runner/src/artifact_manager.py` | NEW | 2, 3, 4 | Infra | 6 | -- | -- |
| I17 | `harness_client.py` (concord_harness UART protocol) | `concord/apps/validation/test-runner/src/harness_client.py` | NEW | 3 | Infra | 12 | F28b | F28, F30 |
| I18 | `cloud_client.py` (CoreCloud REST wrapper for tests) | `concord/apps/validation/test-runner/src/cloud_client.py` | NEW | 3, 4 | Infra | 8 | F28b, I22 | -- |
| I19 | `nfc_client.py` (NFC reader integration) | `concord/apps/validation/test-runner/src/nfc_client.py` | NEW | 4 | Infra | 6 | I22 | H07 |
| I20 | `validation_runner.py` (Stage 4 orchestrator) | `concord/apps/validation/test-runner/src/validation_runner.py` | NEW | 4 | Infra | 16 | I22 | I14, I18, I19 |
| I21 | `main.py` (entry point, stage dispatch) | `concord/apps/validation/test-runner/src/main.py` | NEW | 2, 3, 4 | Infra | 4 | -- | I11-I20 |
| I21a | Stage 2 driver HW runner (orchestration module) | `concord/apps/validation/test-runner/src/driver_hw_runner.py` | NEW | 2 | Infra | 12 | -- | I10-I16 |
| I21b | Stage 3 integration runner (orchestration module) | `concord/apps/validation/test-runner/src/integration_runner.py` | NEW | 3 | Infra | 12 | -- | I10, I12, I14, I17 |

**Subtotal: ~128h**

### 3.3 CoreCloud Integration

The CoreCloud Python client exists at
`/home/mateo/work/concord/concord/libs/python/corekinect/core_cloud/`
with `api_interface.py`, `db_interface.py`, ORM models, and message definitions.
It needs wrapper utilities for test automation use cases.

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I22 | `cloud_client.py` wrapper for `CoreCloudRestInterface` | Inside I18 | NEW | 3, 4 | Infra | (incl. in I18) | -- | -- |
| I23 | Message verification utilities (`wait_for_message`, `assert_message_fields`) | Inside I18 | NEW | 4 | Infra | 4 | I22 | I18 |
| I24 | Config delivery: `GPSConfMsg.send_via_rest()` wrapper | Inside I18 | NEW | 4 | Infra | 4 | I22 | I18 |
| I24a | **DEFERRED** — `GroundModeConfigV2(ConfMsgBase)` Python SDK class (UID 538) | `msg_def_v1_0.py` | NEW | 4 | SDK + CoreCloud | 8 | I22 | **Blocked: needs REST endpoint or SS downlink trigger from CoreCloud C# team** |
| I24b | **DEFERRED** — `BiometricConfig(ConfMsgBase)` Python SDK class (UID 558) | `msg_def_v1_0.py` | NEW | 4 | SDK + CoreCloud | 4 | I22 | **Blocked: needs REST endpoint from CoreCloud C# team** |
| I24c | **DEFERRED** — Ground Mode Config REST endpoint or SS downlink trigger | CoreCloud C# server | NEW | 4 | CoreCloud | TBD | -- | **Blocked: CoreCloud team decision** |
| I25 | Device credential management (Vault integration for test devices) | Inside I20 | NEW | 4 | Infra | 4 | I22 | -- |
| I26 | Test environment setup (`VAL_1_0` namespace, env var mapping: `{NS}_API_KEY`, `{NS}_AUTH_USERNAME`, etc.) | Config + scripts | NEW | 3, 4 | Infra | 4 | I22 | I25 |

**Subtotal: ~16h (POC), ~28h+ (full including deferred)**

### 3.4 Container Images

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I27 | `concord-driver-test-runner` Docker image | `concord/deploy/` | NEW | 2 | Infra | 4 | I21a | I10-I16 |
| I28 | `concord-integration-test-runner` Docker image | `concord/deploy/` | NEW | 3 | Infra | 4 | I21b | I10, I12, I17 |
| I29 | `concord-validation-alpha` Docker image (Stage 4) | `concord/deploy/` | NEW | 4 | Infra | 4 | I20 | I14, I18-I20 |
| I30 | `concord-build-service` Docker image | `concord/deploy/` | NEW | 1, 2, 3, 4 | Infra | 4 | I04 | I04 |
| I31 | `concord-pipeline-controller` Docker image | `concord/deploy/` | NEW | 1, 2, 3, 4 | Infra | 2 | I02 | I02 |

**Subtotal: ~18h**

### 3.5 Helm / K8s Deployment

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I32 | Pipeline controller Deployment (Helm) | `concord/deploy/helm/concord/` | UPDATE | 1, 2, 3, 4 | Infra | 6 | I02 | I02, I31 |
| I33 | Build service Deployment (Helm) | `concord/deploy/helm/concord/` | UPDATE | 1, 2, 3, 4 | Infra | 6 | I04 | I04, I30 |
| I34 | PVC definitions (ccache, west-modules, workspace) | `concord/deploy/helm/concord/` | UPDATE | 1, 2, 3, 4 | Infra | 2 | I04 | -- |
| I35 | Vault secrets (Git SSH key, backend API key, device creds) | Vault config | UPDATE | 1, 2, 3, 4 | Infra | 4 | I04, I25 | -- |
| I36 | CronJob definitions (weekly/nightly Stage 4 runs) | `concord/deploy/helm/concord/` | NEW | 4 | Infra | 4 | I20 | I02, I29 |

**Subtotal: ~22h**

### 3.6 Data Schemas

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I37 | `test_spec.yaml` schema definition (JSON Schema or doc) | `concord/docs/schemas/` | NEW | 2 | Infra | 3 | F13 | -- |
| I38 | `board_features.json` schema definition | `concord/docs/schemas/` | NEW | 2 | Infra | 2 | F16, I13 | -- |
| I39 | `pipeline.yaml` schema definition (canonical) | `concord/docs/schemas/` | NEW | 1, 2, 3, 4 | Infra | 4 | I09 | -- |
| I40 | `build.yaml` schema definition | `concord/docs/schemas/` | NEW | 1, 2, 3, 4 | Infra | 2 | I10a | -- |
| I41 | Fixture profile JSON schema | `concord/docs/schemas/` | NEW | 2, 3, 4 | Infra | 2 | I14 | -- |
| I42 | `alpha_validation_spec.yaml` (Stage 4, 89 PRDTST tests) | `concord/apps/validation/test-runner/src/validation/specs/alpha_validation_spec.yaml` | NEW | 4 | Infra/QA | 24 | I20 | -- |
| I43 | JUnit XML extensions (power data, PRDTST ID mapping) | Inside I15 | NEW | 2, 3, 4 | Infra | 2 | -- | I15 |

**Subtotal: ~39h**

### 3.7 Frontend / Dashboard Updates

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| I44 | Validation pipeline list view | `concord/apps/frontend/concord-app/` or `concord-app-svelte/` | NEW | 1, 2, 3, 4 | Infra | 16 | -- | I01 |
| I45 | Pipeline detail view (stages, jobs, results) | Inside I44 | NEW | 1, 2, 3, 4 | Infra | 16 | -- | I01, I02 |
| I46 | Power trend charts (InfluxDB queries) | Inside I44 | NEW | 2, 3 | Infra | 8 | -- | I16 |
| I47 | Manual trigger UI | Inside I44 | NEW | 1, 2, 3, 4 | Infra | 4 | -- | I01 |

**Subtotal: ~44h**

---

## 4. Hardware / Physical Components

### 4.1 Dev-Kit Fixture (Stage 2)

| # | Component | Status | Stage(s) | Owner | Effort/Cost | Blocks | Blocked By |
|---|-----------|--------|----------|-------|-------------|--------|------------|
| H01 | nRF52840-DK (PCA10056) | PROCURE | 2 | HW | ~$40 | H03, F12 | -- |
| H02 | LSM6DSO breakout board (e.g., Adafruit LSM6DSO) | PROCURE | 2 | HW | ~$12 | H03 | -- |
| H03 | Fixture wiring: nRF52840-DK to LSM6DSO breakout (SPI + IRQ) | NEW | 2 | HW | 4h | H04 | H01, H02 |
| H04 | Power isolation circuitry (relay + current sense per sensor slot) | NEW | 2 | HW | 16h design + fab | H05 | H03 |
| H05 | MTIB test head cable assembly (SWD, UART, power, GPIO) | NEW | 2 | HW | 8h | H09 | H04 |
| H06 | LIS2DE12 breakout board (future, Slot B) | PROCURE | 2 (future) | HW | ~$8 | -- | -- |

**Subtotal: ~28h HW eng + ~$60 parts**

### 4.2 Alpha Product Test Fixture (Stages 3 & 4)

| # | Component | Status | Stage(s) | Owner | Effort/Cost | Blocks | Blocked By |
|---|-----------|--------|----------|-------|-------------|--------|------------|
| H07 | Alpha product board(s) for test (2 units recommended) | PROCURE | 3, 4 | HW | ~$200/unit | H08 | -- |
| H08 | MTIB test head connections (SWD, UART0, power, GPIO for button/charger) | NEW | 3, 4 | HW | 16h | H10 | H07 |
| H08a | Charger connection relay (MTIB-controlled, for charging tests) | NEW | 4 | HW | 8h | I20 | H07 |
| H08b | Button actuator (solenoid or relay, MTIB GPIO-controlled) | NEW | 4 | HW | 4h | I20 | H07 |
| H08c | NFC reader (USB, connected to MTIB host or agent node) | PROCURE | 4 | HW | ~$30 | I19 | -- |
| H08d | Temperature chamber access (for PRDTST-117, 164, 351, 372, 383, 191, 401) | PROCURE/EXISTING | 4 | HW | ~$2,000-5,000 (if new) | I20 | -- |
| H08e | Motion stimulus (shaker table or linear actuator for motion tests) | PROCURE | 4 | HW | ~$200-1,000 | I20 | -- |
| H08f | On-skin electrode simulation (resistive load or capacitive pad) | NEW | 4 | HW | 8h | I20 | H07 |
| H08g | Peltier temperature controller (for localized temp tests) | PROCURE | 4 | HW | ~$100-500 | I20 | -- |
| H08h | Photodiode array / LED sensor (for LED pattern verification) | PROCURE | 4 | HW | ~$50 | I20 | -- |

**Subtotal: ~36h HW eng + ~$3,000-6,500 parts (wide range due to temp chamber)**

### 4.3 MTIB Node Registration

| # | Component | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|--------|----------|-------|------------|--------|------------|
| H09 | Dev-kit MTIB node registration (capability labels, fixture profile JSON) | NEW | 2 | Infra | 2 | I07, F12 | H05 |
| H10 | Alpha product MTIB node registration (capability labels, fixture profile JSON) | NEW | 3, 4 | Infra | 2 | I07, F22, I20 | H08 |
| H11 | MTIB server v2 validation on new nodes (verify gRPC RPCs work) | NEW | 2, 3, 4 | Infra | 4 | H09, H10 | H05, H08 |

**Subtotal: ~8h**

---

## 5. Documentation Components

| # | Component | Path | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|------|--------|----------|-------|------------|--------|------------|
| D01 | Update `00-validation-philosophy.md` (rename `accelerometers` -> `accel_drv`, DTS prefix fixes) | `docs/concord/validation/architecture/00-validation-philosophy.md` | UPDATE | All | Infra | 2 | -- | -- |
| D02 | Update `09-final-architecture.md` (28 `accelerometers` references, schema alignment) | `docs/concord/validation/architecture/09-final-architecture.md` | UPDATE | All | Infra | 4 | -- | -- |
| D03 | Update `stage1-alpha-example.md` (already partially done per cohesion review) | `docs/concord/validation/examples/alpha/stage1-alpha-example.md` | UPDATE | 1 | Infra | 1 | -- | -- |
| D04 | Update `stage2-alpha-example.md` (repo name fixes) | `docs/concord/validation/examples/alpha/stage2-alpha-example.md` | UPDATE | 2 | Infra | 1 | -- | -- |
| D05 | Update `stage3-alpha-example.md` (rewrite extern globals, injection patterns) | `docs/concord/validation/examples/alpha/stage3-alpha-example.md` | UPDATE | 3 | Infra | 6 | -- | F28 |
| D06 | Stage 4 example document (`stage4-alpha-example.md`) | `docs/concord/validation/examples/alpha/stage4-alpha-example.md` | NEW | 4 | Infra | 8 | -- | I20, I42 |
| D07 | `concord_harness` module documentation (API reference, integration guide) | `concord_harness/README.md` + API docs | NEW | 3 | Infra | 6 | -- | F28-F37 |
| D08 | PRDTST-to-stage mapping (living document) | `docs/concord/validation/prdtst-stage-mapping.md` | NEW | 3, 4 | QA/Infra | 8 | -- | I42 |
| D09 | Test runner runbook (operational guide) | `docs/concord/validation/test-runner-runbook.md` | NEW | 2, 3, 4 | Infra | 6 | -- | I21 |
| D10 | Dev-kit fixture setup guide | `docs/concord/validation/devkit-fixture-setup.md` | NEW | 2 | HW/Infra | 4 | -- | H05 |
| D11 | Alpha product fixture setup guide | `docs/concord/validation/alpha-fixture-setup.md` | NEW | 3, 4 | HW/Infra | 4 | -- | H08 |
| D12 | `pipeline.yaml` / `build.yaml` authoring guide | `docs/concord/validation/pipeline-config-guide.md` | NEW | 1, 2, 3, 4 | Infra | 4 | -- | I39, I40 |

**Subtotal: ~54h**

---

## 6. Dependency Graph

```
LEGEND:  [Fxx] = Firmware   [Ixx] = Infrastructure   [Hxx] = Hardware   [Dxx] = Docs
         -----> = blocks (arrow points to what is unblocked)
         =====> = critical path

WEEK 1-2: FOUNDATIONS (parallel tracks)
=========================================================================

Track A (Firmware):                    Track B (Hardware):

  [F01] accel_drv clean branch         [H01] Procure nRF52840-DK
    |                                  [H02] Procure LSM6DSO breakout
    +----> [F02] Root Kconfig              |
    +----> [F03] Root CMakeLists           v
    +----> [F04] module.yml            [H03] Fixture wiring -------+
    +----> [F07] ck,lsm6dso.yaml           |                      |
    +----> [F08] ck,lsm6dso-stub.yaml      v                      |
    |          |                       [H04] Power isolation       |
    |          v                           |                       |
    |      [F09] lsm6dso_stub.c            v                      |
    |      [F10] Stub Kconfig/CMake    [H05] MTIB cable assembly   |
    |          |                           |                       |
    |          v                           v                       |
    |      [F11] Interface tests ===>  [H09] MTIB node reg         |
    |                                                              |
    +----> [F17-F19] alpha_fw getters                              |
               |                                                   |
               v                       Track C (Infra - Harness):  |
           [F20-F21] App stub tests                                |
                                       [F28] concord_harness.h     |
                                           |                       |
Track D (Infra - Pipeline):                v                       |
                                       [F29-F32] Shell, Registry,  |
  [I03] Prisma schema                      Emit                   |
    |                                      |                       |
    v                                      v                       |
  [I09] pipeline.yaml parser          [F34-F36] Kconfig, CMake,    |
  [I10b] Webhook handler                   module.yml             |
    |                                      |                       |
    v                                      v                       |
  [I01] Pipeline trigger API           [F37] Harness unit tests    |
    |                                                              |
    v                                                              |
  [I04] Build service ============================================>+
    |
    v
  [I02] Pipeline controller =======> CRITICAL PATH BOTTLENECK
    |
    +----> [I05] Bitbucket status
    +----> [I06] Stage gating
    +----> [I07] MTIB node matching


WEEK 3-5: STAGE 1 COMPLETION + STAGE 2 START
=========================================================================

  [F11] + [F20] + [I01] + [I04] + [I02]
    ||
    || (Stage 1 end-to-end operational)
    vv
  [F05] LSM6DSO driver (40h, parallel with infra)
    |
    v
  [F12] HW test firmware
  [F13] test_spec.yaml
  [F38] Dev-kit board definition
    |
    v
  [I10-I16] Test runner modules (parallel development)
    |
    v
  [I21a] Stage 2 driver HW runner
  [I27] Docker image


WEEK 5-7: STAGE 2 COMPLETION + STAGE 3 START
=========================================================================

  [F22] alpha_fw concord_harness.c     [I17] harness_client.py
    |                                      |
    v                                      v
  [F23-F24] Harness guards + EMIT     [I21b] Integration runner
    |                                      |
    v                                      v
  [F28b] Integration test Python       [I28] Docker image
    |
    v
  Stage 3 end-to-end on Alpha board


WEEK 7-10: STAGE 3 COMPLETION + STAGE 4
=========================================================================

  [I42] alpha_validation_spec.yaml (89 PRDTST tests)
    |
    v
  [I18-I20] cloud_client, nfc_client, validation_runner
    |
    v
  [I29] concord-validation-alpha image
  [I36] CronJob definitions
    |
    v
  Stage 4 end-to-end on Alpha product board


HARDWARE CRITICAL PATH (longest lead time):
=========================================================================

  [H01-H02] Procure        [H07] Procure Alpha boards
      |                         |
      v (1-2 weeks ship)        v (may be in stock)
  [H03] Wire fixture        [H08] Wire Alpha fixture
      |                         |
      v                         v
  [H04] Power isolation     [H08a-h] Fixture peripherals
      |  (2-3 weeks PCB)       |  (2-4 weeks)
      v                         v
  [H05] Cable assembly      [H10] MTIB node reg
      |                         |
      v                         v
  [H09] MTIB node reg      Stage 3/4 HW ready
      |
      v
  Stage 2 HW ready
  (Target: Week 4-5)
```

---

## 7. Summary Table

All components sorted by critical path priority. Items that block the most
downstream work appear first.

| # | Component | Location | Status | Stage(s) | Owner | Effort (h) | Blocks | Blocked By |
|---|-----------|----------|--------|----------|-------|------------|--------|------------|
| I03 | Prisma schema updates | `concord/prisma/schema.prisma` | UPDATE | All | Infra | 8 | I01, I02, I08 | -- |
| F01 | `accel_drv` clean branch | `accel_drv/` | NEW | 1, 2 | FW | 2 | F02-F16 | -- |
| I09 | `pipeline.yaml` parser | `concord/apps/backend/http-api/` | NEW | All | Infra | 8 | I01 | -- |
| F02 | Root Kconfig | `accel_drv/Kconfig` | NEW | 1, 2 | FW | 1 | F03, F06, F09 | F01 |
| F03 | Root CMakeLists.txt | `accel_drv/CMakeLists.txt` | NEW | 1, 2 | FW | 1 | F06, F09 | F01 |
| F04 | `zephyr/module.yml` | `accel_drv/zephyr/module.yml` | UPDATE | 1, 2 | FW | 0.5 | F06, F09 | F01 |
| F08 | DTS stub binding | `accel_drv/dts/bindings/ck,lsm6dso-stub.yaml` | NEW | 1 | FW | 1 | F09 | F01 |
| F09 | Stub driver | `accel_drv/stubs/lsm6dso_stub.c` | NEW | 1 | FW | 6 | F11, F20 | F02, F03, F08 |
| F10 | Stub Kconfig/CMake | `accel_drv/stubs/` | NEW | 1 | FW | 1 | F09 | F02, F03 |
| I01 | Pipeline trigger API | `concord/apps/backend/http-api/` | NEW | All | Infra | 12 | I02, I04, I44 | I03, I09 |
| I04 | Build service | `concord/apps/backend/build-service/` | NEW | All | Infra | 32 | F11, F12, F20, I02 | -- |
| I02 | Pipeline controller | `concord/apps/backend/pipeline-controller/` | NEW | All | Infra | 40 | I05-I08, all stages | I01, I03 |
| F17 | alpha_state_machine.c getter | `alpha_fw/src/app/alpha_state_machine.c` | UPDATE | 1, 3 | FW | 2 | F20, F22 | -- |
| F18 | motion_state_machine.c getter | `alpha_fw/src/app/motion_state_machine.c` | UPDATE | 1, 3 | FW | 1 | F20 | -- |
| F19 | Move types to headers | `alpha_fw/src/app/*.h` | UPDATE | 1, 3 | FW | 2 | F17, F20, F22 | -- |
| F11 | Interface contract tests | `accel_drv/tests/interface/` | NEW | 1 | FW | 12 | I01 (Stage 1 complete) | F09, F10 |
| F20 | App-level stub tests (~15 module stubs) | `alpha_fw/tests/app/` | NEW | 1 | FW | 20 | I01 (Stage 1 complete) | F09, F17-F19 |
| F21 | App test build files | `alpha_fw/tests/app/` | NEW | 1 | FW | 4 | I01 | F08, F09 |
| F14 | `accel_drv` pipeline.yaml | `accel_drv/.concord/pipeline.yaml` | NEW | 1, 2 | FW/Infra | 4 | I01 | F01 |
| F15 | `accel_drv` build.yaml | `accel_drv/.concord/build.yaml` | NEW | 1, 2 | FW/Infra | 3 | I04 | F01 |
| F26 | `alpha_fw` pipeline.yaml | `alpha_fw/.concord/pipeline.yaml` | NEW | 1, 3, 4 | Infra | 4 | I01 | -- |
| F27 | `alpha_fw` build.yaml | `alpha_fw/.concord/build.yaml` | NEW | 1, 3, 4 | Infra | 3 | I04 | -- |
| H01 | nRF52840-DK | Procure | PROCURE | 2 | HW | $40 | H03 | -- |
| H02 | LSM6DSO breakout | Procure | PROCURE | 2 | HW | $12 | H03 | -- |
| H03 | Dev-kit fixture wiring | Physical | NEW | 2 | HW | 4 | H04 | H01, H02 |
| H04 | Power isolation circuitry | Physical | NEW | 2 | HW | 16 | H05 | H03 |
| H05 | MTIB cable assembly | Physical | NEW | 2 | HW | 8 | H09 | H04 |
| F07 | DTS binding `ck,lsm6dso.yaml` | `accel_drv/dts/bindings/` | NEW | 2 | FW | 3 | F05, F38 | F01 |
| F05 | LSM6DSO driver implementation | `accel_drv/drivers/lsm6dso/src/` | NEW | 2 | FW | 40 | F12 | F01 |
| F06 | LSM6DSO Kconfig | `accel_drv/drivers/lsm6dso/Kconfig` | NEW | 1, 2 | FW | 1 | F05, F09 | F02 |
| F38 | Dev-kit board definition | `ck_boards/.../devkit_nrf52840_lsm6dso_spi/` | NEW | 2 | FW | 8 | F12 | F07 |
| F12 | HW test firmware | `accel_drv/tests/lsm6dso/` | NEW | 2 | FW | 16 | I21a | F05, F07, F38 |
| F13 | `test_spec.yaml` | `accel_drv/tests/lsm6dso/test_spec.yaml` | NEW | 2 | FW | 4 | I13 | F12 |
| F16 | `board_features.py` script | `accel_drv/scripts/` | NEW | 2 | Infra | 4 | I13 | F12 |
| I10 | `mtib_client.py` updates | `concord/libs/python/.../mtib_client/v2/` | EXISTS/UPDATE | 2, 3, 4 | Infra | 4 | I11-I14, I17 | -- |
| I11 | `ztest_parser.py` | `concord/apps/validation/test-runner/` | NEW | 2 | Infra | 8 | I13, I21a | -- |
| I12 | `power_profiler.py` | `concord/apps/validation/test-runner/` | NEW | 2, 3 | Infra | 12 | I13, I21a | I10 |
| I13 | `test_spec_evaluator.py` | `concord/apps/validation/test-runner/` | NEW | 2 | Infra | 8 | I21a | I11, I12 |
| I14 | `fixture_controller.py` | `concord/apps/validation/test-runner/` | NEW | 2, 3, 4 | Infra | 12 | I21a, I21b, I20 | I10 |
| I15 | `report_generator.py` | `concord/apps/validation/test-runner/` | NEW | 2, 3, 4 | Infra | 8 | I21a | I11, I13 |
| I16 | `artifact_manager.py` | `concord/apps/validation/test-runner/` | NEW | 2, 3, 4 | Infra | 6 | I21a | -- |
| I21a | Stage 2 driver HW runner | `concord/apps/validation/test-runner/` | NEW | 2 | Infra | 12 | -- | I10-I16 |
| H09 | Dev-kit MTIB node registration | Concord DB + K8s labels | NEW | 2 | Infra | 2 | I07, F12 | H05 |
| I05 | Bitbucket commit status | Inside I02 | NEW | All | Infra | 4 | -- | I02 |
| I06 | Stage gating logic | Inside I02 | NEW | 2, 3, 4 | Infra | 8 | I07 | I02 |
| I07 | MTIB node matching | Inside I02 | NEW | 2, 3, 4 | Infra | 8 | -- | I02, H09, H10 |
| I08 | SubmoduleMapping sync | Inside I01/I02 | NEW | 2, 3, 4 | Infra | 4 | I07 | I01, I03 |
| F28 | `concord_harness.h` (macros, API) | `concord_harness/` | NEW | 3 | Infra | 8 | F22, F30-F34 | -- |
| F29 | `concord_harness_types.h` | `concord_harness/` | NEW | 3 | Infra | 2 | F30-F33 | F28 |
| F30 | `concord_shell.c` | `concord_harness/` | NEW | 3 | Infra | 8 | F22, I17 | F28, F29 |
| F31 | `concord_registry.c` | `concord_harness/` | NEW | 3 | Infra | 4 | F30 | F28, F29 |
| F32 | `concord_emit.c` | `concord_harness/` | NEW | 3 | Infra | 4 | F24 | F28 |
| F33 | `concord_log_backend.c` | `concord_harness/` | NEW | 3 | Infra | 4 | -- | F28 |
| F34 | Harness Kconfig | `concord_harness/zephyr/Kconfig` | NEW | 3 | Infra | 2 | F30-F33 | -- |
| F35 | Harness CMakeLists.txt | `concord_harness/zephyr/CMakeLists.txt` | NEW | 3 | Infra | 1 | F30-F33 | -- |
| F36 | Harness module.yml | `concord_harness/zephyr/module.yml` | NEW | 3 | Infra | 0.5 | F22 | -- |
| F37 | Harness unit tests | `concord_harness/tests/` | NEW | 3 | Infra | 8 | -- | F28-F32 |
| F22 | `alpha_fw/src/concord_harness.c` | `alpha_fw/src/concord_harness.c` | NEW | 3 | FW/Infra | 16 | F28b | F28, F19 |
| F23 | Harness `#ifdef` guards in alpha_fw | `alpha_fw/src/app/app.c` + others | UPDATE | 3 | FW | 4 | F22 | F28 |
| F24 | CONCORD_EMIT calls in state machines | `alpha_fw/src/app/` | UPDATE | 3 | FW | 3 | F22 | F28, F23 |
| F41 | Alpha B0 harness overlay | `ck_boards/.../alpha_b0/` | UPDATE | 3 | FW | 2 | F22 | F28 |
| I17 | `harness_client.py` | `concord/apps/validation/test-runner/` | NEW | 3 | Infra | 12 | F28b, I21b | F28, F30 |
| I18 | `cloud_client.py` | `concord/apps/validation/test-runner/` | NEW | 3, 4 | Infra | 8 | F28b, I20 | -- |
| F28a | `integration_spec.yaml` | `alpha_fw/.concord/` | NEW | 3 | FW/Infra | 4 | I21b | -- |
| F28b | Integration test Python | `alpha_fw/.concord/tests/integration/` | NEW | 3 | FW/Infra | 24 | I21b | F22, I17, I18 |
| I21b | Stage 3 integration runner | `concord/apps/validation/test-runner/` | NEW | 3 | Infra | 12 | -- | I10, I12, I14, I17 |
| H07 | Alpha product boards (2 units) | Procure | PROCURE | 3, 4 | HW | ~$400 | H08 | -- |
| H08 | Alpha MTIB test head connections | Physical | NEW | 3, 4 | HW | 16 | H10 | H07 |
| H10 | Alpha MTIB node registration | Concord DB + K8s | NEW | 3, 4 | Infra | 2 | I07 | H08 |
| I42 | `alpha_validation_spec.yaml` (89 tests) | `concord/apps/validation/test-runner/` | NEW | 4 | Infra/QA | 24 | I20 | -- |
| I19 | `nfc_client.py` | `concord/apps/validation/test-runner/` | NEW | 4 | Infra | 6 | I20 | H08c |
| I20 | `validation_runner.py` (Stage 4 orchestrator) | `concord/apps/validation/test-runner/` | NEW | 4 | Infra | 16 | -- | I14, I18, I19 |
| I23 | Message verification utilities | Inside I18 | NEW | 4 | Infra | 4 | I20 | I18 |
| I24 | Config delivery: `GPSConfMsg.send_via_rest()` wrapper | Inside I18 | NEW | 4 | Infra | 4 | I20 | I18 |
| I24a-c | **DEFERRED** — GroundModeConfigV2 + BiometricConfig SDK + REST endpoint | See Section 3.3 | NEW | 4 | SDK + CoreCloud | 12+ | -- | **Blocked** |
| I25 | Device credential management | Vault config | NEW | 4 | Infra | 4 | I20 | -- |
| I26 | Test environment setup (`VAL_1_0` env var mapping) | Config | NEW | 3, 4 | Infra | 4 | I22 | I25 |
| H08a | Charger relay | Physical | NEW | 4 | HW | 8 | I20 | H07 |
| H08b | Button actuator | Physical | NEW | 4 | HW | 4 | I20 | H07 |
| H08c | NFC reader | Procure | PROCURE | 4 | HW | ~$30 | I19 | -- |
| H08d | Temperature chamber | Procure/Existing | PROCURE | 4 | HW | ~$2,000-5,000 | I20 | -- |
| H08e | Motion stimulus | Procure | PROCURE | 4 | HW | ~$200-1,000 | I20 | -- |
| H08f | On-skin electrode sim | Physical | NEW | 4 | HW | 8 | I20 | H07 |
| H08g | Peltier controller | Procure | PROCURE | 4 | HW | ~$100-500 | I20 | -- |
| H08h | LED sensor | Procure | PROCURE | 4 | HW | ~$50 | I20 | -- |
| I27 | Driver test runner Docker image | `concord/deploy/` | NEW | 2 | Infra | 4 | I21a | I10-I16 |
| I28 | Integration test runner Docker image | `concord/deploy/` | NEW | 3 | Infra | 4 | I21b | I10, I17 |
| I29 | Validation Alpha Docker image | `concord/deploy/` | NEW | 4 | Infra | 4 | I20 | I14, I18-I20 |
| I30 | Build service Docker image | `concord/deploy/` | NEW | All | Infra | 4 | I04 | I04 |
| I31 | Pipeline controller Docker image | `concord/deploy/` | NEW | All | Infra | 2 | I02 | I02 |
| I32 | Pipeline controller Helm | `concord/deploy/helm/` | UPDATE | All | Infra | 6 | I02 | I02, I31 |
| I33 | Build service Helm | `concord/deploy/helm/` | UPDATE | All | Infra | 6 | I04 | I04, I30 |
| I34 | PVC definitions | `concord/deploy/helm/` | UPDATE | All | Infra | 2 | I04 | -- |
| I35 | Vault secrets | Vault | UPDATE | All | Infra | 4 | I04, I25 | -- |
| I36 | CronJob definitions (weekly/nightly) | `concord/deploy/helm/` | NEW | 4 | Infra | 4 | I20 | I02, I29 |
| I37-I41 | Schema definitions (5 schemas) | `concord/docs/schemas/` | NEW | 2, 3, 4 | Infra | 13 | various | -- |
| I43 | JUnit XML extensions | Inside I15 | NEW | 2, 3, 4 | Infra | 2 | -- | I15 |
| I44-I47 | Frontend / Dashboard (4 views) | `concord/apps/frontend/` | NEW | All | Infra | 44 | -- | I01, I02 |
| D01-D12 | Documentation (12 items) | `docs/concord/validation/` | MIX | All | Various | 54 | -- | Various |

---

## 8. Effort Summary

### 8.1 Total Effort by Category

| Category | Items | Total Hours | Notes |
|----------|-------|-------------|-------|
| **Firmware** (driver, stubs, tests, harness declarations) | F01-F28b | ~238h | Includes 40h LSM6DSO driver, 20h app stubs, 16h harness declarations |
| **Infrastructure** (pipeline, test runners, images, deploy) | I01-I47 | ~399h | Includes 40h pipeline controller, 32h build service, 128h test runners |
| **Hardware** (fixtures, procurement, wiring) | H01-H11 | ~100h + $3,000-6,500 | HW eng hours; parts cost is wide range (temp chamber dominates) |
| **Documentation** | D01-D12 | ~54h | Includes 8h new Stage 4 example doc |
| **TOTAL** | -- | **~791h** | Engineering hours only; does not include procurement lead time |

### 8.2 Total Effort by Stage

| Stage | Firmware (h) | Infra (h) | HW (h) | Docs (h) | Total (h) |
|-------|-------------|-----------|---------|----------|-----------|
| **Stage 1: Software Tests** | 55 | 72 | 0 | 3 | ~130h |
| **Stage 2: Driver HW Tests** | 93 | 96 | 36 | 5 | ~230h |
| **Stage 3: Integration Tests** | 74 | 88 | 20 | 12 | ~194h |
| **Stage 4: Product Validation** | 0 | 102 | 44 | 12 | ~158h |
| **Cross-stage / shared** | 16 | 41 | 0 | 22 | ~79h |
| **TOTAL** | **238h** | **399h** | **100h** | **54h** | **~791h** |

Note: Category totals and stage totals now agree at ~791h.

### 8.3 Critical Path Duration Estimate

```
Weeks 1-2:   Foundations (F01-F10, I03, I09, I01, F28 harness start)
Weeks 2-4:   Stage 1 firmware complete (F11, F20-F21)
Weeks 3-5:   Pipeline infra complete (I04, I02) *** BOTTLENECK ***
Week 5:      Stage 1 operational end-to-end
Weeks 3-6:   LSM6DSO driver (F05, parallel with infra)
Weeks 5-7:   Stage 2 test runner (I10-I16, I21a)
Weeks 4-6:   Dev-kit fixture HW ready (H01-H05, H09)
Week 7:      Stage 2 operational end-to-end
Weeks 3-7:   concord_harness module complete (F28-F37)
Weeks 6-8:   Alpha harness integration (F22-F24)
Weeks 7-9:   Stage 3 test runner + integration tests (I17, I21b, F28b)
Week 9:      Stage 3 operational end-to-end
Weeks 8-10:  Stage 4 spec + runner (I42, I20, I18-I19)
Weeks 8-10:  Alpha product fixture (H07-H08, H10)
Week 10-11:  Stage 4 operational (commit subset)
Week 12:     Stage 4 full suite (weekly + release)

CRITICAL PATH: I02 (pipeline controller) -> I06 (stage gating) -> Stage 2+
CALENDAR: ~10-12 weeks with 3 parallel engineers + 1 HW engineer
          ~24 weeks single-threaded
```

### 8.4 Recommended Team Allocation

| Role | Person-Weeks | Focus |
|------|-------------|-------|
| **Firmware Engineer** | 6 weeks | Track A: accel_drv restructuring, LSM6DSO driver, stub/interface/HW tests, alpha_fw getters, harness declarations |
| **Infra Engineer 1** | 10 weeks | Track C: Pipeline controller, build service, HTTP API, pipeline.yaml parsing, K8s deployment, Helm, schemas |
| **Infra Engineer 2** | 8 weeks | Track D: Test runner modules (mtib_client, ztest_parser, power_profiler, fixture_controller, report_generator), Docker images |
| **Infra Engineer 3 (or 2 cont'd)** | 6 weeks | Track E: concord_harness module, harness_client.py, Stage 3/4 runners, CoreCloud integration, validation_spec.yaml |
| **HW Engineer** | 4 weeks (spread) | Track B: Dev-kit fixture design + fab, Alpha product fixture wiring, MTIB cabling |
| **QA / Test Engineer** | 2 weeks | I42: Map 89 PRDTST tests to validation_spec.yaml; D08: PRDTST-to-stage mapping |
| **Frontend Engineer** | 3 weeks | I44-I47: Dashboard views (can be deferred to after Stage 2 is operational) |

**Total: ~39 person-weeks (~975h), 10-12 calendar weeks with full parallelization**

The gap between the 791h component estimate and 975h allocation accounts for
integration testing between components, debugging, code review, and the overhead
of parallel coordination.

### 8.5 What EXISTS vs What is NEW

| Category | EXISTS (reusable as-is) | UPDATE (needs modification) | NEW (from scratch) |
|----------|------------------------|---------------------------|-------------------|
| Firmware repos | `accel_drv` (repo identity), `lsm6dso_drv` (code reference), `alpha_fw` (app code), `ck_boards` (Alpha B0 board) | `accel_drv` (nuke branch), `alpha_fw` (add getters, harness, tests, .concord/), `ck_boards` (add dev-kit board) | `concord_harness` (entire module) |
| Concord monorepo | HTTP API framework, Prisma ORM, K8s client, MinIO client, InfluxDB client, MTIB client v2, CoreCloud client, frontend app, Helm charts | Prisma schema, Helm values, HTTP API routes, Vault config | Pipeline controller, build service, all test runner modules, Docker images, CronJobs |
| Hardware | MTIB V2 server (deployed), K3s cluster (operational), agent nodes | MTIB node labels/annotations | Dev-kit fixture, Alpha test fixture, all fixture peripherals |
| Documentation | 00, 09, 10, 11, 12, arch-stage1, arch-stage2, arch-stage3, alpha-prdtst-reference, cohesion-review | 00, 09, 10, 11, 12 (naming/pattern fixes) | Stage 4 example, harness docs, runbook, fixture guides, PRDTST mapping, config guide |

---

## 9. Sprint Planning Guide

### 9.1 Sprint 1 (Weeks 1-2): Foundations

**Goal:** Establish the repo structure and begin all parallel tracks.

**Firmware (Track A):**
- F01: Create clean nuke branch on `accel_drv` (2h)
- F02-F04: Root Kconfig, CMakeLists.txt, module.yml (2.5h)
- F06: LSM6DSO driver Kconfig (1h)
- F08: DTS stub binding `ck,lsm6dso-stub.yaml` (1h)
- F09-F10: Stub driver + Kconfig/CMake (7h)
- F17-F19: alpha_fw getters + move types to headers (5h)

**Infrastructure (Track C/D):**
- I03: Prisma schema updates for validation models (8h)
- I09: pipeline.yaml parser (8h)
- I10b: Webhook handler for Bitbucket (4h)
- I39-I40: pipeline.yaml and build.yaml schema definitions (6h)

**Hardware (Track B):**
- H01-H02: Order nRF52840-DK and LSM6DSO breakout board
- H07: Order Alpha product boards for Stage 3/4 fixture

**Infra - Harness (Track E):**
- F28: Begin `concord_harness.h` public API design (8h)

**Sprint 1 Definition of Done:**
- `accel_drv` nuke branch exists with stub driver compiling on native_sim
- alpha_fw state machine getters merged behind `#ifdef CONFIG_ZTEST`
- Prisma schema migration for validation models deployed to staging
- pipeline.yaml parser unit tests passing
- HW parts on order

### 9.2 Sprint 2 (Weeks 3-4): Stage 1 Firmware + Pipeline Core

**Goal:** Stage 1 tests compiling and running locally. Pipeline API and build service MVP.

**Firmware (Track A):**
- F11: Interface contract tests (12h)
- F20: App-level stub tests for alpha_state_machine -- the ~15 module stubs (20h)
- F21: App test build files (testcase.yaml, prj.conf, native_sim overlay) (4h)
- F14-F15: .concord/pipeline.yaml + build.yaml for accel_drv (7h)
- F25: Submodule pointer update (0.5h)

**Infrastructure (Track C):**
- I01: Pipeline trigger API endpoint (12h)
- I04: Build service MVP -- clone, build, upload artifacts (32h, starts here, continues Sprint 3)
- I10a: build.yaml parser inside build service (4h)

**Infrastructure (Track D):**
- I10: MTIB client updates/validation (4h)
- I11: ztest_parser.py (8h)

**Infra - Harness (Track E):**
- F29-F32: concord_harness implementation (concord_shell.c, concord_registry.c, concord_emit.c) (18h)
- F34-F36: Kconfig, CMakeLists.txt, module.yml (3.5h)

**Sprint 2 Definition of Done:**
- `twister -p native_sim -T tests/interface/` passes on local machine
- `twister -p native_sim -T tests/app/` passes on local machine (alpha_fw)
- Pipeline trigger API accepting webhook payloads (staging)
- Build service compiling firmware from repo (staging)
- ztest_parser.py parsing sample UART output correctly
- concord_harness module compiling in a test firmware

### 9.3 Sprint 3 (Weeks 5-6): Stage 1 E2E + Stage 2 Firmware

**Goal:** Stage 1 pipeline running end-to-end. Stage 2 firmware compiling.

**Infrastructure (Track C):**
- I02: Pipeline controller MVP -- Job creation, watch, stage transitions (40h, starts here)
- I05: Bitbucket commit status reporting (4h)
- I06: Stage gating logic (8h)
- I30-I31: Build service + pipeline controller Docker images (6h)
- I32-I33: Helm chart updates (12h)
- I34-I35: PVC definitions + Vault secrets (6h)

**Firmware (Track A):**
- F05: Begin LSM6DSO driver implementation (40h, continues Sprint 4)
- F07: DTS binding `ck,lsm6dso.yaml` (3h)
- F38: Dev-kit board definition (8h)

**Infrastructure (Track D):**
- I12: power_profiler.py (12h)
- I13: test_spec_evaluator.py (8h)
- I14: fixture_controller.py (12h, starts here)

**Hardware (Track B):**
- H03: Dev-kit fixture wiring (4h) -- parts should have arrived
- H04: Power isolation design + PCB order (16h)

**Infra - Harness (Track E):**
- F33: concord_log_backend.c (4h)
- F37: Harness unit tests (8h)

**Sprint 3 Definition of Done:**
- Stage 1 pipeline runs automatically: Bitbucket push -> build -> test -> commit status
- LSM6DSO driver skeleton compiling for alpha_b0
- DTS binding validated against existing Alpha board DTS
- Dev-kit board definition accepted by Zephyr build system
- Power profiler slicing sample power traces correctly
- Dev-kit fixture wired (pending PCB for power isolation)

### 9.4 Sprint 4 (Weeks 7-8): Stage 2 E2E + Stage 3 Start

**Goal:** Stage 2 test runner operational on dev-kit fixture. Stage 3 harness integrated.

**Firmware (Track A):**
- F05: Complete LSM6DSO driver (continued)
- F12: HW test firmware (16h)
- F13: test_spec.yaml (4h)
- F16: board_features.py extraction script (4h)
- F22: alpha_fw concord_harness.c (16h)
- F23: CONCORD_HARNESS #ifdef guards in alpha_fw (4h)
- F24: CONCORD_EMIT calls in state machines (3h)

**Infrastructure (Track D):**
- I14: fixture_controller.py (continued)
- I15: report_generator.py (8h)
- I16: artifact_manager.py (6h)
- I21a: Stage 2 driver HW runner orchestration (12h)
- I27: Driver test runner Docker image (4h)
- I37-I38, I41: Schema definitions (7h)

**Infrastructure (Track E):**
- I17: harness_client.py (12h)
- I18: cloud_client.py (8h)

**Hardware (Track B):**
- H04: Power isolation PCB arrives and assembled
- H05: MTIB cable assembly (8h)
- H09: Dev-kit MTIB node registration (2h)
- H08: Begin Alpha product MTIB test head (16h)

**Sprint 4 Definition of Done:**
- Stage 2 pipeline runs: push to accel_drv -> build -> flash to dev-kit -> ztest -> power -> pass/fail
- LSM6DSO WHO_AM_I reads correctly on dev-kit via MTIB
- Alpha firmware builds with CONFIG_CONCORD_HARNESS=y
- `concord list` shows harness points on Alpha board UART
- harness_client.py sending commands and parsing responses

### 9.5 Sprint 5 (Weeks 9-10): Stage 3 E2E + Stage 4 Start

**Goal:** Stage 3 integration tests running on Alpha board. Stage 4 spec defined.

**Firmware/Infra:**
- F28a: integration_spec.yaml (4h)
- F28b: Integration test Python modules (24h)
- F41: Alpha B0 harness overlay if needed (2h)
- I21b: Stage 3 integration runner (12h)
- I28: Integration test runner Docker image (4h)

**Stage 4:**
- I42: alpha_validation_spec.yaml -- map 89 PRDTST tests to spec (24h)
- I19: nfc_client.py (6h)
- I20: validation_runner.py Stage 4 orchestrator (16h)
- I23-I24: Message verification + GPS config delivery utilities (8h)
- I24a-c: **DEFERRED** — GroundModeConfigV2 + BiometricConfig SDK classes + REST endpoint (12h+ blocked on CoreCloud team)
- I25-I26: Device credential management + test env setup (8h)

**Hardware:**
- H08a-h: Alpha fixture peripherals (charger relay, button, NFC, etc.)
- H10: Alpha MTIB node registration (2h)
- H11: MTIB server v2 validation on new nodes (4h)

**Sprint 5 Definition of Done:**
- Stage 3 pipeline runs: push to alpha_fw -> instrumented build -> flash -> harness tests -> pass/fail
- alpha_validation_spec.yaml covers all 89 PRDTST tests with tags
- Stage 4 commit subset (43 tests) executes on Alpha fixture
- CronJob for weekly full suite configured

### 9.6 Sprint 6 (Weeks 11-12): Stage 4 Hardening + Dashboard

**Goal:** Stage 4 fully operational. Dashboard live.

- I29: concord-validation-alpha Docker image (4h)
- I36: CronJob definitions for weekly/nightly (4h)
- I43: JUnit XML extensions (2h)
- I44-I47: Frontend dashboard (44h)
- D01-D12: Documentation cleanup (54h, spread across team)

**Sprint 6 Definition of Done:**
- All 4 stages operational end-to-end
- Dashboard shows pipeline status, test results, power trends
- Stage 4 weekly suite completes without infrastructure failures
- All documentation updated and consistent

---

## Appendix A: PRDTST Coverage by Stage

The 89 Alpha PRDTST tests map to stages as follows (many tests span Stage 3 + 4):

| Domain | Count | Stage 3 | Stage 4 Commit | Stage 4 Weekly | Notes |
|--------|-------|---------|----------------|----------------|-------|
| Power / Runtime | 7 | 2 (idle, active current) | 3 (sleep, active, normal) | 7 (+ endurance, lockout) | Endurance (72h) weekly only |
| Config Values | 18 | 6 (config propagation) | 12 (default/non-default) | 18 | Config tests are fast |
| Motion Detection | 5 | 3 (threshold, duration, axis) | 5 | 5 | All runnable per-commit |
| Charging / BMS | 29 | 4 (SoC, temp, charger detect) | 8 (detect, LED, SoC) | 29 (+ full cycle, temp limits) | Full charge cycle = 4h |
| Environmental | 7 | 3 (accuracy at 25C) | 4 (accuracy, altitude) | 7 (+ extremes) | Extreme temp weekly only |
| GNSS | 7 | 0 | 2 (cold start) | 7 (+ warm, aiding, heading) | GNSS needs outdoor/simulator |
| On-Skin / Biometric | 3 | 2 (on-skin detect, bio msg) | 3 | 3 | Needs on-skin electrode |
| Button / SOS / Haptic | 9 | 0 | 5 (button, haptic) | 9 (+ SOS, mfg mode) | Needs button actuator |
| NFC | 1 | 0 | 1 (PRDTST-337) | 1 | Needs NFC reader |
| FUOTA | 1 | 0 | 0 | 1 | Weekly only |
| VSM / IPC | 1 | 1 (VSM power cutoff) | 0 | 1 | Stage 3 via harness |
| Cloud Messages | 1 | 0 | 0 | 1 (temp range) | Weekly (needs temp chamber) |
| **TOTAL** | **89** | **21** | **43** | **89** | |

## Appendix B: Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| R1 | Pipeline controller (I02) is the critical bottleneck at 40h | Delays all stages beyond Stage 1 | High | Start I02 in Week 1; keep scope minimal for MVP; add features incrementally; consider splitting into Phase A (job creation) and Phase B (stage gating) |
| R2 | Dev-kit PCB fabrication (H04) takes 3-4 weeks | Stage 2 HW tests delayed until Week 6+ | Medium | Order PCB in Week 1; use point-to-point wiring prototype for initial bring-up testing; have backup supplier |
| R3 | LSM6DSO fresh driver (F05, 40h) may take longer than estimated | Stage 2 firmware delayed; blocks all HW tests | Medium | Reference existing `lsm6dso_drv` code at `/home/mateo/work/firmware/alpha_fw/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/`; time-box to 2 weeks; fall back to porting existing driver with flat path restructure if deadline approaches |
| R4 | Temperature chamber ($2-5K) procurement may be slow or need approval | Stage 4 weekly suite incomplete for 7 temp-dependent PRDTST tests (117, 164, 351, 372, 383, 191, 401) | Low | Defer temp-dependent tests to Phase 2; use existing manufacturing temp chamber if available; mark tests as SKIP until hardware arrives |
| R5 | App-level stub module count (~15 modules in F20) higher than expected | Stage 1 app tests delayed | Medium | Audit dependencies in Phase 0 (arch-stage1 Section 4.1 has the full list); stub incrementally; test alpha_state_machine.c first, motion_state_machine.c second; accept partial coverage initially |
| R6 | `concord_harness` is novel infrastructure (no prior art, no reference impl) | Stage 3 integration risk; firmware engineers unfamiliar with API | Medium | Unit test the module thoroughly (F37); build a minimal demo app for validation; write comprehensive API docs (D07); have infra team write the first `concord_harness.c` for Alpha |
| R7 | UART0 conflict: app kills UART0 RX for power savings (`NRF_UARTE0->TASKS_STOPRX = 1` in app.c) | Stage 3 harness transport completely broken; no shell commands possible | High | Must resolve before Sprint 4; add `#ifdef CONFIG_CONCORD_HARNESS` guard in app.c (F23); this is item #8 in arch-stage3 Section 9 open questions |
| R8 | Cross-repo build (driver push triggers alpha_fw build) adds complexity to build service | Build service scope creep; submodule override logic is tricky | Medium | Implement direct-repo builds first (Stage 1a interface tests); add cross-repo logic as a second phase; use `west manifest --override` or `git submodule set-url` approach from doc-09 |
| R9 | MTIB V2 gRPC API compatibility with new validation node hardware | Flash, UART, power measurement may behave differently on new MTIB nodes | Low | H11 validation step catches this; test each RPC individually before running full test suite; MTIB server v2 at `/home/mateo/work/concord/concord/apps/edge/mtib-server-v2/` is the reference |
| R10 | Frontend dashboard (I44-I47, 44h) may be deprioritized | No visibility into pipeline status for non-CLI users | Low | Dashboard is not on the critical path; can use `kubectl` and MinIO browser as interim; defer to after Stage 2 is operational |
| R11 | `alpha_state_t` type duplication between .c and .h (cohesion-review question 8.1/3.1) | Risk of divergence between test-visible type and production-visible type | Medium | Resolve during Sprint 1 (F19): move typedef unconditionally to header; avoids `#ifdef CONFIG_ZTEST` workaround that gets removed later for Stage 3 |

## Appendix C: Existing Infrastructure Inventory

Components that already exist and are leveraged by the validation pipeline.
These are NOT in the BOM (no work required) but are dependencies.

### C.1 Concord Monorepo Existing Components

| Component | Path | Used By |
|-----------|------|---------|
| HTTP API (Flask) | `/home/mateo/work/concord/concord/apps/backend/http-api/` | I01 extends this |
| K8s operator | `/home/mateo/work/concord/concord/apps/backend/operator/` | Reference for K8s patterns |
| Prisma ORM | `/home/mateo/work/concord/concord/prisma/schema.prisma` | I03 extends this |
| Frontend (Svelte) | `/home/mateo/work/concord/concord/apps/frontend/concord-app-svelte/` | I44-I47 extend this |
| MTIB client v2 | `/home/mateo/work/concord/concord/libs/python/corekinect/mtib_client/v2/` | I10 wraps this |
| CoreCloud client | `/home/mateo/work/concord/concord/libs/python/corekinect/core_cloud/` | I18 wraps this |
| InfluxDB client | `/home/mateo/work/concord/concord/apps/backend/http-api/src/services/influxdb/` | I16 uses this |
| MinIO storage client | `/home/mateo/work/concord/concord/apps/backend/http-api/src/services/storage/client.py` | I16 uses this |
| Validation config service | `/home/mateo/work/concord/concord/apps/backend/http-api/src/services/validation/config.py` | I01 extends this |
| Auth services (JWT, CoreCloud, Google) | `/home/mateo/work/concord/concord/apps/backend/http-api/src/services/auth/` | I01 uses this |
| K8s client service | `/home/mateo/work/concord/concord/apps/backend/http-api/src/services/kubernetes/client.py` | I01, I02 use this |
| Helm chart | `/home/mateo/work/concord/concord/deploy/helm/concord/` | I32-I36 extend this |
| MTIB server v2 | `/home/mateo/work/concord/concord/apps/edge/mtib-server-v2/` | Deployed on edge nodes |
| MTIB V2 protobuf definitions | `/home/mateo/work/concord/concord/libs/protocols/mtib_v2/` | I10 depends on these |

### C.2 Firmware Existing Components

| Component | Path | Used By |
|-----------|------|---------|
| Alpha firmware source | `/home/mateo/work/firmware/alpha_fw/src/app/` | F17-F24 modify this |
| Alpha state machine | `/home/mateo/work/firmware/alpha_fw/src/app/alpha_state_machine.c` | F17, F20 test target |
| Motion state machine | `/home/mateo/work/firmware/alpha_fw/src/app/motion_state_machine.c` | F18, F20 test target |
| Existing LSM6DSO driver (reference) | `/home/mateo/work/firmware/alpha_fw/lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/` | F05 references this |
| Alpha B0 board definition | `/home/mateo/work/firmware/alpha_fw/ck_boards/current/boards/corekinect/alpha_b0/` | F38, F41 reference this |
| Alpha build script | `/home/mateo/work/firmware/alpha_fw/build_all.sh` | F27 references this |
| Alpha prj.conf | `/home/mateo/work/firmware/alpha_fw/prj.conf` | F21 references this |

### C.3 Cluster Infrastructure

| Component | Status | Used By |
|-----------|--------|---------|
| K3s cluster (3 servers + 3 agents) | Operational | I02, I04 run here |
| PostgreSQL | Operational | I03 schema lives here |
| MinIO | Operational | I16 uploads here |
| InfluxDB | Operational | I16 pushes metrics here |
| Vault | Operational | I35 stores secrets here |
| MTIB edge nodes (manufacturing) | Operational | Separate from validation nodes |
| Container registry (containers.ad.corekinect.com) | Operational | I27-I31 push images here |
| Bitbucket (corekinect org) | Operational | I10b receives webhooks from here |

### C.4 MTIB V2 gRPC API (Existing RPCs)

All 71 RPCs are available. The validation pipeline uses a subset:

| RPC | Used By Stage(s) | Purpose |
|-----|-------------------|---------|
| `FlashProgram` | 2, 3, 4 | Flash test/instrumented/production firmware |
| `UartStream` | 2, 3, 4 | Bidirectional UART for ztest markers, shell commands, device logs |
| `PowerMeasure` | 2, 3, 4 | Continuous current measurement for power profiling |
| `GpioSet` | 2, 4 | Relay control (sensor power, charger, button) |
| `GpioRead` / `GpioStream` | 2 | Optional interrupt timing observation |
| `DutPowerEnable` / `DutPowerDisable` | 2, 3, 4 | MCU power control |
| `BLE` | 4 | BLE advertising verification (PRDTST comms tests) |
