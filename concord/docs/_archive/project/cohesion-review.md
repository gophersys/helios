# Cohesion Review: Cross-Document Consistency Audit

> Generated: 2026-02-25
> Scope: All 8 validation architecture documents
> Method: Systematic cross-reference of naming conventions, schemas, interfaces, patterns, and roadmaps

---

## 1. Cross-Document Inconsistencies Found

### 1.1 Repo Name: `accelerometers` vs `lsm6dso_drv` vs `accel_drv`

Three different names for the same driver repository appeared across the docs:

| Name | Used In | Status |
|------|---------|--------|
| `accelerometers` | doc-00 (15 occurrences), doc-09 (28 occurrences), doc-12 (2 occurrences) | **Legacy name** |
| `lsm6dso_drv` | doc-11 (20+ occurrences) | **Current single-driver repo name** |
| `accel_drv` | arch-stage1, arch-stage2, arch-stage3 | **Canonical (locked decision)** |

The arch docs explicitly decided on `accel_drv` -- Sigma's existing accelerometer repo, restructured to hold multiple chips (LSM6DSO, LIS2DE12). The name `accelerometers` was the original philosophy-doc working name; `lsm6dso_drv` is the current single-driver repo being migrated into `accel_drv`.

### 1.2 DTS Vendor Prefix: `corekinect,` vs `ck,`

| Prefix | Used In | Status |
|--------|---------|--------|
| `corekinect,lsm6dso-stub` | doc-00 (3 occurrences), doc-11 (3 occurrences for lsm6dso, pah8151, vsm) | **Old prefix** |
| `ck,lsm6dso-stub` | arch-stage1, arch-stage2 | **Canonical (locked decision)** |

The `ck,` prefix is the Zephyr vendor prefix for CoreKinect. The longer `corekinect,` was used in early drafts but is not a valid Zephyr vendor prefix.

Note: `corekinect,devkit-nrf52840-lsm6dso-spi` in arch-stage2 line 782 is a **board-level** compatible string, not a device binding. Board compatible strings use the full vendor name and are not affected by the `ck,` device prefix decision.

### 1.3 State Names: Generic vs Real Alpha Names

| Location | Before | After |
|----------|--------|-------|
| doc-00, Section 5.3 | `idle`, `active` | `off_body_e`, `low_heat_risk_e` |

The philosophy doc used placeholder names. The real Alpha state machine states are: `off_body_e`, `low_heat_risk_e`, `increased_heat_risk_e`, `heat_emergency_e`, `off_body_validation_e`.

### 1.4 Pipeline.yaml Schema Mismatch

Doc-11 Section 4.3 used a simplified, non-canonical pipeline.yaml schema:

| Field | Doc-11 (old) | Arch-stage1 (canonical) |
|-------|-------------|------------------------|
| Stage name | `software_tests` | `software` |
| Test paths | `twister_args: "-T tests/interface/ -p native_sim"` | `testPaths: ["tests/interface"]` |
| Timeout | `timeout_s: 120` | `timeout: 600` |
| Runner | `runs_on: agent` | *(not specified -- K8s Job is implicit)* |
| Version | *(missing)* | `version: 1` |
| Triggers | *(missing)* | `on: { push: { branches, paths } }` |
| Retry | *(missing)* | `retry: { max_attempts: 2, on: [infrastructure_failure] }` |

The canonical schema (from arch-stage1 Section 5.4) includes `version`, `on`, `concurrency`, `stages` (with `name`, `order`, `type`, `testPaths`, `timeout`, `retry`), `notifications`, `artifacts`, and `targets`.

### 1.5 Harness Pattern: `extern` Globals vs Accessor Functions

Doc-10 (Stage 3 Alpha example) declares 8 `extern` global variables at lines 203-210:

```c
extern alpha_state_t  g_alpha_state;
extern motion_state_t g_motion_state;
extern vsm_data_t     g_last_vsm_data;
// ... 5 more
```

Arch-stage3 Section 3.2 explicitly states: "These do not exist. The firmware uses static local variables." The corrected pattern uses accessor functions:
- Category 1: Accessors that already exist (`get_vsm_data()`, `is_device_on_body()`, `get_battery_percent()`, etc.)
- Category 2: Accessors that need to be added (`get_alpha_state()`, `get_motion_state()`, `get_bio_config()`)

