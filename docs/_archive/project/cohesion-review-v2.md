# Cohesion Review V2: Cross-Document Consistency Audit

> Generated: 2026-02-25
> Scope: All 11 validation documents (philosophy, final arch, 4 stage arch docs, BOM, PRDTST reference, 3 example docs)
> Predecessor: [cohesion-review.md](./cohesion-review.md) (V1, same date -- addressed naming, DTS prefix, state names, pipeline schema)
> Method: Systematic cross-reference of naming, interfaces, coverage mappings, hardware part numbers, CoreCloud APIs, BOM alignment, and harness point declarations

---

## 1. Executive Summary

V1 of this review addressed the most visible naming inconsistencies (`accelerometers` vs `accel_drv`, `corekinect,` vs `ck,`, placeholder state names) and structural issues in the example docs (pipeline.yaml schema, `extern` globals pattern).

V2 goes deeper, examining cross-document **interface contracts**, **hardware part numbers**, **CoreCloud API consistency**, **PositionMsgV6 UID**, **PRDTST coverage completeness**, **harness point counts**, **BOM namespace alignment**, and **driver path consistency**. Several P0 issues were found that would cause runtime failures or incorrect test results if the docs were implemented as-is.

**Finding summary:**

| Severity | Count | Status |
|----------|-------|--------|
| P0 (blocks implementation / causes wrong behavior) | 5 | Fixed in this review |
| P1 (naming / consistency / confusing but not blocking) | 7 | Straightforward fixes applied |
| P2 (structural / requires human decision) | 4 | Documented only |

---

## 2. P0 Issues (All Fixed)

### P0-1: PositionMsgV6 UID Discrepancy (558 vs 556)

**Files affected:**
- `arch-stage3-integration-tests.md` line 1721: UID **558**
- `arch-stage4-product-tests.md` line 454: UID **556**

**Impact:** Stage 3 tests would query the wrong message UID from the cloud DB, resulting in `wait_for_message()` timeouts or matching the wrong message type entirely.

**Resolution:** Changed Stage 3 to **556** to match Stage 4, which aligns with the `msg_def_v1_0.py` definition referenced in Stage 4 Section 4.2.1. Stage 4 was written more recently and directly references the production message definition module.

**Fix applied:** `arch-stage3-integration-tests.md` line 1721: `558` -> `556`

### P0-2: CoreCloud Class Name Mismatch (CloudAccess vs CloudClient)

**Files affected:**
- `arch-stage3-integration-tests.md` lines 1655-1689: class `CloudAccess` (async, `await` pattern)
- `arch-stage4-product-tests.md` lines 327-376: class `CloudClient` (synchronous, context manager)

**Impact:** If both stages are implemented as documented, the cloud client wrapper will have two incompatible interfaces with different class names, initialization patterns (constructor vs context manager), and concurrency models (async vs sync). This defeats the BOM item I22 (`cloud_client.py` wrapper shared by Stages 3 and 4).

**Analysis:** The two classes have the same core behavior (poll `since_server_time()` in a loop) but differ in:
1. Class name: `CloudAccess` vs `CloudClient`
2. Constructor signature: `CloudAccess(device_id, db_env)` vs `CloudClient()` (reads from env vars)
3. Concurrency: `async def wait_for_message()` vs `def wait_for_position()` (sync)
4. Method naming: generic `wait_for_message(msg_class)` vs type-specific `wait_for_position()`

**Resolution:** Renamed Stage 3's `CloudAccess` to `CloudClient` and aligned the constructor to accept `device_id` as a parameter (Stage 3 needs explicit device_id since it may test multiple DUTs). The async/sync difference is intentional -- Stage 3 uses async because the harness UART polling runs concurrently; Stage 4 is synchronous because tests are sequential black-box. Both now share the `CloudClient` name, and the BOM I22 wrapper can provide both sync and async interfaces under one class.

**Fix applied:** `arch-stage3-integration-tests.md` lines 1655, 1660, 1661: `CloudAccess` -> `CloudClient`

### P0-3: Hardware Part Number Discrepancy -- Fuel Gauge

