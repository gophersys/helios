# System Implementation BOM: The Complete Validation Platform

> Comprehensive inventory of every component, interface agreement, and integration
> point required to implement the full Concord validation system — from Stage 1
> software tests through Stage 4 product validation, including manufacturing
> integration, FUOTA lifecycle testing, and CoreCloud backend connectivity.
>
> **Generated**: 2026-02-26
> **Scope**: All stages (1-4), manufacturing, FUOTA, all repositories, all interfaces
> **Companion to**: `bom-validation-pipeline.md` (component-level tracking)
> **Source documents**: 00, 09, stage3, stage4, fuota-flow, test-runner-stack,
> corecloud-architecture, alpha-manufacturing-research

---

## 1. How This Document Differs from the Component BOM

The component BOM (`bom-validation-pipeline.md`) tracks ~100 individual deliverables
with hours, owners, and dependency chains — the sprint-planning view.

This document is the **system-level view**. It answers:
- What are the clearly defined interface agreements between system components?
- How do all the moving pieces compose into a working whole?
- What exists today (production code), what needs adaptation, and what is entirely new?
- If we were to implement every stage for the entire system, what does the full picture look like?

The organizing principle here is **interfaces and integration boundaries**, not
individual file deliverables. Components that share an interface are grouped
together. The goal is to see the system collectively — every connection point,
every contract, every domain.

### Status Legend

| Status   | Meaning |
|----------|---------|
| `PROD`   | In production today. Battle-tested in manufacturing or existing services. |
| `EXISTS` | Code exists and works. May need minor adaptation for validation use cases. |
| `ADAPT`  | Exists but needs structural changes for validation (new wrappers, new patterns). |
| `NEW`    | Does not exist. Must be created from scratch. |
| `BLOCKED`| Depends on an external team (CoreCloud backend, firmware) for resolution. |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  CONCORD PLATFORM                                                                    │
│                                                                                      │
│  ┌──────────────┐  REST   ┌──────────────────┐  REST/K8s  ┌────────────────────┐    │
│  │   Frontend    │◄───────►│    HTTP API       │◄──────────►│ Pipeline Controller│    │
│  │  (SvelteKit)  │         │    (Flask)        │            │   (K8s Jobs)       │    │
│  └──────────────┘         └────────┬─────────┘            └────────┬───────────┘    │
│                                     │                               │                │
│                              ┌──────┴──────┐                 ┌──────┴──────┐         │
│                              │  Prisma ORM  │                 │ Build Service│         │
│                              │ (PostgreSQL)  │                 │  (west build)│         │
│                              └─────────────┘                 └─────────────┘         │
│                                                                                      │
├──────────────────────────────── K8s Job Boundary ───────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐     │
│  │  Test Pod (per-DUT K8s Job)                                                  │     │
│  │                                                                               │     │
│  │  ┌─────────────────────────────────────────────────────────────────────┐     │     │
│  │  │  TestContext                                                         │     │     │
│  │  │                                                                     │     │     │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │     │     │
│  │  │  │ CloudClient   │  │ MtibV2Client │  │  FixtureController     │   │     │     │
│  │  │  │ (CoreCloud)   │  │ (MTIB gRPC)  │  │  (profile → pins)     │   │     │     │
│  │  │  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘   │     │     │
│  │  │         │                  │                        │               │     │     │
│  │  │  ┌──────┴────┐  ┌────────┴────────┐  ┌───────────┴──────────┐   │     │     │
│  │  │  │ PowerProf  │  │  UartDemuxer    │  │  HarnessTransport   │   │     │     │
│  │  │  │            │  │                  │  │  (Stage 3 only)     │   │     │     │
│  │  │  └────────────┘  └─────────────────┘  └────────────────────┘   │     │     │
│  │  └─────────────────────────────────────────────────────────────────┘     │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                      │
├──────────────────────────────── Network Boundary ───────────────────────────────────┤
│                                                                                      │
│  ┌────────────────┐        ┌────────────────┐        ┌─────────────────────────┐    │
│  │ CoreCloud       │        │ MTIB V2 Server │        │ CoreCloud Backend       │    │
│  │ PostgreSQL      │        │ (71 gRPC RPCs) │        │ (REST API, FUOTA mgmt)  │    │
│  │ (VAL_1_0 env)   │        │ (Verdin node)  │        │ (External)              │    │
│  └────────────────┘        └───────┬────────┘        └─────────────────────────┘    │
│                                     │                                                │
│                              ┌──────┴──────────────────────┐                         │
│                              │ Physical Hardware             │                         │
│                              │                               │                         │
│                              │  ┌─────────────────────────┐ │                         │
│                              │  │ DUT (Alpha B0 / Sigma5)  │ │                         │
│                              │  │ nRF52840 + nRF9151       │ │                         │
│                              │  └─────────────────────────┘ │                         │
│                              │  ┌─────────────────────────┐ │                         │
│                              │  │ Fixture Board             │ │                         │
│                              │  │ GPIO, ADC, Motor, SWD    │ │                         │
│                              │  └─────────────────────────┘ │                         │
│                              └──────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Interface Agreements

The system has **seven primary interface boundaries**. Each boundary defines a
contract between two components. Understanding these contracts is how the system
composes into a working whole.

### 3.1 MTIB gRPC Interface

**Between**: Test Pod ↔ MTIB V2 Server (edge node)
**Protocol**: gRPC (protobuf)
**Status**: `PROD`

```
┌──────────────┐      gRPC (50052)      ┌──────────────┐
│ MtibV2Client │ ◄───────────────────► │ MTIB V2      │
│ (Python)     │                        │ Server       │
│              │  71 RPCs across        │ (Python)     │
│              │  17 handlers           │              │
└──────────────┘                        └──────────────┘
```

| Aspect | Detail |
|--------|--------|
| Proto definition | `libs/protocols/mtib_v2/` |
| Python client | `libs/python/corekinect/mtib_client/v2/` |
| Server | `apps/edge/mtib-server-v2/src/` |
| Error convention | Go-style: `Optional[str]` for errors, `Tuple[Optional[str], T]` for values |
| Auth | None (cluster-internal, node IP trusted) |
| Connection pattern | `MtibV2Client(ClientConfig(net=NetConfig(addr=host, port=50052)))` then `.connect()` |

**RPC categories used by validation**:

| Category | RPCs | Stage | Status |
|----------|------|-------|--------|
| Power | `PowerEnable`, `PowerDisable`, `PowerMeasure`, `PowerStream` | 2,3,4 | PROD |
| Flash | `DebugConnect`, `FlashProgram`, `FlashVerify`, `DebugDisconnect` | 2,3,4 | PROD |
| UART | `UartOpen`, `UartClose`, `UartStream` | 2,3,4 | PROD |
| GPIO | `GpioConfig`, `GpioWrite`, `GpioRead`, `GpioStream` | 2,4 | PROD |
| Motor | `MotorOutput`, `MotorStop` | 4 | PROD (unused in mfg) |
| ADC | `AdcRead`, `AdcStream` | 2,4 | PROD |
| BLE | `BleSetup`, `BleStartScan`, `BleAdvDecode` | 4 (future) | PROD (unused in mfg) |
| I2C | `I2cTransfer` | 4 (NFC reader) | PROD (unused in mfg) |