### 1.6 Injection Pattern: Fabricated Event Functions vs Adapter Pattern

Doc-10 lines 320-353 use functions that do not exist in the firmware:

| Doc-10 Function | Status | Arch-stage3 Replacement |
|----------------|--------|------------------------|
| `app_post_event(EVT_TOUCH_DETECTED)` | Does not exist; firmware is polling-based | `concord_force_on_body(true)` override pattern (arch-stage3 Section 3.4) |
| `motion_post_event(MOTION_EVT_DETECTED)` | Does not exist | `force_motion_state_machine(true)` -- already exists in firmware |
| `ipc_inject_rx(buf, len)` | Does not exist | `concord_ipc_inject_rx()` -- new conditional function in `ipc_bus_hw.c` (arch-stage3 Section 3.5) |

The Alpha firmware uses cooperative polling, not event queues. The arch-stage3 doc provides the correct adapter-based injection pattern that works with the current polling architecture.

### 1.7 Doc-09 (`accelerometers` Throughout)

Doc-09 (final architecture) uses `accelerometers` as the repo name in 28 places including:
- K8s Job labels (line 99, 102)
- SubmoduleMapping entries (lines 1546, 1560, 1561)
- PipelineConfig name (line 1572)
- API request/response bodies (lines 1838, 1842, 1853, 1854)
- Build service examples (line 2031)
- west.yml (line 2160, 2177)
- Protobuf message examples (line 2663, 2675)
- Pipeline.yaml example (line 2921)

This is a **structural** inconsistency with the `accel_drv` decision in the arch docs.

### 1.8 Doc-09 SubmoduleMapping: `corekinect/accelerometers`

Doc-09 lines 1546-1561 reference `corekinect/accelerometers` as the submodule repo path. This should be `corekinect/accel_drv` to match the arch docs' Bitbucket URL convention (`git@bitbucket.org:corekinect/accel_drv.git`).

### 1.9 Doc-00 Repo Layout Diagram vs Arch-stage1

Doc-00 originally had driver paths as `drivers/lsm6dso/` and bindings as `dts/bindings/`. Arch-stage1 Section 2.1 specifies:
- Driver path: `drivers/corekinect/sensors/lsm6dso/`
- Bindings path: `dts/bindings/sensor/`

### 1.10 Testcase Name Format

| Doc | Name | Status |
|-----|------|--------|
| doc-00 (original) | `drivers.accelerometers.lsm6dso.hardware` | Old format |
| arch-stage1 | `drivers.sensor.lsm6dso.hw` | Canonical |

---

## 2. Fixes Applied

### 2.1 doc-00 (`00-validation-philosophy.md`)

| Line(s) | Change | Reason |
|---------|--------|--------|
| Section 5.3 | `idle`/`active` -> `off_body_e`/`low_heat_risk_e` | Generic state names replaced with real Alpha state names |
| 3 occurrences | `corekinect,lsm6dso-stub` -> `ck,lsm6dso-stub` | DTS vendor prefix alignment |
| 3 occurrences | `accelerometers/stubs/` -> `accel_drv/stubs/` | Repo name alignment |
| Repo layout diagram | `accelerometers` -> `accel_drv`, `drivers/lsm6dso/` -> `drivers/corekinect/sensors/lsm6dso/`, `dts/bindings/` -> `dts/bindings/sensor/` | Directory structure alignment with arch-stage1 Section 2.1 |
| Testcase path | `accelerometers/tests/lsm6dso/testcase.yaml` -> `accel_drv/tests/lsm6dso/testcase.yaml` | Repo name |
| test_spec path | `accelerometers/tests/lsm6dso/test_spec.yaml` -> `accel_drv/tests/lsm6dso/test_spec.yaml` | Repo name |
| Testcase name | `drivers.accelerometers.lsm6dso.hardware` -> `drivers.sensor.lsm6dso.hw` | Matches arch-stage1 naming convention |
| Line 671 | `accelerometers/.concord/pipeline.yaml (driver repo)` -> `accel_drv/.concord/pipeline.yaml (driver repo)` | Repo name |
| Line 1516 | `accelerometers/.concord/pipeline.yaml` -> `accel_drv/.concord/pipeline.yaml` | Repo name |
| Line 666 | "when accelerometers changes" -> "when accel_drv changes" | Repo name in prose |
| Lines 707-711 | `repo=accelerometers` -> `repo=accel_drv` (4 BuildRequest examples) | Repo name in API examples |
| Line 731 | "from the accelerometers repo" -> "from the accel_drv repo" | Repo name in prose |
| Line 756 | `Driver repo (accelerometers/)` -> `Driver repo (accel_drv/)` | Repo name in directory tree |
| Lines 923-929 | Mermaid diagram: `accelerometers repo push` -> `accel_drv repo push`, `accelerometers -> alpha` -> `accel_drv -> alpha`, `accelerometers -> sigma5` -> `accel_drv -> sigma5` | Repo name in diagram |
| Line 984 | "The accelerometers repo doesn't know" -> "The accel_drv repo doesn't know" | Repo name in prose |
| Line 1654 | `git@bitbucket.org:corekinect/accelerometers.git` -> `git@bitbucket.org:corekinect/accel_drv.git` | Repo URL |