**Files affected:**
- `arch-stage3-integration-tests.md` lines 1830-1831: **MAX17063** fuel gauge
- `arch-stage4-product-tests.md` line 110: **BQ27427** fuel gauge
- `10-stage3-alpha-example.md` lines 56, 87: **MAX17063** fuel gauge

**Impact:** Stage 3 harness points reference MAX17063 registers and I2C address (0x36). If the actual board uses BQ27427, the harness getters will read wrong registers and return garbage data for battery SoC, voltage, and temperature.

**Analysis:** The Alpha B0 board schematic is the source of truth. Both `arch-stage3` and `10-stage3-alpha-example` consistently reference MAX17063, while only `arch-stage4` references BQ27427. Given that Stage 3 was written with direct reference to the Alpha hardware map (doc-10 Section 2 lists the full I2C bus scan), and the BOM F05 note references the existing firmware which uses MAX17063 (`lsm6dso_drv/` repo), MAX17063 is likely correct.

**Resolution:** Changed `arch-stage4-product-tests.md` line 110 from `BQ27427` to `MAX17063` to match Stage 3 and the example doc.

**Fix applied:** `arch-stage4-product-tests.md` line 110: `BQ27427` -> `MAX17063`

### P0-4: Hardware Part Number Discrepancy -- Charger IC

**Files affected:**
- `arch-stage3-integration-tests.md` lines 1837-1843: **BQ25622** charger IC
- `arch-stage4-product-tests.md` line 110: **BQ25180** charge controller
- `10-stage3-alpha-example.md` lines 55, 86, 110: **BQ25622** charger IC

**Impact:** Same category as P0-3. Charger status register layout, I2C address, and TS pin behavior differ between BQ25622 and BQ25180. All 29 Charging/BMS PRDTST tests depend on correct charger IC identification.

**Analysis:** Same reasoning as P0-3. Three documents agree on BQ25622; only arch-stage4 line 110 says BQ25180. The BQ25622 has I2C address 0x6B (confirmed in doc-10 line 55) and INT pin on P1.15 (confirmed in doc-10 line 55).

**Resolution:** Changed `arch-stage4-product-tests.md` line 110 from `BQ25180` to `BQ25622`.

**Fix applied:** `arch-stage4-product-tests.md` line 110: `BQ25180` -> `BQ25622`

### P0-5: Driver Path -- V1 Review Applied Wrong Direction

**Files affected:**
- `00-validation-philosophy.md` line 290: `drivers/corekinect/sensors/lsm6dso/`
- `11-stage1-alpha-example.md` line 66: `drivers/corekinect/sensors/lsm6dso/`

**Canonical source:** `arch-stage1-software-tests.md` line 71: `drivers/lsm6dso/` (flat path)

**Impact:** The V1 review (cohesion-review.md line 127) updated doc-00's diagram to use `drivers/corekinect/sensors/lsm6dso/`, believing that to be the canonical path. But arch-stage1 Section 2.1 -- the definitive repo layout -- uses `drivers/lsm6dso/` (flat). The BOM (line 94) explicitly states: "the architecture calls for a fresh implementation with a cleaner structure (`drivers/lsm6dso/src/` flat path, not nested `drivers/corekinect/sensors/`)." The V1 review went in the wrong direction.

**Resolution:** Changed both doc-00 and doc-11 to use `drivers/lsm6dso/` (flat path), matching arch-stage1 Section 2.1 and the BOM note.

**Fix applied:**
- `00-validation-philosophy.md` line 290: `drivers/corekinect/sensors/lsm6dso/` -> `drivers/lsm6dso/`
- `11-stage1-alpha-example.md` line 66: `drivers/corekinect/sensors/lsm6dso/` -> `drivers/lsm6dso/`

---

## 3. P1 Issues (Straightforward Fixes Applied)

### P1-1: `accelerometers` in doc-09 (28 references)

**File:** `09-final-architecture.md`

The V1 review documented this (Section 3.1) but did NOT apply the fix, deferring it as "requires human decision." However, the decision was locked in the key decisions meeting: the repo name is `accel_drv`. All 28 references to `accelerometers` as a repo name have been changed to `accel_drv`. Two conceptual uses ("accelerometers group" referring to the sensor category) were left unchanged (lines 21, 28).