**What validation adds**: No new RPCs needed. The validation stack adds
_composition_ on top of existing RPCs: FixtureController (abstract actions →
MTIB calls) and UartDemuxer (prefix-based UART routing).

### 3.2 CoreCloud SDK Interface

**Between**: Test Pod ↔ CoreCloud PostgreSQL + REST API
**Protocol**: SQLAlchemy (DB) + HTTPS (REST)
**Status**: `EXISTS` (DB reads), `ADAPT` (needs CloudClient polling wrappers)

```
┌──────────────┐    SQLAlchemy     ┌──────────────┐
│ CloudClient   │ ◄──────────────► │ PostgreSQL    │
│ (Python)     │    via SSH/direct │ (VAL_1_0)    │
│              │                    │              │
│              │    HTTPS (REST)   ┌──────────────┐
│              │ ◄──────────────► │ CoreCloud     │
│              │                    │ REST API     │
└──────────────┘                    └──────────────┘
```

| Aspect | Detail |
|--------|--------|
| SDK location | `libs/python/corekinect/core_cloud/` |
| DB interface | `db_interface.py` — SQLAlchemy sessions, SSH tunnel, `CoreCloudDBInterface` context manager |
| REST interface | `api_interface.py` — token auth, rate limiting, `CoreCloudRestInterface` singleton |
| ORM models | `db_orm_v1_0.py` — PostgreSQL tables, including FUOTA tables |
| Message defs | `msg_def_v1_0.py` — `MsgBase` (reads), `ConfMsgBase` (reads + writes) |
| Namespace config | Env vars: `{NS}_DB_HOST`, `{NS}_DB_NAME`, `{NS}_API_KEY`, etc. |

**Message types available for validation**:

| Class | UID | Base | DB Read | REST Write | Validation Use |
|-------|-----|------|---------|------------|---------------|
| `BootMsgV2` | 548 | `MsgBase` | Yes | No | FUOTA boot reason, FW version verification |
| `PositionMsgV6` | 556 | `MsgBase` | Yes | No | Motion, GNSS, config, power state |
| `BiometricDataMsg` | 557 | `MsgBase` | Yes | No | On-skin detection, heart rate, SpO2 |
| `NetworkStatusMsgV4` | 512 | `MsgBase` | Yes | No | LTE connectivity, signal strength |
| `AlphaHwFailureMsg` | 559 | `MsgBase` | Yes | No | Hardware failure detection |
| `GPSConfMsg` | 524 | `ConfMsgBase` | Yes | `.send_via_rest()` | GNSS config delivery |
| `GroundModeConfigV2` | 538 | `MsgBase` | Yes | **No** (not ConfMsgBase) | **BLOCKED** — 18 tests deferred |
| `DeviceMessageLog` | — | `MsgBase` | Yes | No | Generic message audit trail |

**FUOTA ORM tables** (exist in `db_orm_v1_0.py`):

| Table | Status | Used For |
|-------|--------|----------|
| `Fuotaplanstbl` | EXISTS | FUOTA plan definition (create/read) |
| `Fuotaprogresshistorytbl` | EXISTS | Per-device FUOTA progress tracking |
| `Fuotasettingsperdevicetypetbl` | EXISTS | Device type FUOTA settings |

**What validation adds**: `CloudClient` class — thin polling wrappers
(`wait_for_position()`, `wait_for_boot()`, `wait_for_biometric()`) + FUOTA plan
management (`create_fuota_plan()`, `wait_for_fuota_completion()`). See
`test-runner-stack.md` Section 4 for full API design.

### 3.3 Concord HTTP API Interface

**Between**: Frontend/Build Service/Pipeline Controller ↔ Flask HTTP API
**Protocol**: REST (JSON)
**Status**: `EXISTS` (base API), `ADAPT` (validation endpoints needed)

```
┌──────────────┐                    ┌──────────────┐
│ Frontend      │                    │              │
│ (SvelteKit)   │    REST/JSON       │              │
│              │ ◄──────────────►   │  HTTP API    │
│              │                    │  (Flask +    │
├──────────────┤                    │   Blueprints) │
│ Build Service │                    │              │
│ Pipeline Ctrl │    REST/JSON       │              │
│              │ ◄──────────────►   │              │
└──────────────┘                    └──────────────┘
```

**Existing endpoints relevant to validation**:

| Endpoint Group | Path Pattern | Status | Purpose |
|----------------|-------------|--------|---------|
| Validation tests | `POST /v2/validation/tests/run` | EXISTS | Trigger test execution |
| Test results | `GET /v2/validation/tests/{id}/results` | EXISTS | Fetch test results |
| Fixtures | `GET/POST/PUT /v2/fixtures/` | EXISTS | Fixture CRUD |
| MTIB nodes | `GET /v2/mtib/nodes/` | EXISTS | Node listing |
| MTIB commands | `POST /v2/mtib/nodes/{id}/{command}` | EXISTS | Proxy commands to MTIB |
| Observability | `GET /v2/observability/` | EXISTS | Metrics, health |
| K8s resources | `GET /v2/k8s/{resource}` | EXISTS | Cluster resources |
| Firmware catalog | `GET /v2/catalog/firmware/` | EXISTS | Firmware builds |
| Deployments | `GET/POST /v2/deployments/` | EXISTS | Deployment CRUD |
| ICLE devices | `GET /v2/icle/devices/` | EXISTS | ICLE device management |

**New endpoints needed for validation pipeline**:

| Endpoint | Status | Purpose |
|----------|--------|---------|
| `POST /v2/validation/pipelines/trigger` | NEW | Trigger full pipeline (webhook + manual) |
| `GET /v2/validation/pipelines/{id}` | NEW | Pipeline status, stages, jobs |
| `GET /v2/validation/pipelines/{id}/stages` | NEW | Stage-by-stage results |
| `POST /v2/validation/builds/trigger` | NEW | Trigger firmware build |
| `GET /v2/validation/builds/{id}` | NEW | Build status, artifacts |
| `GET /v2/validation/nodes/capabilities` | NEW | MTIB node capability matching |
| `POST /v2/validation/jobs/{id}/results` | NEW | Test pod reports results back |

**Prisma schema** — existing models that validation uses:

| Model | Status | Used For |
|-------|--------|----------|
| `Test` | EXISTS | Test definitions |
| `TestExecution` | EXISTS | Test run records |
| `TestResult` | EXISTS | Per-test outcomes |
| `Session` | EXISTS | Manufacturing sessions (reference) |
| `Device` | EXISTS | DUT inventory |
| `Node` | EXISTS | MTIB node records |
| `Fixture` | EXISTS | Fixture definitions |
| `FixtureSlot` | EXISTS | Slot assignments |
| `FirmwareBuild` | EXISTS | Build records |
| `Deployment` | EXISTS | Deployment tracking |
| `IcleDevice` | EXISTS | ICLE devices |
| `ValidationPipeline` | NEW | Pipeline state machine |
| `PipelineStage` | NEW | Stage tracking (1-4) |
| `PipelineJob` | NEW | Individual K8s Job records |
| `SubmoduleMapping` | NEW | Cross-repo trigger routing |

### 3.4 K8s Job Interface