**Kept as-is** (conceptual uses of "accelerometers" that refer to the sensor type, not the repo):
- Line 1214: "By grouping drivers by sensor type (accelerometers, ppg, temperature)"
- Line 1306: "LSM6DSO (in the accelerometers group)"

### 2.2 doc-11 (`11-stage1-alpha-example.md`)

| Change | Reason |
|--------|--------|
| All `lsm6dso_drv` -> `accel_drv` (replace_all) | Repo name alignment |
| All `corekinect,lsm6dso-stub` -> `ck,lsm6dso-stub` | DTS prefix |
| All `corekinect,pah8151-stub` -> `ck,pah8151-stub` | DTS prefix |
| All `corekinect,vsm-stub` -> `ck,vsm-stub` | DTS prefix |
| Section 4.3 pipeline.yaml snippets | Replaced simplified schema (`twister_args`, `runs_on`, `timeout_s`) with canonical schema from arch-stage1 (`version`, `on`, `stages` with `testPaths`, `timeout`, `retry`). Added reference to arch-stage1 Section 5.4. |

### 2.3 doc-12 (`12-stage2-alpha-example.md`)

| Change | Reason |
|--------|--------|
| `accelerometers/.concord/pipeline.yaml` -> `accel_drv/.concord/pipeline.yaml` | Repo name |
| "push to the `accelerometers` repo" -> "push to the `accel_drv` repo" | Repo name in prose |

---

## 3. Fixes NOT Applied (Require Human Decision)

### 3.1 Doc-09: 28 `accelerometers` References (MAJOR)

**File**: `/home/mateo/work/docs/concord/validation/09-final-architecture.md`
**Count**: 28 occurrences across K8s labels, SubmoduleMapping entries, API examples, west.yml, protobuf messages, pipeline.yaml examples

**Why not auto-fixed**: Doc-09 is the master architecture document. Mass-renaming `accelerometers` to `accel_drv` would touch:
- K8s Job labels and annotations (lines 99, 102)
- Database schema examples (lines 1465, 1546, 1560, 1561, 1572)
- API request/response bodies (lines 1838, 1842, 1853, 1854)
- west.yml manifest path (lines 2160, 2177 -- `path: modules/lib/accelerometers` would become `path: modules/lib/accel_drv`)
- Protobuf field values (lines 2663, 2675)
- Pipeline.yaml snippet (line 2921)

**Recommendation**: Apply a targeted search-and-replace in doc-09, changing `accelerometers` to `accel_drv` in all contexts where it refers to the repo name (not the sensor category). The west.yml `path:` at line 2177 needs special attention -- the Zephyr module path may intentionally differ from the repo name.

### 3.2 Doc-10: `extern` Globals Pattern (STRUCTURAL)

**File**: `/home/mateo/work/docs/concord/validation/10-stage3-alpha-example.md`, lines 201-316
**Issue**: The entire `concord_harness.c` example uses `extern` globals and fabricated event functions

**Why not auto-fixed**: This requires rewriting ~120 lines of C code in the example to match the accessor-function pattern from arch-stage3 Section 3.2. The corrected code exists in arch-stage3 lines 750-895. However:
1. The example doc's didactic structure (progressive build-up of getters, setters, inject, events) would need restructuring
2. The arch-stage3 doc already contains the corrected version and explicitly references doc-10's errors
3. Replacing the code would require adjusting surrounding prose explanations