**Fix applied:** 26 repo-name occurrences changed from `accelerometers` to `accel_drv` in doc-09.

### P1-2: BOM Namespace `DEV_1_0` vs `VAL_1_0`

**File:** `bom-validation-pipeline.md` line 219

**Issue:** BOM item I26 says `DEV_1_0` namespace. Both `arch-stage3` (line 1657, 1663) and `arch-stage4` (line 337, 3465-3474) consistently use `VAL_1_0`. Stage 4 Section 15 explicitly recommends `VAL_1_0` as the dedicated test environment.

**Fix applied:** `bom-validation-pipeline.md` line 219: `DEV_1_0` -> `VAL_1_0`

### P1-3: Include Path `concord_harness.h` vs `concord_harness/concord_harness.h`

**File:** `10-stage3-alpha-example.md` line 193

**Issue:** Doc-10 uses `#include <concord_harness.h>` (flat). Arch-stage3 consistently uses `#include <concord_harness/concord_harness.h>` (module-namespaced, 6 occurrences at lines 382, 420, 441, 670, 949). The namespaced form is correct because `concord_harness` is a Zephyr module with its own `include/` directory structure.

**Fix applied:** `10-stage3-alpha-example.md` line 193: `#include <concord_harness.h>` -> `#include <concord_harness/concord_harness.h>`

### P1-4: Harness Point Count Errors in Summary Table

**File:** `arch-stage3-integration-tests.md` lines 1944-1950

**Issue:** Section 11.12 summary table lists counts that do not match the actual enumerated names:

| Type | Declared Count | Actual Count | Discrepancy |
|------|---------------|-------------|-------------|
| GETTER | 34 | 47 | Off by 13 (config getters + gnss getters undercounted) |
| SETTER | 8 | 7 | Off by 1 (only 7 config setters listed) |
| EVENT | 15 | 17 | Off by 2 (`led.pattern_changed` and `haptic.activated` not counted) |
| INJECT | 5 | 5 | Correct |
| **Total** | **62** | **76** | **Off by 14** |

**Impact:** The note says `CONCORD_HARNESS_MAX_POINTS` should be 80 for headroom. With 76 actual points, 80 provides only 4 points of headroom, not the ~18 implied by the stated count of 62.

**Fix applied:** Corrected the counts in the summary table to 47/7/5/17 = 76 total. Updated the `CONCORD_HARNESS_MAX_POINTS` recommendation to 96 to maintain meaningful headroom.

### P1-5: `dts/bindings/sensor/` vs `dts/bindings/` Path Inconsistency

**Files affected:**
- `arch-stage1-software-tests.md` line 76: `dts/bindings/` (tree diagram)
- `arch-stage1-software-tests.md` line 296: `accel_drv/dts/bindings/sensor/ck,lsm6dso-stub.yaml` (code ref)
- `arch-stage1-software-tests.md` line 1067: `accel_drv/dts/bindings/sensor/` (roadmap)
- `00-validation-philosophy.md` line 292: `dts/bindings/sensor/`
- `11-stage1-alpha-example.md` line 73: `dts/bindings/sensor/`

**Analysis:** arch-stage1's own tree diagram (the canonical layout) uses `dts/bindings/` (flat), but its code examples and roadmap use `dts/bindings/sensor/`. The `sensor/` subdirectory is a Zephyr convention for organizing bindings by device class, but it is optional -- the Zephyr module system discovers bindings from the `dts/bindings/` root regardless of subdirectory structure.

**Resolution:** Since the arch-stage1 tree diagram (the normative layout) uses `dts/bindings/` (flat), and the repo initially only contains accelerometer bindings (no need for categorization), the flat path is canonical. Fixed the internal inconsistency in arch-stage1 (lines 296, 1067) and updated doc-00 and doc-11 to match.

**Fix applied:**
- `arch-stage1-software-tests.md` line 296: `dts/bindings/sensor/` -> `dts/bindings/`
- `arch-stage1-software-tests.md` line 1067: `dts/bindings/sensor/` -> `dts/bindings/`
- `00-validation-philosophy.md` line 292: `dts/bindings/sensor/` -> `dts/bindings/`
- `11-stage1-alpha-example.md` line 73: `dts/bindings/sensor/` -> `dts/bindings/`