**Between**: Pipeline Controller ↔ K8s API ↔ Test Pods
**Protocol**: K8s API (Job creation, ConfigMap/Secret injection)
**Status**: `ADAPT` (K8s client exists, Job template exists, controller is NEW)

```
┌──────────────┐   K8s API    ┌──────┐   Pod Spec   ┌──────────────┐
│ Pipeline      │ ───────────►│ K8s  │ ────────────►│ Test Pod     │
│ Controller    │              │ API  │              │ (per-DUT)    │
│              │◄─────────── │      │              │              │
│ (Job watcher)│  Job status  │      │              │ Env vars:    │
└──────────────┘              └──────┘              │ MTIB_HOST    │
                                                     │ DEVICE_ID    │
                                                     │ FIRMWARE_HEX │
                                                     │ PRODUCT      │
                                                     │ BUILD_VARIANT│
                                                     └──────────────┘
```

| Aspect | Detail |
|--------|--------|
| Job template | `apps/backend/http-api/assets/templates/validation_job.yaml` (EXISTS) |
| K8s client | `apps/backend/http-api/src/services/kubernetes/client.py` (EXISTS) |
| Node selector | `product=alpha` label on MTIB nodes |
| Pod anti-affinity | One test pod per MTIB node |
| Env injection | MTIB host, device ID, firmware path, product, variant, CoreCloud creds |
| Result reporting | Test pod POSTs results to HTTP API on completion |
| Artifact storage | MinIO upload from pod, path: `validation/pipelines/{id}/stages/{n}/` |

### 3.5 Build Service Interface

**Between**: Pipeline Controller ↔ Build Service
**Protocol**: gRPC or internal REST (TBD)
**Status**: `NEW`

The build service compiles firmware from source and uploads artifacts to MinIO.
It reads `.concord/build.yaml` from the firmware repo for build configuration.

| Aspect | Detail |
|--------|--------|
| Input | Git repo URL + commit SHA + build variant |
| Output | Compiled `.hex` file in MinIO |
| Build system | `west build --sysbuild` for Zephyr firmware |
| Cross-repo | `west manifest --override` for submodule overrides |
| Caching | PVCs for ccache, west modules |

### 3.6 Frontend Interface

**Between**: SvelteKit SPA ↔ HTTP API
**Protocol**: REST (JSON), design token styling
**Status**: `EXISTS` (framework), `NEW` (validation pages)

**Existing pages** (relevant to validation):

| Page | Status | Purpose |
|------|--------|---------|
| Test results list | EXISTS | Manufacturing test results |
| MTIB node view | EXISTS | Node status and commands |
| ICLE device view | EXISTS | Power monitoring devices |
| Fixture management | EXISTS | Fixture CRUD |
| Firmware catalog | EXISTS | Firmware build listing |
| Deployment tracking | EXISTS | Deployment status |

**New pages needed**:

| Page | Status | Purpose |
|------|--------|---------|
| Validation pipeline list | NEW | All pipeline runs, status, progress |
| Pipeline detail view | NEW | Stages, jobs, results per pipeline |
| Power trend charts | NEW | InfluxDB-backed power measurements |
| Manual trigger UI | NEW | Kick off pipeline or individual stage |

### 3.7 Manufacturing ↔ Validation Interface

**Between**: Manufacturing test scripts ↔ Validation pipeline
**Protocol**: Shared libraries (MtibV2Client, ShellCommandHelper, CoreCloud SDK)
**Status**: `PROD` (manufacturing), `ADAPT` (validation reuses same libraries)

Manufacturing and validation share the same bottom layers but diverge at the
orchestration level:

```
MANUFACTURING                        VALIDATION
┌──────────────────────┐            ┌──────────────────────┐
│ gRPC Operator         │            │ Pipeline Controller   │
│ (multi-node parallel) │            │ (K8s Jobs, per-DUT)  │
└───────────┬──────────┘            └───────────┬──────────┘
            │                                    │
            ▼                                    ▼
┌──────────────────────┐            ┌──────────────────────┐
│ Test/TestStep         │            │ TestContext            │
│ ThreadPoolExecutor    │            │ (single DUT)          │
│ usr_data[node]        │            │ ctx.mtib/cloud/fix    │
└───────────┬──────────┘            └───────────┬──────────┘
            │                                    │
            ▼                                    ▼
┌───────────────────────────────────────────────────────────┐
│ SHARED LAYER                                               │
│                                                             │
│  MtibV2Client    ShellCommandHelper    CoreCloud SDK       │
│  boot_and_lock_shells()    AlphaAppShellCommands           │
│  CommsShellCommands        TestStepResult                  │
└───────────────────────────────────────────────────────────┘
```

| Shared Component | Mfg Uses | Validation Uses | Status |
|-----------------|----------|-----------------|--------|
| `MtibV2Client` | Directly in test steps | Via `TestContext.mtib` | PROD |
| `boot_and_lock_shells()` | POST test step 0 | `TestContext.power_on()` → shell init | PROD |
| `AlphaAppShellCommands` | `post`, `config_show` | Stage 3 harness, Stage 4 diagnostics | PROD |
| `CommsShellCommands` | SIM status, IMEI reads | Network diagnostics | PROD |
| CoreCloud SDK | Not used in mfg | `CloudClient` wrappers | EXISTS |
| `TestStep`/`Test` framework | Full mfg execution | Result/reporting pattern only | ADAPT |
| Firmware `.hex` files | Flashed via J-Link | Same, from MinIO instead of local | PROD |

---

## 4. Domain: Firmware Validation (Stages 1-4)

### 4.1 Stage 1: Software Tests (native_sim)

Pure software validation. No hardware, no network, no CoreCloud. Tests run on
`native_sim` target via Zephyr's `twister` runner.

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| `accel_drv` clean branch | `accel_drv/` (external repo) | NEW | Nuke legacy, restructure |
| LSM6DSO stub driver | `accel_drv/stubs/` | NEW | For `native_sim` tests |
| DTS stub binding | `accel_drv/dts/bindings/ck,lsm6dso-stub.yaml` | NEW | |
| Interface contract tests | `accel_drv/tests/interface/` | NEW | 12 Ztest cases |
| Alpha app stub tests | `alpha_fw/tests/app/` | NEW | ~15 module stubs needed |
| `alpha_state_machine` getters | `alpha_fw/src/app/` | ADAPT | `#ifdef CONFIG_ZTEST` guards |
| `.concord/pipeline.yaml` | Each firmware repo | NEW | Pipeline definition |
| `.concord/build.yaml` | Each firmware repo | NEW | Build configuration |

**Effort**: ~130h | **Dependencies**: None (first stage, no HW)
**Interface touched**: Build Service (compiles), Pipeline Controller (orchestrates)

### 4.2 Stage 2: Driver Hardware Tests