**Recommendation**: Either (a) replace doc-10's `concord_harness.c` section wholesale with the corrected version from arch-stage3, updating surrounding prose, or (b) add a prominent "Superseded" callout at the top of doc-10 Section 5 directing readers to arch-stage3 Section 3 for the corrected patterns. Option (b) is lower risk; option (a) makes the example doc self-contained.

### 3.3 Doc-10: Fabricated Injection Functions (STRUCTURAL)

**File**: `/home/mateo/work/docs/concord/validation/10-stage3-alpha-example.md`, lines 320-353
**Issue**: `app_post_event(EVT_TOUCH_DETECTED)`, `motion_post_event(MOTION_EVT_DETECTED)`, and `ipc_inject_rx()` do not exist in the firmware

**Why not auto-fixed**: Same as 3.2 -- requires rewriting the injection section to use `concord_force_on_body()` override pattern and `force_motion_state_machine()`. The corrected patterns are in arch-stage3 Sections 3.4-3.5.

### 3.4 Doc-09 Pipeline.yaml Schema vs Arch Docs

**File**: `/home/mateo/work/docs/concord/validation/09-final-architecture.md`, line 2921+
**Issue**: Doc-09's pipeline.yaml example may use an older schema version than what arch-stage1/2/3 define

**Why not auto-fixed**: Doc-09 defines the *general* pipeline.yaml schema; the arch docs refine it for each stage. A schema reconciliation is needed to determine which fields are canonical. The arch docs' schemas should be authoritative for stage-specific fields.

---

## 4. Unified Roadmap

### 4.1 Shared Infrastructure (Cross-Stage Dependencies)

These items are prerequisites for multiple stages:

| Item | Needed By | Owner | Effort |
|------|-----------|-------|--------|
| `accel_drv` repo restructuring (new directory layout, module.yml, merged Kconfig/CMake) | Stage 1, Stage 2 | Firmware | 17h (Stage 1 Phase 1) |
| `ck_boards` dev-kit board definition (`devkit_nrf52840_lsm6dso_spi`) | Stage 1 (interface tests reference it), Stage 2 | Firmware | Included in Stage 2 Phase 1 |
| `.concord/pipeline.yaml` parsing in HTTP API | Stage 1, Stage 2, Stage 3 | Infra | 8h (Stage 1 Phase 5) |
| `.concord/build.yaml` parsing in build service | Stage 1, Stage 2, Stage 3 | Infra | Part of Stage 1 Phase 5 |
| `pipeline.yaml` schema definition (triggers, stages, targets, concurrency) | All stages | Infra | Embedded in Stage 1 Phase 5 |
| K8s Job templating in pipeline controller | All stages | Infra | 4h (Stage 1 Phase 5) |
| Stage gate mechanism (Stage N pass -> create Stage N+1 Jobs) | Stage 1->2->3 | Infra | 4h (Stage 1 Phase 5) |
| Bitbucket commit status reporting | All stages | Infra | 2h (Stage 1 Phase 5) |
| `concord_harness` Zephyr module | Stage 3 only, but can start in parallel | Infra | Phase A of Stage 3 |
| MTIB client library (`mtib_client.py`) | Stage 2, Stage 3 | Infra | Part of Stage 2 Phase 3 |
| MinIO artifact storage patterns | Stage 2, Stage 3 | Infra | Part of Stage 2 Phase 3 |
| InfluxDB power data push | Stage 2, Stage 3 | Infra | Part of Stage 2 Phase 3 |

### 4.2 Critical Path

```
Week 1-2:  [Stage 1] Phase 0+1: Prep + accel_drv repo restructuring (24h)
           [Stage 2] Phase 1.1: Dev-kit fixture schematic (HW eng, parallel)
           [Stage 3] Phase A: concord_harness module (Infra, parallel)

Week 2-3:  [Stage 1] Phase 2+3: Interface tests + App test infra (31.5h)
           [Stage 2] Phase 1.3-1.5: Board definition + driver restructure (parallel with Stage 1)
           [Stage 3] Phase A cont'd: concord_harness unit tests

Week 3-4:  [Stage 1] Phase 4: App-level tests (20h)
           [Stage 2] Phase 2: Test firmware (FW eng, after Stage 1 Phase 1)

Week 4-5:  [Stage 1] Phase 5: Pipeline integration (40h) *** CRITICAL ***
           [Stage 2] Phase 2 cont'd: test_spec.yaml
           [Stage 3] Phase B: Alpha firmware integration (after Phase A)
                     Phase C: Python-side infra (parallel with Phase B)

Week 5-7:  [Stage 2] Phase 3: Test runner (after mtib_client exists) + Phase 4: Pipeline integration
           [Stage 3] Phase D: Build service integration (after Phase B)

Week 7-8:  [Stage 2] Phase 4+5: Pipeline integration + production hardening
           [Stage 3] Phase E: End-to-end validation

Week 8-10: [Stage 2] Phase 5: Production hardening
           [Stage 3] Phase E cont'd: First real Stage 3 run on hardware
```