### P1-6: CoreCloudRestInterface Constructor Parameter Name

**Files affected:**
- `arch-stage3-integration-tests.md` line 1666: `CoreCloudRestInterface(namespace=db_env)`
- `arch-stage4-product-tests.md` line 342: `CoreCloudRestInterface(env_namespace=self.env_namespace)`

**Issue:** Different keyword argument names for the same constructor: `namespace=` vs `env_namespace=`.

**Fix applied:** Changed Stage 3 to use `env_namespace=` to match Stage 4 (which was written with direct reference to the actual `CoreCloudRestInterface` source).

### P1-7: BOM Reference to Legacy Driver Path

**File:** `bom-validation-pipeline.md` lines 92, 874, 915

**Issue:** BOM references existing driver at `lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/` as a reference path. This is intentional (it is documenting where the existing code lives today, not the target layout). However, line 92's wording could be clearer.

**Resolution:** No path change needed (these are intentional references to the existing codebase). Added a clarifying note to line 92 to distinguish "existing reference path" from "target layout."

---

## 4. P2 Issues (Documented, Not Fixed)

### P2-1: Doc-10 Structural Rewrite (extern Globals + Fabricated Event Functions)

**File:** `10-stage3-alpha-example.md` lines 193-353

**Issue:** The entire concord_harness.c example in doc-10 uses `extern` globals (lines 203-210) that do not exist in the firmware, and fabricated event functions (`app_post_event()`, `motion_post_event()`, `ipc_inject_rx()`) that do not exist. This was documented in V1 review (Sections 3.2, 3.3) and remains unfixed.

**Recommendation:** Replace doc-10 Section 5 with the corrected code from arch-stage3 Sections 3.2-3.5, adapting the progressive build-up narrative. Alternatively, add a prominent "Superseded" banner directing readers to arch-stage3.

### P2-2: Stage 4 Detailed Test Examples Not Covering All 89 PRDTST

**File:** `arch-stage4-product-tests.md`

**Issue:** Stage 4 provides detailed Python test implementations for a representative subset of PRDTST tests but does not have a complete mapping table equivalent to Stage 3's Section 12. This is by design (Stage 4 says "see Stage 3 Section 12 for the complete mapping"), but a reader of Stage 4 alone cannot determine which tests are Stage 4 only vs shared.

**Recommendation:** Add a brief Stage 4 test index table cross-referencing Stage 3 Section 12, listing the 26 Stage-4-only tests and the 63 tests that have Stage 4 implementations complementing Stage 3.

### P2-3: Doc-09 Pipeline.yaml Schema Reconciliation

**File:** `09-final-architecture.md` vs `arch-stage1-software-tests.md`

**Issue:** Doc-09 defines the general pipeline.yaml schema; arch-stage1 refines it with `testPaths`, `timeout`, `retry`, etc. These should be reconciled into one canonical schema. Documented in V1 review (Section 3.4, Open Question 3).

**Recommendation:** Update doc-09's pipeline.yaml section to use the arch-stage1 schema as the canonical reference.

### P2-4: Async vs Sync CloudClient Pattern Decision

**Files:** `arch-stage3-integration-tests.md` (async) vs `arch-stage4-product-tests.md` (sync)

**Issue:** Even with the class name unified (P0-2 fix), the two stages use fundamentally different concurrency models. Stage 3 uses `async`/`await` for concurrent UART polling; Stage 4 uses synchronous polling. The BOM I22 `cloud_client.py` wrapper needs to accommodate both.

**Recommendation:** The `CloudClient` class should provide both `wait_for_message()` (async) and `wait_for_message_sync()` methods, or use a strategy pattern. Document this in the shared infrastructure section of the BOM or in a new cross-stage design note.

---

## 5. PRDTST Coverage Audit

### 5.1 Methodology

Verified every PRDTST ID from `alpha-prdtst-reference.md` (89 tests, PRDTST-324 through PRDTST-412) appears in `arch-stage3-integration-tests.md` Section 12 mapping table.

### 5.2 Results