First stage that touches real hardware. A dev-kit board on an MTIB node runs
hardware-level driver tests.

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| LSM6DSO driver implementation | `accel_drv/drivers/lsm6dso/src/` | NEW | 40h — dominant effort |
| DTS real binding | `accel_drv/dts/bindings/ck,lsm6dso.yaml` | NEW | |
| HW test firmware | `accel_drv/tests/lsm6dso/` | NEW | Ztest on real SPI |
| `test_spec.yaml` | `accel_drv/tests/lsm6dso/test_spec.yaml` | NEW | Pass/fail criteria |
| Dev-kit board definition | `ck_boards/.../devkit_nrf52840_lsm6dso_spi/` | NEW | |
| `ztest_parser.py` | Test runner | NEW | Parse UART Ztest output |
| `power_profiler.py` | Test runner | NEW | Continuous measurement |
| `test_spec_evaluator.py` | Test runner | NEW | Spec vs result matching |
| `fixture_controller.py` | Test runner | NEW | Abstract → pin mapping |
| Dev-kit fixture wiring | Physical | NEW (HW) | nRF52840-DK + LSM6DSO |
| Power isolation circuit | Physical | NEW (HW) | Per-sensor relay + sense |
| MTIB cable assembly | Physical | NEW (HW) | SWD, UART, power, GPIO |

**Effort**: ~230h | **Dependencies**: Stage 1 infra, dev-kit hardware
**Interfaces touched**: MTIB gRPC (power, flash, UART, GPIO, ADC)

### 4.3 Stage 3: Integration Tests (concord_harness)

Instrumented firmware build with `concord_harness` Zephyr module. Software-driven
stimulus via UART shell commands. Internal state observation that hardware tests
cannot do.

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| `concord_harness` module | `concord_harness/` (new repo) | NEW | GETTER/SETTER/INJECT/EVENT macros |
| `concord_harness.h` (public API) | `concord_harness/zephyr/include/` | NEW | 8h |
| `concord_shell.c` | `concord_harness/zephyr/src/` | NEW | Shell command handlers |
| `concord_registry.c` | `concord_harness/zephyr/src/` | NEW | STRUCT_SECTION lookup |
| `concord_emit.c` | `concord_harness/zephyr/src/` | NEW | Event emission (k_msgq) |
| Alpha harness declarations | `alpha_fw/src/concord_harness.c` | NEW | Binds getters/setters to FW state |
| `#ifdef` guards in alpha_fw | `alpha_fw/src/app/app.c` + others | ADAPT | Kill UART0 RX guard |
| `CONCORD_EMIT()` calls | `alpha_fw/src/app/` state machines | ADAPT | Event emission points |
| `harness_client.py` | Test runner | NEW | Shell protocol for harness |
| `cloud_client.py` | Test runner | NEW | CloudClient (optional in S3) |
| `UartDemuxer` | Test runner | NEW | Prefix routing: harness vs logs |
| `HarnessTransport` | Test runner | NEW | Harness shell protocol |
| Integration test modules | `alpha_fw/.concord/tests/integration/` | NEW | ~25 test functions |
| Alpha product fixture | Physical | NEW (HW) | SWD, UART, power, GPIO |

**Effort**: ~194h | **Dependencies**: Stage 2 infra, Alpha HW, concord_harness module
**Interfaces touched**: MTIB gRPC (power, flash, UART), CoreCloud (optional), Harness UART protocol

### 4.4 Stage 4: Product Validation (black-box)

Production firmware on real hardware. No instrumentation. All verification through
external observation: CoreCloud messages, MTIB power/GPIO/ADC measurements,
fixture-driven stimulus. The PRD test suite (89 PRDTST tests).

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| `TestContext` | Test runner | NEW | Composes all three pillars |
| `CloudClient` | Test runner | NEW | Polling wrappers over SDK |
| `FixtureController` | Test runner | NEW (if not built in S2) | Abstract → MTIB pins |
| `PowerProfiler` | Test runner | EXISTS/ADAPT (from S2) | Add trace storage |
| `ValidationRunner` | Test runner | NEW | pytest-based discovery + TestContext fixture |
| `alpha_validation_spec.yaml` | Test runner | NEW | 89 PRDTST tests mapped |
| `FuotaPlanBuilder` | Test runner | NEW | Create FUOTA plans via DB/REST |
| `FuotaMonitor` | Test runner | NEW | Poll FUOTA progress |
| `nfc_client.py` | Test runner | NEW | NFC reader integration |
| FUOTA validation flow | Test runner | NEW | 12-step orchestration |
| Fixture peripherals | Physical | NEW (HW) | Button, on-skin, charger relay, peltier, LED sensor, motion actuator |

**Effort**: ~158h | **Dependencies**: Stage 3 infra, CoreCloud access, fixture peripherals
**Interfaces touched**: All — MTIB gRPC, CoreCloud SDK+REST, Fixture profiles, K8s Jobs

### 4.5 PRDTST Test Coverage by Stage

| Domain | Total | Stage 3 | Stage 4 Commit | Stage 4 Weekly | Notes |
|--------|-------|---------|----------------|----------------|-------|
| Power / Runtime | 7 | 2 | 3 | 7 | Endurance (72h) weekly only |
| Config Values | 18 | 6 | 12 | 18 | **18 BLOCKED** on GroundModeConfigV2 |
| Motion Detection | 5 | 3 | 5 | 5 | Needs motor/actuator |
| Charging / BMS | 29 | 4 | 8 | 29 | Full charge = 4h, weekly only |
| Environmental | 7 | 3 | 4 | 7 | Extreme temp = weekly only |
| GNSS | 7 | 0 | 2 | 7 | Indoor — needs GPS simulator |
| On-Skin / Biometric | 3 | 2 | 3 | 3 | Needs electrode simulation |
| Button / SOS / Haptic | 9 | 0 | 5 | 9 | Needs button actuator |
| NFC | 1 | 0 | 1 | 1 | Needs NFC reader |
| FUOTA | 1 | 0 | 0 | 1 | Weekly only (12-step flow) |
| VSM / IPC | 1 | 1 | 0 | 1 | Stage 3 via harness only |
| Cloud Messages | 1 | 0 | 0 | 1 | Weekly (needs temp chamber) |
| **Total** | **89** | **21** | **43** | **89** | |

---

## 5. Domain: FUOTA Validation

The 12-step FUOTA validation flow exercises every firmware transition path on
real hardware. Full details in `stage4-fuota-validation-flow.md`.

### 5.1 FUOTA Components

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| FUOTA ORM tables | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` | EXISTS | `Fuotaplanstbl`, `Fuotaprogresshistorytbl`, `Fuotasettingsperdevicetypetbl` |
| DB query methods (MsgBase) | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` | EXISTS | `.last()`, `.since_*()` for BootMsgV2 |
| `FuotaPlanBuilder` | Test runner | NEW | Plan creation logic |
| `FuotaMonitor` | Test runner | NEW | Progress polling |
| FUOTA flow orchestrator | Test runner | NEW | 12-step sequence logic |
| Mfg firmware `.hex` | `apps/firmware/products/alpha/alpha_mfg_fw` | EXISTS | Manufacturing baseline |
| Release firmware `.hex` | Build service output | NEW per build | Build service artifact |

### 5.2 FUOTA Flow Interface Dependencies

The 12-step FUOTA flow uses multiple interface boundaries:

| Step | Description | Interfaces Used |
|------|-------------|----------------|
| 1. Electrical test | Verify DUT health | MTIB (power, ADC) |
| 2. Flash mfg FW | J-Link flash | MTIB (flash, SWD) |
| 3. POST + personalization | Manufacturing checks | MTIB (UART, shell) |
| 4. FUOTA mfg → mfg (same ver) | Self-update test | CoreCloud (FUOTA plan, boot msg) |
| 5. Re-run POST | Verify HW after FUOTA | MTIB (UART, shell) |
| 6. FUOTA mfg → prod debug | Cross-variant update | CoreCloud (FUOTA plan, boot msg) |
| 7. Validation tests (debug) | Full PRDTST suite | All interfaces |
| 8. FUOTA debug → debug (same ver) | Self-update test | CoreCloud (FUOTA plan, boot msg) |
| 9. FUOTA debug → release | Final transition | CoreCloud (FUOTA plan, boot msg) |
| 10. Validation tests (release) | Full PRDTST suite | All interfaces |
| 11. Flash prev prod FW | Upgrade path baseline | MTIB (flash, SWD) |
| 12. Upgrade path test | Real-world update | CoreCloud (FUOTA plan, boot msg) |

### 5.3 FUOTA Open Questions

| # | Question | Impact | Status |
|---|----------|--------|--------|
| Q1 | Does a REST API exist for FUOTA plan creation? | Clean interface vs DB ORM writes | Ask CoreCloud team |
| Q2 | 5-minute cooldown between FUOTA completions — can it be shortened for testing? | Flow takes 2+ hours with cooldowns | Ask CoreCloud team |
| Q3 | How does the nRF9151 comms coprocessor FUOTA work? | Dual-MCU FUOTA must be tested separately | Ask firmware team |

---

## 6. Domain: Manufacturing Integration

Manufacturing tests are production-proven on Alpha and Sigma5 hardware. The
validation pipeline reuses the same libraries but with a different orchestration
model.

### 6.1 Manufacturing Components

| Component | Location | Status | Validation Reuse |
|-----------|----------|--------|-----------------|
| Alpha mfg test scripts | `apps/manufacturing/alpha/src/tests/` | PROD | Reference patterns, share libraries |
| Electrical test (10 steps) | `apps/manufacturing/alpha/src/tests/electrical/` | PROD | Step patterns → FixtureController |
| FW flash test (3 steps) | `apps/manufacturing/alpha/src/tests/fw_flash/` | PROD | Flash sequence → TestContext.flash_firmware() |
| POST test (10 steps) | `apps/manufacturing/alpha/src/tests/post/` | PROD | boot_and_lock_shells() pattern |
| ThetaFixtureConfig | `apps/manufacturing/alpha/src/tests/shared/config.py` | PROD | Pattern → FixtureProfile JSON |
| Test/TestStep framework | `libs/python/corekinect/test/` | PROD | TestStepResult reuse, execution model diverges |
| gRPC operator | `deploy/manufacturing/sigma5/operator-deployment.yaml` | PROD | Different model in validation (K8s Jobs) |
| Mfg firmware binaries | `apps/firmware/products/alpha/alpha_mfg_fw` | PROD | FUOTA baseline |

### 6.2 Manufacturing → Validation Traceability Gap

Today manufacturing and validation are disconnected systems. A device that passes
manufacturing POST has no automated link to its validation test history.

| Gap | What's Missing | Priority |
|-----|---------------|----------|
| Device lifecycle linking | Mfg session → validation pipeline run for same device | Medium (future) |
| POST result reuse | Stage 4 Step 1 (electrical) duplicates mfg POST checks | Low (different context) |
| Firmware build provenance | Mfg uses local `.hex`, validation uses MinIO artifact | High (need consistent source) |
| Personalization data | nRF9151 certs/keys needed for LTE → CoreCloud | High (FUOTA blocked without) |

---

## 7. Domain: CoreCloud Library

Full analysis in `corecloud-library-architecture.md`. Summary of what validation
needs from the CoreCloud SDK:

### 7.1 SDK Components

| Component | Status | Validation Need |
|-----------|--------|----------------|
| `db_interface.py` (PostgreSQL sessions) | PROD | CloudClient DB reads |
| `api_interface.py` (REST client) | PROD | Config delivery, FUOTA (if REST exists) |
| `msg_def_v1_0.py` (message classes) | PROD | All message reads |
| `db_orm_v1_0.py` (ORM models) | PROD | FUOTA table access |
| `msg_def_v0_9.py` (legacy MySQL) | PROD | Not needed for validation — v0.9 deadweight |
| `db_orm_v0_9.py` (legacy MySQL) | PROD | Not needed for validation — v0.9 deadweight |

### 7.2 CoreCloud Gaps for Validation

| Gap | Impact | Resolution Path |
|-----|--------|----------------|
| `GroundModeConfigV2` not `ConfMsgBase` | 18 config tests deferred | CoreCloud team adds REST endpoint |
| No `BiometricConfig` message class | Biometric config tests deferred | CoreCloud team adds UID + endpoint |
| No FUOTA plan creation API | Must write DB directly or ask for REST | CoreCloud team decision |
| No `wait_for_*` polling wrappers | Every test must implement polling | Build CloudClient (validation team) |
| v0.9/v1.0 dual code paths | Complexity, maintenance burden | Proposed: v1.0-only restructuring |
| SSH tunnel requirement for DB | Dev env complexity | Direct connection in VAL_1_0 |

---

## 8. Domain: Platform Services

Cross-cutting services that support all stages and domains.

### 8.1 Pipeline Controller

| Aspect | Detail | Status |
|--------|--------|--------|
| Core function | Watch firmware repos → trigger builds → create K8s Jobs → gate stages → report status | NEW |
| K8s integration | Create/watch Jobs, inject env vars + ConfigMaps | ADAPT (K8s client exists) |
| Stage gating | Stage N pass → unblock Stage N+1 | NEW |
| MTIB work queue | Match test requirements to MTIB node capabilities | NEW |
| Bitbucket integration | Commit status reporting, webhook handling | NEW |
| Effort | ~40h (core) + 24h (gating, matching, reporting) | |

### 8.2 Build Service

| Aspect | Detail | Status |
|--------|--------|--------|
| Core function | Clone repo → `west build` → upload `.hex` to MinIO | NEW |
| Build variants | Integration (harness), production debug, production release | NEW |
| Cross-repo builds | `west manifest --override` for submodule changes | NEW |
| Caching | PVCs for ccache, west modules | NEW |
| Effort | ~32h | |

### 8.3 Container Images

| Image | Content | Status | Stage |
|-------|---------|--------|-------|
| `concord-driver-test-runner` | Stage 2 test runner + MTIB client | NEW | 2 |
| `concord-integration-test-runner` | Stage 3 runner + harness client | NEW | 3 |
| `concord-validation-alpha` | Stage 4 runner + all clients | NEW | 4 |
| `concord-build-service` | West toolchain, ARM gcc, nRF tools | NEW | All |
| `concord-pipeline-controller` | Python + K8s client | NEW | All |

### 8.4 Helm / K8s Deployment

| Component | Status | Purpose |
|-----------|--------|---------|
| Pipeline controller Deployment | NEW | Long-running controller |
| Build service Deployment | NEW | Long-running build worker |
| PVC definitions (ccache, west) | NEW | Build caching |
| Vault secrets | ADAPT | Git SSH key, API keys, device creds |
| CronJob (weekly/nightly Stage 4) | NEW | Scheduled full-suite runs |
| Validation Job template | EXISTS | Test pod template |