**Critical path**: Stage 1 Phase 5 (pipeline integration, 40h) is the bottleneck. It produces the shared pipeline infrastructure (pipeline.yaml parsing, K8s Job creation, stage gates, build service) that Stages 2 and 3 depend on. Stages 2 and 3 cannot integrate with the pipeline until Stage 1 Phase 5 is substantially complete.

### 4.3 Parallelization Opportunities

| Parallel Track | Items | Owner |
|---------------|-------|-------|
| **Track A: Firmware (Stage 1 + 2)** | accel_drv restructuring, interface tests, app tests, test firmware for Stage 2 | Firmware engineer |
| **Track B: Hardware (Stage 2)** | Dev-kit fixture schematic, PCB fab, assembly, wiring to MTIB | HW engineer |
| **Track C: Infra - Pipeline (Stage 1)** | pipeline.yaml parsing, build service, K8s Jobs, stage gates | Infra engineer 1 |
| **Track D: Infra - Test Runner (Stage 2)** | mtib_client, ztest_parser, power_profiler, fixture_controller | Infra engineer 2 |
| **Track E: Infra - Harness (Stage 3)** | concord_harness module, Python client, UART demuxer | Infra engineer 3 (or same as 2, sequenced) |

Tracks A, B, and C/D/E can proceed independently for the first 3-4 weeks. Track B has the longest physical lead time (PCB fabrication).

### 4.4 Effort Summary

| Stage | Effort Estimate | Calendar Time | Source |
|-------|----------------|---------------|--------|
| Stage 1: Software Tests | ~116h | ~5 weeks | arch-stage1 Section 7 |
| Stage 2: Driver HW Tests | ~160-200h (estimated) | ~10 weeks | arch-stage2 Section 8 (25+ work items across 5 phases) |
| Stage 3: Integration Tests | ~120-160h (estimated) | ~8 weeks | arch-stage3 Section 8 (5 phases, A through E) |
| **Total** | **~400-475h** | **~10 weeks (with parallelization)** | |

Stage 2 and Stage 3 roadmaps do not include per-item hour estimates in the arch docs (unlike Stage 1). The totals above are estimated from item complexity and Stage 1 as a reference.

Without parallelization (single engineer), the calendar time would be ~23 weeks. With the parallel tracks above (3 engineers + 1 HW eng), the critical path compresses to ~10 weeks, gated by Stage 2 Phase 3-4 (test runner + pipeline integration).

---

## 5. Remaining Open Questions Across All Stages

### Cross-Stage Questions

| # | Question | Stages Affected | Impact |
|---|----------|----------------|--------|
| 1 | **Doc-09 `accelerometers` rename**: Should doc-09 be updated to use `accel_drv` throughout? This is 28 references including DB schema, API examples, K8s labels, protobuf messages. | All | Consistency across the documentation set. Without this, doc-09 and the arch docs use different names for the same repo. |
| 2 | **Doc-10 rewrite vs supersede callout**: Should doc-10's harness code examples be rewritten to match arch-stage3's accessor pattern, or should doc-10 be marked as "illustrative only, see arch-stage3 for implementation details"? | Stage 3 | Developer confusion if doc-10 is read without arch-stage3 context. |
| 3 | **pipeline.yaml schema source of truth**: Doc-09 defines a general schema, arch-stage1 defines a refined schema with `testPaths`/`timeout`/`retry`. Which is canonical? Should doc-09's schema be updated? | All | Pipeline implementation will need one definitive schema. |
| 4 | **build.yaml schema**: Doc-09 and arch-stage1 both define `build.yaml` but with slightly different structures. Need a single canonical schema. | Stage 1, Stage 2 |
| 5 | **west.yml module path**: Doc-09 line 2177 uses `path: modules/lib/accelerometers`. If the repo is renamed to `accel_drv`, should the west module path also change? The path is independent of the repo name in Zephyr's west manifest. | Stage 1, Stage 2 |