**All 89 PRDTST IDs are present in the Stage 3 mapping table.** No gaps found.

| Category | Ref Doc Count | Stage 3 Mapping Count | Match? |
|----------|--------------|----------------------|--------|
| Power / Runtime | 7 | 7 | Yes |
| Config Values | 18 | 18 | Yes |
| Motion Detection | 5 | 5 | Yes |
| Charging / BMS | 29 | 29 (12 partial/full + 17 Stage 4 only) | Yes |
| Environmental Sensors | 7 | 7 | Yes |
| GNSS | 7 | 7 | Yes |
| On-Skin / Biometrics | 3 | 3 | Yes |
| Button / SOS / Haptic | 9 | 9 | Yes |
| NFC | 1 | 1 | Yes |
| FUOTA | 1 | 1 | Yes |
| VSM / IPC | 1 | 1 | Yes |
| Cloud Messages / Temp | 1 | 1 | Yes |
| **Total** | **89** | **89** | **Yes** |

### 5.3 Coverage Distribution

From Stage 3 Section 12.2:

| Coverage Level | Count | Percentage |
|---------------|-------|-----------|
| Stage 3 Full | 44 | 49% |
| Stage 3 Partial | 19 | 21% |
| Stage 4 Only | 26 | 29% |

### 5.4 Minor Categorization Note

`alpha-prdtst-reference.md` places PRDTST-401 ("Device Must Operate Within -20C to +60C") under "Cloud Messages" (line 300). The Stage 3 mapping table correctly categorizes it under "Cloud / Temp Range." The reference doc's category header is misleading but does not affect coverage.

---

## 6. CoreCloud Consistency Audit

### 6.1 Class Name and Interface

| Aspect | Stage 3 (Before Fix) | Stage 4 | After Fix |
|--------|----------------------|---------|-----------|
| Class name | `CloudAccess` | `CloudClient` | **`CloudClient`** (both) |
| Constructor | `CloudAccess(device_id, db_env)` | `CloudClient()` (env vars) | Stage 3 keeps explicit params |
| Concurrency | `async` | `sync` | Intentional difference (see P2-4) |
| REST interface | `CoreCloudRestInterface(namespace=)` | `CoreCloudRestInterface(env_namespace=)` | **`env_namespace=`** (both) |
| DB env default | `"VAL_1_0"` | `"VAL_1_0"` | Consistent |

### 6.2 Message UIDs

| Message | Stage 3 (Before Fix) | Stage 4 | After Fix |
|---------|----------------------|---------|-----------|
| PositionMsgV6 | 558 | 556 | **556** (both) |
| BiometricDataMsg | 557 | 557 | Consistent |
| BootMsgV2 | 548 | 548 (implicit) | Consistent |
| GPSConfMsg | 524 | 524 (implicit) | Consistent |

### 6.3 Message Verification Pattern

Both stages use the same core pattern:
1. Record timestamp before action
2. Trigger device action
3. Poll `msg_class.since_server_time(device_id, since, db_env=)` in a loop
4. Return latest match or timeout

The implementation is compatible despite the async/sync difference.

### 6.4 Namespace Alignment

| Document | Namespace | Status |
|----------|-----------|--------|
| arch-stage3 | `VAL_1_0` | Correct |
| arch-stage4 | `VAL_1_0` | Correct |
| BOM I26 (before fix) | `DEV_1_0` | **Fixed to `VAL_1_0`** |

---

## 7. BOM Gap Analysis

### 7.1 Component Coverage

Verified that every major implementation artifact referenced in the arch docs has a corresponding BOM line item.

| Component | Arch Doc Reference | BOM Item | Status |
|-----------|--------------------|----------|--------|
| LSM6DSO fresh driver | arch-stage1 2.1, BOM F05 | F05 (40h) | Covered |
| Stub driver | arch-stage1 2.1, BOM F03 | F03 (8h) | Covered |
| DTS bindings | arch-stage1 2.1, BOM F04 | F04 (4h) | Covered |
| Interface tests | arch-stage1 3.x, BOM F06 | F06 (16h) | Covered |
| App-level tests | arch-stage1 4.x, BOM F10 | F10 (20h) | Covered |
| concord_harness module | arch-stage3 3.x, BOM I16 | I16 (24h) | Covered |
| MTIB client | arch-stage2 5.x, BOM I10 | I10 (12h) | Covered |
| cloud_client.py | arch-stage3 10.x, arch-stage4 4.x, BOM I22 | I22 (incl in I18) | Covered |
| Pipeline controller | doc-09, BOM I04 | I04 (24h) | Covered |
| Dev-kit fixture | arch-stage2 2.x, BOM H01-H05 | H01-H05 | Covered |