### 8.5 Data Schemas

| Schema | Status | Purpose |
|--------|--------|---------|
| `pipeline.yaml` | NEW | Pipeline definition per firmware repo |
| `build.yaml` | NEW | Build configuration per firmware repo |
| `test_spec.yaml` | NEW | Pass/fail criteria for Stage 2 |
| `board_features.json` | NEW | Board capability descriptor |
| Fixture profile JSON | NEW | Per-node fixture wiring map |
| `alpha_validation_spec.yaml` | NEW | 89 PRDTST tests mapped to code |
| JUnit XML extensions | NEW | Power data, PRDTST ID mapping |

### 8.6 Artifact Storage (MinIO)

| Path Pattern | Content | Stage |
|-------------|---------|-------|
| `firmware/builds/{repo}/{commit}/` | Compiled `.hex` files | All |
| `validation/pipelines/{id}/stages/{n}/` | Test results, power traces, UART logs | 2,3,4 |
| `validation/pipelines/{id}/reports/` | JUnit XML, summary reports | All |
| `firmware/products/{product}/{variant}/` | Production firmware catalog | 4 |

### 8.7 Observability

| Component | Status | Purpose |
|-----------|--------|---------|
| InfluxDB (metrics) | EXISTS | Power measurement time series |
| MinIO (artifacts) | EXISTS | Firmware builds, test artifacts |
| PostgreSQL (Prisma) | EXISTS | Pipeline state, test results |
| Structured logging | EXISTS | API + test runner logs |
| Power trend charts | NEW | Frontend visualization |

---

## 9. Component Inventory: Exists vs Needs Building

### 9.1 Production-Ready (No Changes Needed)

| # | Component | Location | Used By |
|---|-----------|----------|---------|
| 1 | MTIB V2 Server (71 RPCs) | `apps/edge/mtib-server-v2/` | All HW stages |
| 2 | MtibV2Client (Python, mixin arch) | `libs/python/corekinect/mtib_client/v2/` | All HW stages |
| 3 | ShellCommandHelper + boot_and_lock_shells | `libs/python/corekinect/mtib_client/v2/client/shell.py` | Stages 3, 4 |
| 4 | AlphaAppShellCommands, CommsShellCommands | `libs/python/corekinect/mtib_client/v2/client/cmd_*.py` | Stages 3, 4 |
| 5 | CoreCloud DB Interface | `libs/python/corekinect/core_cloud/db_interface.py` | Stages 3, 4 |
| 6 | CoreCloud REST Interface | `libs/python/corekinect/core_cloud/api_interface.py` | Stage 4 |
| 7 | v1.0 Message Definitions | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` | Stages 3, 4 |
| 8 | v1.0 ORM Models (inc. FUOTA tables) | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` | Stage 4 |
| 9 | MTIB V2 Protobuf Definitions | `libs/protocols/mtib_v2/` | All HW stages |
| 10 | K3s Cluster (3 server + 3 agent) | Infrastructure | All stages |
| 11 | PostgreSQL (Concord DB) | Infrastructure | All stages |
| 12 | MinIO (object storage) | Infrastructure | All stages |
| 13 | InfluxDB (metrics) | Infrastructure | Stages 2, 3, 4 |
| 14 | Vault (secrets) | Infrastructure | All stages |
| 15 | Container Registry | `containers.ad.corekinect.com` | All stages |
| 16 | Manufacturing Test Scripts | `apps/manufacturing/alpha/src/tests/` | Reference patterns |
| 17 | TestStep/Test Framework | `libs/python/corekinect/test/` | Result patterns |
| 18 | Flask HTTP API Framework | `apps/backend/http-api/` | Extended for validation |
| 19 | SvelteKit Frontend Framework | `apps/frontend/concord-app-svelte/` | Extended for validation |
| 20 | Prisma ORM + Schema | `prisma/schema.prisma` | Extended for validation |
| 21 | Helm Charts | `deploy/helm/concord/` | Extended for validation |
| 22 | Mfg Firmware Binaries | `apps/firmware/products/alpha/` | FUOTA baseline |

### 9.2 Needs Adaptation

| # | Component | What Changes | Effort |
|---|-----------|-------------|--------|
| 1 | Prisma Schema | Add ValidationPipeline, PipelineStage, PipelineJob, SubmoduleMapping models | 8h |
| 2 | alpha_fw State Machine | Add `#ifdef CONFIG_ZTEST` getters, move types to headers | 5h |
| 3 | alpha_fw Harness Integration | `CONFIG_CONCORD_HARNESS` guards, `CONCORD_EMIT()` calls | 7h |
| 4 | HTTP API Routes | Add validation pipeline, build, and result endpoints | 16h |
| 5 | Helm Values | Add pipeline controller + build service deployments | 12h |
| 6 | Vault Secrets | Add Git SSH key, CoreCloud API keys, device credentials | 4h |
| 7 | K8s Job Template | Update env injection, ConfigMap mounting | 4h |

### 9.3 Must Be Built From Scratch

| # | Component | Category | Effort | Stage |
|---|-----------|----------|--------|-------|
| 1 | `accel_drv` clean branch + stubs | Firmware | 15h | 1 |
| 2 | Interface contract tests | Firmware | 12h | 1 |
| 3 | Alpha app stub tests (~15 modules) | Firmware | 24h | 1 |
| 4 | LSM6DSO driver implementation | Firmware | 40h | 2 |
| 5 | HW test firmware + test_spec.yaml | Firmware | 20h | 2 |
| 6 | Dev-kit board definition | Firmware | 8h | 2 |
| 7 | `concord_harness` Zephyr module | Firmware/Infra | 41.5h | 3 |
| 8 | Alpha harness declarations | Firmware | 16h | 3 |
| 9 | Integration test Python modules | Firmware/Infra | 24h | 3 |
| 10 | Pipeline controller | Infra | 40h | All |
| 11 | Build service | Infra | 32h | All |
| 12 | Pipeline trigger API | Infra | 12h | All |
| 13 | `ztest_parser.py` | Infra | 8h | 2 |
| 14 | `power_profiler.py` | Infra | 12h | 2,3,4 |
| 15 | `test_spec_evaluator.py` | Infra | 8h | 2 |
| 16 | `fixture_controller.py` | Infra | 12h | 2,3,4 |
| 17 | `report_generator.py` | Infra | 8h | 2,3,4 |
| 18 | `artifact_manager.py` | Infra | 6h | 2,3,4 |
| 19 | `harness_client.py` | Infra | 12h | 3 |
| 20 | `cloud_client.py` (CloudClient) | Infra | 8h | 3,4 |
| 21 | `TestContext` | Infra | 8h | 3,4 |
| 22 | `UartDemuxer` | Infra | 8h | 3,4 |
| 23 | `HarnessTransport` | Infra | 8h | 3 |
| 24 | `ValidationRunner` (pytest-based) | Infra | 16h | 4 |
| 25 | `FuotaPlanBuilder` + `FuotaMonitor` | Infra | 8h | 4 |
| 26 | FUOTA flow orchestrator (12-step) | Infra | 12h | 4 |
| 27 | `nfc_client.py` | Infra | 6h | 4 |
| 28 | `alpha_validation_spec.yaml` (89 tests) | Infra/QA | 24h | 4 |
| 29 | 5 Container images | Infra | 18h | All |
| 30 | Helm deployments (controller, build svc) | Infra | 12h | All |
| 31 | CronJob definitions | Infra | 4h | 4 |
| 32 | 7 Data schemas | Infra | 13h | All |
| 33 | 4 Frontend pages | Frontend | 44h | All |
| 34 | `.concord/` configs (pipeline.yaml, build.yaml) | Infra | 14h | All |
| 35 | Dev-kit fixture (wiring, power, cables) | HW | 28h | 2 |
| 36 | Alpha product fixture + peripherals | HW | 36h | 3,4 |
| 37 | MTIB node registration (2 nodes) | Infra | 4h | 2,3 |
| 38 | 12 Documentation items | Docs | 54h | All |