### Stage 1 Open Questions (from arch-stage1 Section 8)

| # | Question | Status |
|---|----------|--------|
| 8.1 | Type duplication in test headers (`alpha_state_t` in .c and .h) | Decision needed: accept risk or move types to headers |
| 8.2 | Stub completeness for `stubs.c` (~15 module stubs) | Resolved by Phase 0.2 dependency audit |
| 8.3 | Timer behavior on `native_sim` (`k_timer` precision) | Verify during Phase 4 |

### Stage 2 Open Questions (from arch-stage2 Section 9)

| # | Question | Status |
|---|----------|--------|
| 1 | Sense resistor value (10 ohm vs 1 ohm) | Analysis favors 10 ohm; verify LDO dropout |
| 2 | VDDIO 3.3V vs 1.8V on dev-kit | Proceed with 3.3V, document difference |
| 3 | CONFIG_CK_LSM6DSO_TRIGGER timeline | Use raw GPIO approach for Phase 1 |
| 4 | Multi-chip relay sequencing discharge time | Use 100ms between transitions |
| 5 | nRF52840-DK J-Link compatibility with MTIB SWD | Verify with MTIB team |
| 6 | LIS2DE12 I2C address conflict | Verify breakout board SA0 jumper |
| 7 | InfluxDB retention policy for power data | Proposed: 90 days full, 1 year downsampled |

### Stage 3 Open Questions (from arch-stage3 Section 9)

| # | Question | Status |
|---|----------|--------|
| 1 | `alpha_state_t` move to header: unconditional or `#ifdef`? | Recommended: unconditional |
| 2 | Bio config setters: individual vs generic `set_bio_config_field()`? | Decision needed |
| 3 | `CONCORD_EMIT` timestamp inclusion | Recommended: include `k_uptime_get()` |
| 4 | Shell command concurrency | Recommended: single-command-at-a-time with lock |
| 5 | `concord_harness` module versioning | Needs semver policy |
| 6 | IPC injection: bypass encryption? | Recommended: inject after decryption |
| 7 | `CONCORD_EMIT` from ISR: `k_msgq_put` with `K_NO_WAIT` safety | Verify for NCS versions |
| 8 | UART0 conflict: `NRF_UARTE0->TASKS_STOPRX = 1` in app.c | **Must resolve before Phase B12** |
| 9 | Harness point naming registry schema | Deferred (nice-to-have) |
| 10 | Harness shell output via `shell_print()` vs log backend | Recommended: keep `shell_print()` |

### Cross-Stage Decision: Type Visibility

Both Stage 1 (question 8.1) and Stage 3 (question 1) ask whether `alpha_state_t` and `motion_state_t` should be moved to headers. Stage 1 proposes `#ifdef CONFIG_ZTEST` accessor blocks as a workaround; Stage 3 recommends moving the typedef unconditionally. These should be resolved together -- if Stage 3 needs the typedef in the header, do it once during Stage 1 implementation rather than adding `#ifdef` workarounds that get removed later.

**Recommendation**: Move `alpha_state_t` and `motion_state_t` to their respective headers unconditionally during Stage 1 Phase 3, item 3.1. This satisfies both Stage 1 test needs and Stage 3 harness needs, and avoids the type duplication risk entirely.

---

## 6. Document Dependency Graph

```
00-validation-philosophy.md  (foundational "why")
        |
        v
09-final-architecture.md     (system-wide "how")
        |
        +---> arch-stage1-software-tests.md  --> 11-stage1-alpha-example.md
        |
        +---> arch-stage2-driver-hw-tests.md --> 12-stage2-alpha-example.md
        |
        +---> arch-stage3-integration-tests.md --> 10-stage3-alpha-example.md
```

When making changes:
- Naming decisions (repo name, DTS prefix, state names) flow DOWN from the arch docs
- Schema decisions (pipeline.yaml, build.yaml) should be locked in the arch docs and referenced by example docs
- Example docs should not introduce new patterns -- they illustrate what the arch docs define
- Doc-09 and doc-00 need periodic sync with the arch docs as decisions are refined