### 7.2 BOM vs Doc Naming Alignment

| BOM Term | Doc Term | Consistent? |
|----------|----------|-------------|
| `accel_drv` | `accel_drv` (all arch docs) | Yes |
| `VAL_1_0` (after fix) | `VAL_1_0` (Stage 3, 4) | Yes (was `DEV_1_0`) |
| `cloud_client.py` | `CloudClient` class | Yes (after P0-2 fix) |
| `MAX17063` fuel gauge | Stage 3: MAX17063, Stage 4: MAX17063 (after fix) | Yes (was BQ27427 in Stage 4) |
| `BQ25622` charger | Stage 3: BQ25622, Stage 4: BQ25622 (after fix) | Yes (was BQ25180 in Stage 4) |

### 7.3 Effort Totals

BOM total: ~763h across all stages. This is higher than the V1 review estimate (~400-475h) because the BOM includes:
- Stage 4 implementation (not estimated in V1)
- Documentation updates (D01-D07)
- Container images (C01-C03)
- Hardware fixtures (H01-H05)

---

## 8. Naming Consistency Audit

### 8.1 Repository Name

| Document | Uses `accel_drv`? | Uses `accelerometers`? | Status |
|----------|-------------------|----------------------|--------|
| 00-validation-philosophy.md | Yes | 2 conceptual uses (sensor type) | Clean |
| 09-final-architecture.md | Yes (after P1-1 fix) | 2 conceptual uses (sensor type) | **Fixed** |
| arch-stage1-software-tests.md | Yes | No | Clean |
| arch-stage2-driver-hw-tests.md | Yes | No | Clean |
| arch-stage3-integration-tests.md | Yes | No | Clean |
| arch-stage4-product-tests.md | Yes | No | Clean |
| bom-validation-pipeline.md | Yes | No | Clean |
| 10-stage3-alpha-example.md | Yes | No | Clean |
| 11-stage1-alpha-example.md | Yes | No | Clean |
| 12-stage2-alpha-example.md | Yes | No | Clean |

### 8.2 DTS Vendor Prefix

All documents now consistently use `ck,` prefix. No remaining `corekinect,` device binding references (the board-level compatible `corekinect,devkit-nrf52840-lsm6dso-spi` in arch-stage2 is intentionally different -- board compatibles use full vendor name).

### 8.3 Driver Path

| Document | Path | Status |
|----------|------|--------|
| arch-stage1 (canonical) | `drivers/lsm6dso/` | Canonical |
| doc-00 | `drivers/lsm6dso/` (after P0-5 fix) | **Fixed** |
| doc-11 | `drivers/lsm6dso/` (after P0-5 fix) | **Fixed** |
| BOM (lines 92, 874, 915) | `lsm6dso_drv/drivers/corekinect/sensors/lsm6dso/` | Intentional (existing codebase reference) |

### 8.4 DTS Bindings Path

| Document | Path | Status |
|----------|------|--------|
| arch-stage1 tree (canonical) | `dts/bindings/` | Canonical |
| arch-stage1 code ref (line 296) | `dts/bindings/` (after P1-5 fix) | **Fixed** |
| doc-00 | `dts/bindings/` (after P1-5 fix) | **Fixed** |
| doc-11 | `dts/bindings/` (after P1-5 fix) | **Fixed** |

### 8.5 State Machine Names

All documents use the real Alpha state names (`off_body_e`, `low_heat_risk_e`, etc.) after V1 fixes. No remaining placeholder names.

### 8.6 Build Variants