---

## 10. Unified Effort Summary

### 10.1 By Category

| Category | Items | Hours | Notes |
|----------|-------|-------|-------|
| **Firmware** | Drivers, stubs, tests, harness, getters | ~238h | 40h LSM6DSO driver is largest item |
| **Infrastructure** | Pipeline, runners, images, APIs, schemas | ~399h | 40h pipeline controller is bottleneck |
| **Hardware** | Fixtures, wiring, procurement | ~100h | + $3,000-6,500 parts |
| **Frontend** | Dashboard, charts, trigger UI | ~44h | Can be deferred |
| **Documentation** | Guides, runbooks, examples | ~54h | Spread across team |
| **TOTAL** | | **~835h** | Engineering hours only |

### 10.2 By Stage

| Stage | FW (h) | Infra (h) | HW (h) | FE (h) | Docs (h) | Total |
|-------|--------|-----------|---------|--------|----------|-------|
| Stage 1: Software Tests | 55 | 72 | 0 | 0 | 3 | ~130h |
| Stage 2: Driver HW Tests | 93 | 96 | 36 | 0 | 5 | ~230h |
| Stage 3: Integration Tests | 74 | 88 | 20 | 0 | 12 | ~194h |
| Stage 4: Product Validation | 0 | 102 | 44 | 0 | 12 | ~158h |
| FUOTA Validation | 0 | 20 | 0 | 0 | 4 | ~24h |
| Manufacturing Integration | 0 | 8 | 0 | 0 | 4 | ~12h |
| Platform Services | 16 | 13 | 0 | 44 | 14 | ~87h |
| **TOTAL** | **238h** | **399h** | **100h** | **44h** | **54h** | **~835h** |

### 10.3 By Interface Boundary

This view shows where the integration complexity concentrates:

| Interface | Components That Touch It | Total Effort (h) | Risk |
|-----------|-------------------------|-------------------|------|
| MTIB gRPC | FixtureController, PowerProfiler, UartDemuxer, test functions, flash sequence | ~60h new code | Low — interface is stable PROD |
| CoreCloud SDK | CloudClient, FuotaPlanBuilder, FuotaMonitor, test functions | ~30h new code | Medium — FUOTA API unclear |
| K8s API | Pipeline controller, Job template, node matching, CronJobs | ~60h new code | Medium — new orchestration |
| HTTP API | Pipeline endpoints, build endpoints, result reporting | ~28h new code | Low — extends existing Flask |
| Harness UART | concord_harness module, HarnessTransport, UartDemuxer | ~70h new code | High — novel, no reference impl |
| Build System | Build service, west toolchain, cross-repo builds | ~36h new code | Medium — cross-repo is tricky |
| Frontend REST | 4 new pages, existing API patterns | ~44h new code | Low — established patterns |

### 10.4 Critical Path

```
Week 1-2:   Foundations (firmware stubs, Prisma schema, parser, harness API design)
Week 2-4:   Stage 1 firmware complete (interface tests, app tests)
Week 3-5:   Pipeline infra (build service, pipeline controller) *** BOTTLENECK ***
Week 5:     Stage 1 operational end-to-end
Week 3-6:   LSM6DSO driver (parallel with infra)
Week 5-7:   Stage 2 test runner modules
Week 4-6:   Dev-kit fixture HW ready
Week 7:     Stage 2 operational end-to-end
Week 3-7:   concord_harness module (parallel)
Week 6-8:   Alpha harness integration
Week 7-9:   Stage 3 runner + tests
Week 9:     Stage 3 operational end-to-end
Week 8-10:  Stage 4 spec + runner + FUOTA flow
Week 8-10:  Alpha product fixture
Week 10-11: Stage 4 operational (commit subset: 43 tests)
Week 12:    Stage 4 full suite (weekly: 89 tests) + FUOTA validation

CRITICAL PATH: Pipeline Controller (40h) → Stage Gating (8h) → All stages after 1
CALENDAR: 10-12 weeks with 3 parallel engineers + 1 HW engineer
          24+ weeks single-threaded
```

---

## 11. Blocked Items

Items that cannot proceed until external decisions are made:

| # | Item | Blocked By | Impact | Workaround |
|---|------|-----------|--------|-----------|
| B1 | `GroundModeConfigV2` REST delivery | CoreCloud team: REST endpoint for UID 538 | 18 config value tests deferred | Defer tests; implement when endpoint exists |
| B2 | `BiometricConfig` message class | CoreCloud team: UID + REST endpoint | Biometric config tests deferred | Defer tests |
| B3 | FUOTA plan creation via REST | CoreCloud team: REST API vs DB ORM decision | Determines `FuotaPlanBuilder` implementation | Fallback: DB ORM writes (works but bypasses business logic) |
| B4 | FUOTA cooldown reduction | CoreCloud team: is 5-min cooldown configurable? | FUOTA flow takes 2+ hours | Accept long run time for weekly suite |
| B5 | Device personalization | Firmware/operations team: nRF9151 certs/keys | FUOTA and all CoreCloud-dependent tests | Must personalize test DUTs before Stage 4 |
| B6 | nRF9151 comms coprocessor FUOTA | Firmware team: dual-MCU FUOTA flow | Full device FUOTA coverage | Test nRF52840 FUOTA only initially |
| B7 | CoreCloud `VAL_1_0` environment access | CoreCloud team: credentials, DB access | All CoreCloud-dependent tests | Use `DEV_1_0` via SSH tunnel initially |

---

## 12. Open Design Decisions

Decisions that the implementation team must make before building:

| # | Decision | Options | Recommendation | Document |
|---|----------|---------|---------------|----------|
| D1 | FUOTA plan creation interface | DB ORM vs REST API | REST if available, DB ORM as fallback | test-runner-stack.md §11.1 |
| D2 | GroundModeConfigV2 delivery | REST endpoint, promote to ConfMsgBase, v0.9 shim, defer | Defer until REST endpoint exists | test-runner-stack.md §11.2 |
| D3 | Test framework architecture | Adapt mfg TestStep/Test, new pytest-based, hybrid | Hybrid: pytest execution + TestStepResult patterns | test-runner-stack.md §11.3 |
| D4 | Async vs sync test functions | Async (concurrent), sync (simple) | Start sync, add async if needed | test-runner-stack.md §11.4 |
| D5 | Fixture profile storage | K8s ConfigMap, Concord DB, env var, MinIO | Concord DB (Node.fixtureProfile) | test-runner-stack.md §11.5 |
| D6 | UartDemuxer strategy | Prefix-based, MTIB channel, shell+prefix | Shell + prefix (matches ShellCommandHelper) | test-runner-stack.md §11.6 |
| D7 | Build service interface | gRPC, internal REST, K8s CRD | Internal REST (simplest, HTTP API already exists) | New |
| D8 | Pipeline state machine | In-memory, PostgreSQL, Redis | PostgreSQL (Prisma, survives restart) | New |

---

## 13. Implementation Phases

### Phase 0: Prerequisites (Week 0-1)

| Deliverable | Owner | Hours |
|-------------|-------|-------|
| K3s cluster access verified | Infra | 2 |
| Container registry access verified | Infra | 1 |
| CoreCloud `VAL_1_0` credentials obtained | Infra + CoreCloud | 4 |
| Alpha DUT personalized (nRF9151 certs) | FW/Ops | 8 |
| Hardware procurement ordered | HW | 2 |
| Design decision D1-D8 resolved | All | 8 |

### Phase 1: Parallel Foundation (Weeks 1-4)

Five parallel streams:

| Stream | Components | Owner | Hours |
|--------|-----------|-------|-------|
| A: Firmware stubs + tests | F01-F21 (accel_drv, alpha_fw stubs) | FW | 55h |
| B: Hardware fixtures | H01-H05 (dev-kit wiring, procurement) | HW | 28h |
| C: Pipeline infra | I01-I09 (Prisma, parser, trigger API, build svc, controller) | Infra-1 | 132h |
| D: Test runner modules | I10-I16 (MTIB updates, ztest parser, power profiler, fixture ctrl) | Infra-2 | 60h |
| E: concord_harness | F28-F37 (Zephyr module, shell, registry, emit) | Infra-3 | 41.5h |

### Phase 2: Integration + Stage 2 (Weeks 5-7)

| Stream | Components | Owner | Hours |
|--------|-----------|-------|-------|
| LSM6DSO driver | F05, F07, F38 (driver, DTS, board def) | FW | 51h |
| HW test firmware | F12-F13, F16 (test FW, spec, board features) | FW | 24h |
| Stage 2 runner | I21a, I27 (orchestration, Docker image) | Infra-2 | 16h |
| Alpha harness | F22-F24, F41 (harness declarations, #ifdef guards, EMIT calls) | FW | 23h |

### Phase 3: Stage 3 Proof (Weeks 7-9)

| Stream | Components | Owner | Hours |
|--------|-----------|-------|-------|
| Harness client | I17 (harness_client.py, protocol) | Infra-3 | 12h |
| Cloud client | I18, I23-I24 (CloudClient, message verification, GPS config) | Infra-2 | 16h |
| Integration runner | I21b, I28 (orchestration, Docker image) | Infra-2 | 16h |
| Integration tests | F28a-b (spec + Python test modules) | FW/Infra | 28h |

### Phase 4: Stage 4 Proof (Weeks 8-11)

| Stream | Components | Owner | Hours |
|--------|-----------|-------|-------|
| TestContext + runner | TestContext, ValidationRunner, UartDemuxer | Infra-2 | 32h |
| Validation spec | I42 (89 PRDTST tests mapped) | QA | 24h |
| FUOTA flow | FuotaPlanBuilder, FuotaMonitor, 12-step orchestrator | Infra-3 | 20h |
| NFC + peripherals | I19, H08a-h (NFC client, fixture peripherals) | Infra/HW | 14h |
| Container images | I29 (validation image) | Infra | 4h |

### Phase 5: Hardening + Dashboard (Weeks 11-12)

| Stream | Components | Owner | Hours |
|--------|-----------|-------|-------|
| Frontend pages | I44-I47 (pipeline list, detail, power charts, trigger) | FE | 44h |
| CronJobs | I36 (weekly/nightly schedules) | Infra | 4h |
| Documentation | D01-D12 (all docs, spread across team) | All | 54h |
| Stage 4 full suite | Weekly suite with all 89 tests operational | Infra/QA | 16h |

---

## 14. Risk Register

| # | Risk | Impact | Mitigation |
|---|------|--------|-----------|
| R1 | Pipeline controller (40h) is critical bottleneck | Blocks all stages beyond 1 | Start in Week 1; MVP scope; split into Job creation (Phase A) and stage gating (Phase B) |
| R2 | PCB fabrication for dev-kit fixture takes 3-4 weeks | Stage 2 HW delayed | Order in Week 1; use point-to-point wiring as interim |
| R3 | LSM6DSO driver (40h) may exceed estimate | Stage 2 delayed | Reference existing driver code; time-box to 2 weeks |
| R4 | `concord_harness` is novel infrastructure | Stage 3 integration risk | Thorough unit testing; demo app for validation; comprehensive docs |
| R5 | CoreCloud `VAL_1_0` access not yet confirmed | All Stage 3/4 CoreCloud tests blocked | Use `DEV_1_0` via SSH tunnel initially |
| R6 | FUOTA cooldown makes flow >2 hours | Weekly suite takes very long | Accept for weekly; investigate cooldown reduction |
| R7 | 18 config tests blocked on GroundModeConfigV2 | Incomplete PRDTST coverage | Defer; implement when REST endpoint exists |
| R8 | Cross-repo build complexity (submodule overrides) | Build service scope creep | Direct-repo builds first; cross-repo as Phase B |
| R9 | Temperature chamber ($2-5K) procurement | 7 temp-dependent tests blocked | Defer to Phase 2; use manufacturing chamber if available |
| R10 | UART0 RX killed by app for power savings | Stage 3 harness completely broken | Must add `#ifdef CONFIG_CONCORD_HARNESS` guard before any Stage 3 work |

---

## 15. Cross-Reference to Architecture Documents

| Document | What It Defines | BOM Section |
|----------|----------------|------------|
| `00-validation-philosophy.md` | Why we test, the pyramid, the 3-domain lifecycle | Entire document scope |
| `09-final-architecture.md` | K8s topology, pipeline state machine, Prisma schema | §3.3, §3.4, §8.1 |
| `stage3-integration-tests.md` | concord_harness design, shell protocol, Stage 3 tests | §4.3, §3.7 (harness) |
| `stage4-product-tests.md` | 89 PRDTST specs, test domains, acceptance criteria | §4.4, §4.5 |
| `stage4-fuota-validation-flow.md` | 12-step FUOTA flow, timing, failure handling | §5.1, §5.2 |
| `test-runner-stack.md` | TestContext, CloudClient, FixtureController, walk-throughs | §3.1-3.7, §9.3 (items 20-26) |
| `corecloud-library-architecture.md` | SDK analysis, v0.9 removal, missing capabilities | §3.2, §7.1, §7.2 |
| `bom-validation-pipeline.md` | Component-level tracking with hours and owners | All (companion doc) |
| `plans/stage3-and-4/overview.md` | Stage 3+4 proof overview, BOM summary, dependency graph | §10, §13 |
| `plans/stage3-and-4/phases/` | Phase-by-phase execution plans | §13 (Phases 1-5) |