| Variant | Stage 3 | Stage 4 | Consistent? |
|---------|---------|---------|-------------|
| Instrumented | CONFIG_CONCORD_HARNESS=y, CONFIG_LOG=y | N/A | N/A |
| Debug | N/A | CONFIG_CONCORD_HARNESS=n, CONFIG_LOG=y | Yes |
| Release | N/A | CONFIG_CONCORD_HARNESS=n, CONFIG_LOG=n | Yes |

Stage 3 always uses the instrumented build; Stage 4 never uses the harness. This is architecturally correct and consistent.

---

## 9. Recommendations

### Immediate (Before Implementation Starts)

1. **Verify fuel gauge and charger IC part numbers against Alpha B0 schematic.** The P0-3 and P0-4 fixes assume MAX17063 + BQ25622 based on document consensus (3 vs 1). If the schematic says otherwise, update all 4 documents accordingly.

2. **Review the harness point list** in arch-stage3 Section 11.12. The corrected count is 76 (up from the stated 62). Confirm all 76 points are needed, and set `CONCORD_HARNESS_MAX_POINTS` to 96.

3. **Decide on doc-10 rewrite** (P2-1). If implementation starts from arch-stage3 (likely), doc-10 can be deferred. If doc-10 will be used as a tutorial, it needs the structural rewrite.

### Before Stage 3 Implementation

4. **Design the unified `CloudClient` class** (P2-4) that serves both async (Stage 3) and sync (Stage 4) use cases. This affects BOM item I22.

### Before Stage 4 Implementation

5. **Create Stage 4 test index table** (P2-2) cross-referencing Stage 3 Section 12.

### Documentation Maintenance

6. **Reconcile doc-09 pipeline.yaml schema** with arch-stage1 (P2-3). This can be done during Stage 1 Phase 5 implementation when the actual schema is finalized.

7. **Update V1 cohesion review** (cohesion-review.md) Section 1.9 to correct the driver path direction. V1 incorrectly stated the canonical path was `drivers/corekinect/sensors/lsm6dso/`; the correct canonical path is `drivers/lsm6dso/`.

---

## Appendix A: Complete Fix Log

| ID | File | Line(s) | Change | Severity |
|----|------|---------|--------|----------|
| P0-1 | arch-stage3-integration-tests.md | 1721 | UID 558 -> 556 | P0 |
| P0-2 | arch-stage3-integration-tests.md | 1655, 1660, 1661 | CloudAccess -> CloudClient | P0 |
| P0-3 | arch-stage4-product-tests.md | 110 | BQ27427 -> MAX17063 | P0 |
| P0-4 | arch-stage4-product-tests.md | 110 | BQ25180 -> BQ25622 | P0 |
| P0-5a | 00-validation-philosophy.md | 290 | drivers/corekinect/sensors/lsm6dso/ -> drivers/lsm6dso/ | P0 |
| P0-5b | 11-stage1-alpha-example.md | 66 | drivers/corekinect/sensors/lsm6dso/ -> drivers/lsm6dso/ | P0 |
| P1-1 | 09-final-architecture.md | 26 occurrences | accelerometers -> accel_drv (repo name only) | P1 |
| P1-2 | bom-validation-pipeline.md | 219 | DEV_1_0 -> VAL_1_0 | P1 |
| P1-3 | 10-stage3-alpha-example.md | 193 | concord_harness.h -> concord_harness/concord_harness.h | P1 |
| P1-4 | arch-stage3-integration-tests.md | 1944-1950 | Count corrections: 34->47, 8->7, 15->17, 62->76 | P1 |
| P1-5a | arch-stage1-software-tests.md | 296 | dts/bindings/sensor/ -> dts/bindings/ | P1 |
| P1-5b | arch-stage1-software-tests.md | 1067 | dts/bindings/sensor/ -> dts/bindings/ | P1 |
| P1-5c | 00-validation-philosophy.md | 292 | dts/bindings/sensor/ -> dts/bindings/ | P1 |
| P1-5d | 11-stage1-alpha-example.md | 73 | dts/bindings/sensor/ -> dts/bindings/ | P1 |
| P1-6 | arch-stage3-integration-tests.md | 1666 | namespace= -> env_namespace= | P1 |
| P1-7 | bom-validation-pipeline.md | 92 | Added clarifying note | P1 |
