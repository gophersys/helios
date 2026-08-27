# Stage 4 Proof — Overview

> **Goal:** Prove black-box product validation of production Alpha B0 firmware
> on real hardware — physical stimulus via MTIB GPIO/ADC/motion, verification
> via CoreCloud message inspection and power measurement, zero instrumentation.
>
> **Relationship to Stage 3+4 combined plan:** This plan extracts Stage 4
> into a standalone proof. It updates the V1 MTIB server
> peripheral-by-peripheral, skips all `concord_harness` infrastructure
> (Stage 3), and builds only the test framework and test cases needed to run
> 64 product tests on debug and release firmware. The TestContext interface
> is designed so Stage 3 can plug in later by adding HarnessTransport —
> nothing is discounted, just deferred.
>
> **Estimated Effort:** ~194h engineering + ~$450–1,600 hardware
>
> **Test Hardware:** 2 MTIB nodes (REV 1.1 + REV 1.2) in K3s cluster, each
> with Alpha B0 connected in manufacturing fixture configuration. Full
> manufacturing test capability (power, ADC, UART, SWD, GPIO) available
> from Day 1 — TDD possible immediately.
>
> **Date:** 2026-03-01

---

## Engineering Protocol

Every work unit in this plan touches production systems — a live K8s
cluster, deployed MTIB servers, real hardware, an active CoreCloud
environment. The cost of a wrong assumption is high: broken manufacturing
pipelines, bricked devices, corrupted test data. Move deliberately.

### Before Starting Any Work Unit

1. **Read the existing code.** Before modifying a handler, client, proto,
   manifest, or build script — read what's there today. Understand the
   current behavior, data flow, and edge cases. Do not design against an
   assumption of what the code does; design against what it actually does.

2. **Check Confluence.** Use the Confluence MCP server (read-only) to
   search for relevant documentation — hardware specs, MTIB design docs,
   firmware architecture notes, manufacturing procedures, and CoreCloud
   API docs. Search before you ask.

3. **Query live systems.** The K8s cluster, MTIB servers, CoreCloud
   validation instance, and firmware build system are all accessible.
   Use them to verify assumptions:
   - `kubectl get nodes/pods/deployments` — verify cluster state
   - `grpcurl` — verify MTIB server RPCs and responses
   - CoreCloud SDK — query the DB, call the REST API, check message schemas
   - Build firmware the way the build server would — use the same scripts
     and configs

4. **Compare V1 and V2 code.** The V2 server (`apps/edge/mtib-server-v2/`)
   already implements many features that Phase 1 adds to V1 — hardware
   auto-detection, TCA9534A driver, J-Link mux, motor power control,
   per-revision MCP4017 voltage calculation. V2 is the reference
   implementation. Read it before writing new code for V1.

5. **Call out inconsistencies.** If you find something that contradicts
   this plan, contradicts the code, or contradicts documentation — stop
   and flag it. Do not paper over it. Examples found during plan creation:
   - V1's GPIO pin maps for REV 1.1 and REV 1.2 are identical — is this
     intentional or a copy-paste artifact?
   - V1 uses `HARDWARE_VERSION` (string: "REV1.1"), V2 uses
     `MTIB_HARDWARE_REVISION` (numeric: "1.2") — naming inconsistency
   - The existing `validation.yaml` sets `HARDWARE_VERSION=REV1.1` but
     the validation node `verdin-imx8mm-15702161` may actually be REV 1.2
   - `MOTION_ENABLED` controls whether motion RPCs are exposed — it's
     about the scaffold, not the hardware revision. Both revisions can
     do motion.

### What's Available for Investigation

| Resource | How to Access | Use For |
|----------|--------------|---------|
| K3s cluster | `kubectl` (cluster-admin) | Node state, pod state, labels, deployments |
| MTIB V1 servers | `grpcurl -plaintext <ip>:50053` | RPC verification, health checks |
| CoreCloud VAL_1_0 | `CoreCloudDBInterface(db_env='VAL_1_0')` | DB queries, message schemas, device records |
| CoreCloud REST API | `requests.get(f'{API_URL}/...')` | API verification, endpoint discovery |
| Firmware build system | `bash scripts/build.sh` (in alpha_fw repo) | Build exactly like CI would |
| Confluence | MCP server (read-only) | Hardware specs, architecture docs, procedures |
| Concord monorepo | This repo | All server, client, proto, deploy, and test code |
| V2 reference implementation | `apps/edge/mtib-server-v2/src/` | Reference for TCA9534A, auto-detection, etc. |

### Known Inconsistencies (Investigate Before Assuming)

These were discovered during plan creation by reading existing code.
Each should be investigated and resolved before the relevant work unit
starts.

| # | Inconsistency | Relevant Work Unit | Impact |
|---|--------------|-------------------|--------|
| 1 | V1 GPIO maps identical for REV 1.1 and 1.2 (`providers/mtib.py:35-68`) | M3 (GPIO) | Are pin assignments actually different? Check schematic. |
| 2 | V1 `HARDWARE_VERSION` vs V2 `MTIB_HARDWARE_REVISION` naming | M1 (Proto), M9 (Cleanup) | Which convention do we follow? Standardize. |
| 3 | ~~`validation.yaml` says `HARDWARE_VERSION=REV1.1`~~ **Resolved:** old deployment targets absent node. Will be replaced by per-revision manifests. | Phase 0 (K8s) | Old manifest is dead — create new ones. |
| 4 | V1 MCP4017 voltage calculation assumes 100kΩ pot for all revisions | M2 (Power) | REV 1.2 uses 10kΩ pot — voltage will be wrong. Check `services/mcp4017.py`. |
| 5 | V1 has no TCA9534A code at all — Phase 1 adds it from scratch | M6 (Flash), M7 (Motion) | Use V2's `hardware/tca9534a.py` as reference, not guesswork. |
| 6 | Manufacturing code imports `DutPowerRequest` directly from proto | M1 (Proto), M9 (Cleanup) | Breaking change if RPCs renamed without aliases. |
| 7 | V1 `METRICS_ENABLED` + `METRICS_BROKER_URL` env vars in manifests | M8 (Observability) | V1 may have existing MQTT metrics code — read it before building new observability. |
| 8 | UART port paths: V1 uses `/dev/ttyUSB0`, hardware rules say `/dev/verdin-uart1` and `/dev/verdin-uart2` | M5 (UART) | Are these the same physical ports? Verify on live hardware. |

---

## Parallelization Strategy

This plan is designed to run across **2 Claude instances + physical hardware
setup** in parallel from Day 1:

```
Claude Instance 1                Claude Instance 2          You (hardware)
──────────────────                ──────────────────         ──────────────
Phase 1: MTIB server              Phase 0: prereqs           DONE (K8s + HW)
├── M1: Proto (first)             ├── CoreCloud env          ✓ 2 Verdins flashed
├── M2: Power                     ├── Build ALL firmware     ✓ Both in K3s
├── M3: GPIO                      │   assets (9 hexes)       ✓ Labels applied
├── M4: ADC                       ├── TDD: flash + verify    ✓ Alphas connected
├── M5: UART                      │   each hex on real HW       (mfg fixture)
├── M6: Flash                     ├── Device personalization
├── M7: Motion                    └── POST verification      Later (Phase 2B):
├── M8: Observability                                        ├── Button relay
├── M9: Cleanup + client     ──► Phase 2: Test framework     ├── Charger relay
└── M10: Deploy + verify          (starts after Phase 1)     ├── Photodiode
                                                              ├── Peltier + NTC
                                                              └── NFC reader
```

**Rule:** Claude Instance 1 owns the MTIB server. Claude Instance 2 handles
everything else — firmware builds, CoreCloud, test framework. Hardware setup
(K8s + Alpha connection) is already done. Stage 4 stimulus wiring (relays,
sensors) happens when parts arrive and can overlap with Phase 2A.

---

## What Already Exists (Production)

These components are deployed and battle-tested in manufacturing. This plan
builds on top of them.

| Component | Location | Status |
|-----------|----------|--------|
| MTIB V1 gRPC server (26 RPCs) | `apps/edge/mtib-server/` | Production, deployed on K3s |
| MTIB V1 Python client | `libs/python/corekinect/mtib_client/v1/` | Production |
| CoreCloud SDK (DB + REST) | `libs/python/corekinect/core_cloud/` | Production, 10+ message classes |
| Manufacturing test patterns | `apps/manufacturing/alpha/src/tests/` | Proven in manufacturing |
| K3s cluster + infra scripts | `deploy/infra/v2/` | Production, 11 nodes (3 server + 3 agent + 5 edge) |
| Node labeling + taints | `deploy/infra/v2/00-labels-taints.sh` | Production, idempotent |
| MTIB K8s manifests | `deploy/edge/mtib-server/` | Manufacturing (4 replicas) + validation (1 replica) |

### Test Hardware

| Node | Address | HW Revision | K8s Hostname | Notes |
|------|---------|-------------|-------------|-------|
| MTIB-A | 10.4.45.33 | REV 1.2 | `verdin-imx8mm-15005665` | TCA9534A, J-Link mux, motor switch |
| MTIB-B | 10.4.45.32 | REV 1.1 | `verdin-imx8mm-15702161` | No GPIO expander, no J-Link mux |

### K8s Infrastructure

**Cluster state as of 2026-03-01 (verified via `kubectl`):**

| Resource | Status |
|----------|--------|
| Total cluster nodes | 8 (3 server + 3 agent + 2 validation edge) |
| REV 1.2 validation node | `verdin-imx8mm-15005665` at 10.4.45.33 — labeled, Ready |
| REV 1.1 validation node | `verdin-imx8mm-15702161` at 10.4.45.32 — labeled, Ready |
| Manufacturing edge nodes | 0 — removed from cluster (clean slate for validation) |
| Validation MTIB deployments | 0 — per-revision manifests not yet created |
| K3s version | Servers/agents: `v1.33.5`, edge: `v1.28.7` — skew noted, acceptable for now |
| Edge node K8s roles | `<none>` — need to assign roles (see infra TODO) |

**Infra debt (deferred, tracked in `deploy/infra/v2/TODO.md`):**
- `00-labels-taints.sh` references 5 manufacturing + 1 validation node
  that no longer exist. Needs cleanup to match current 2-node validation cluster.
- K3s version skew: edge nodes at v1.28.7 vs cluster v1.33.5 (5 minor
  versions). Acceptable for Stage 4 proof but should be resolved before
  production validation.
- Edge nodes have no K8s roles assigned (`ROLES: <none>`). Should assign
  roles for consistency.

---

## What This Plan Builds

### Phase 1: MTIB Server Updates (~48h)

Update the V1 server peripheral-by-peripheral to add Stage 4 capabilities.
The user works with Claude on each handler in focused sessions.

| ID | Work Unit | Effort |
|----|-----------|--------|
| M-01 | Proto + health (update proto to 23 RPCs) | 4h |
| M-02 | Power handler (consolidate 6→5 RPCs, add PowerMeasure + PowerStream) | 8h |
| M-03 | GPIO handler (add GpioWatch streaming) | 3h |
| M-04 | ADC handler (add AdcStream) | 3h |
| M-05 | UART handler (cleanup, harden broadcast) | 3h |
| M-06 | Flash handler (remove file mgmt, add streaming, REV 1.2 J-Link mux) | 6h |
| M-07 | Motion handler (REV 1.2 motor power switch) | 3h |
| M-08 | Observability (new: GetSnapshot) | 10h |
| M-09 | Cleanup + client update | 4h |
| M-10 | Deploy + verify all 23 RPCs | 4h |

### Phase 0: Firmware Assets (~8h)

Build all firmware variants for both MTIB revisions. REV 1.1 has UART TX/RX
swapped on the carrier board — nRF firmware needs a DTS overlay to
compensate. REV 1.2 fixed this in hardware.

| ID | Asset | MTIB Rev | Effort |
|----|-------|----------|--------|
| FW-01 | REV 1.1 pin swap DTS overlay (`alpha_b0_nrf52840_mtib11.overlay`) | 1.1 | 2h |
| FW-02 | 9 firmware hex files (3 variants × 2 MTIB revs × nRF52840 + 3 nRF9151) | Both | 4h |
| FW-03 | Verify UART + POST on both MTIB revisions | Both | 2h |

**Naming convention:** `<product>_<variant>_<mcu>_<mtib_rev>.hex`
```
alpha_mfg_nrf52840_mtib11.hex      alpha_mfg_nrf52840_mtib12.hex
alpha_debug_nrf52840_mtib11.hex    alpha_debug_nrf52840_mtib12.hex
alpha_release_nrf52840_mtib11.hex  alpha_release_nrf52840_mtib12.hex
alpha_mfg_nrf9151.hex              alpha_debug_nrf9151.hex
alpha_release_nrf9151.hex
```

Stored at: `libs/corekinect/test/validation/assets/firmware/`

### Phases 2-4: Test Framework + Tests + Comparison (~150h)

| ID | Component | Location | Effort |
|----|-----------|----------|--------|
| S-01 | CloudClient (polling wrappers) | `libs/corekinect/test/validation/cloud_client.py` | 8h |
| S-02 | FixtureController | `libs/corekinect/test/validation/fixture_controller.py` | 24h |
| S-03 | UartDemuxer (log capture) | `libs/corekinect/test/validation/uart_demuxer.py` | 4h |
| S-04 | PowerProfiler | `libs/corekinect/test/validation/power_profiler.py` | 4h |
| S-05 | TestContext + conftest | `libs/corekinect/test/validation/test_context.py` | 10h |
| S-06 | Fixture profile JSON (per MTIB revision) | `libs/corekinect/test/validation/fixtures/` | 4h |
| T-01 | Stage 4 test modules (7 modules, 64 tests) | `libs/corekinect/test/validation/tests/stage4/` | 48h |
| T-02 | Debug E2E run + debug | — | 8h |
| T-03 | Release E2E run + debug | — | 8h |
| H-01 | Alpha B0 board | — | $200-400 |
| H-02 | Fixture wiring (both MTIB revisions) | — | 32h + parts |
| H-03 | Motion scaffold | — | $200-1,000 |

**Software total:** 8 (assets) + 48 (MTIB) + 54 (framework) + 64 (tests) = **~174h**
**Fixture wiring:** **~20h** (reduced from 32h — manufacturing baseline already wired)
**Grand total:** **~194h**

---

## Repositories & Branch Strategy

| Repository | Hosting | Base Branch |
|-----------|---------|-------------|
| **concord** | Bitbucket | `v2/init` |
| **alpha_fw** | Bitbucket | `feat/concord_integration_pod` |

Branch naming: `<type>/<description>` (feat, fix, chore, docs, test, refactor)

Merge flow: Feature branch → PR (human-reviewed, human-merged) → base branch.
Never auto-commit. No AI references in any git operation.

### Key Paths in Concord Monorepo

| Path | What |
|------|------|
| `apps/edge/mtib-server/` | MTIB V1 server (Phase 1 updates this) |
| `libs/protocols/mtib/mtib.proto` | V1 proto definition (Phase 1 updates this) |
| `libs/python/corekinect/mtib_client/v1/` | V1 Python client (Phase 1 updates this) |
| `libs/python/corekinect/core_cloud/` | CoreCloud SDK (production, unchanged) |
| `libs/corekinect/test/validation/` | Test framework library (Phase 2 builds this) |
| `libs/corekinect/test/validation/tests/stage4/` | Stage 4 test modules (Phase 3 writes them) |
| `libs/corekinect/test/validation/assets/firmware/` | Pre-built firmware hexes for both MTIB revisions |
| `apps/firmware/products/alpha/` | Firmware build system (source of hex assets) |
| `deploy/infra/v2/00-labels-taints.sh` | Node labeling script (Phase 0 updates this) |
| `deploy/edge/mtib-server/validation.yaml` | Current validation deployment (Phase 0 splits into per-revision) |
| `deploy/edge/mtib-server/validation-rev11.yaml` | New: REV 1.1 validation deployment (Phase 0 creates) |
| `deploy/edge/mtib-server/validation-rev12.yaml` | New: REV 1.2 validation deployment (Phase 0 creates) |

---

## Hardware Topology

```
┌────────────────────────────────────────────────────────────────────────────┐
│  K3s CLUSTER — VALIDATION EDGE NODES                                      │
│                                                                            │
│  Node A (REV 1.2)                           Node B (REV 1.1)              │
│  ┌──────────────────────────────┐           ┌──────────────────────────┐  │
│  │ Verdin iMX8MM (K3s agent)   │           │ Verdin iMX8MM (K3s agent)│  │
│  │ └── MTIB Carrier REV 1.2   │           │ └── MTIB Carrier REV 1.1│  │
│  │     ├── TCA9534A (0x38)    │           │     ├── No TCA9534A     │  │
│  │     ├── J-Link mux         │           │     ├── Direct J-Link   │  │
│  │     ├── Motor switch       │           │     ├── No motor switch │  │
│  │     └── 48-pin DUT         │           │     └── 48-pin DUT      │  │
│  │         └── Fixture Board  │           │         └── Fixture Board│  │
│  │             └── Alpha B0   │           │             └── Alpha B0 │  │
│  └──────────────────────────────┘           └──────────────────────────┘  │
│                                                                            │
│  LINEAR RAIL SCAFFOLD (FluidNC ESP32 — both nodes, scaffold is per-node)  │
└────────────────────────────────────────────────────────────────────────────┘
```

| MTIB Resource | Count | Stage 4 Usage |
|--------------|-------|---------------|
| GPIO (DUT) | 7 pins | Button sim, on-skin electrode, charger relay |
| ADC | 8 channels | Photodiode RGB, thermistor, signal taps |
| Power (DUT) | 1 ch, mA sense | Battery sim (4.5V), current measurement |
| Power (CHG) | 1 ch | Charger simulation (limited) |
| SWD | 2 J-Link (muxed) | Flash debug + release firmware |
| UART | 2 ports | Log capture (debug build only) |
| Motion | 1 axis | Accelerometer stimulus |

---

## Firmware Builds

Stage 4 tests two nRF52840 builds. The nRF9151 `comm_coproc_mfg` firmware is
the same across both. No integration (harness) build is needed.

| Build | nRF52840 Config | UART Output | Purpose |
|-------|----------------|-------------|---------|
| Production Debug | HARNESS=n, LOG=y, SHELL=n | Logs only | Diagnostic visibility for failure analysis |
| Production Release | HARNESS=n, LOG=n, SHELL=n | Silent | Shipping binary — authoritative results |

---

## Work Streams & Dependency Graph

```
Phase 0 ──► Phase 1 ──► Phase 2 (parallel) ──► Phase 3 ──► Phase 4
             │           │                       │
             │           ├── Stream A (Python)   │
             │           │                       └── Stream C (tests + E2E)
             │           └── Stream B (fixture)
             │
             └── M1-M10 (peripheral-by-peripheral)
                                     C depends on A, B
                                     A depends on Phase 1
```

| Stream | Phase | Effort | Dependencies |
|--------|-------|--------|-------------|
| M: MTIB server updates | 1 | 48h | None (V1 server is the starting point) |
| A: Python test framework | 2 | 54h | Phase 1, CoreCloud access |
| B: Hardware fixture wiring | 2 | 20h | Parts arrived (manufacturing baseline already wired) |
| C: Stage 4 test modules + E2E | 3 | 64h | A, B |

**Critical path:** M (48h) → A (54h) → C (64h) = **166h sequential (~4 weeks)**

Stream B (fixture wiring) runs in parallel with Streams M and A. If hardware
arrives early, wiring can begin during Phase 1.

---

## Verification Checkpoints

| Phase | Checkpoint | Pass Criteria |
|-------|-----------|--------------|
| 0 | Infra ready | 2 validation nodes in K3s, device personalized, CoreCloud accessible, V1 server on both nodes |
| 1 | MTIB updated | All 23 RPCs verified on real hardware, deployed to K3s |
| 2 | Foundation | CloudClient returns real data, FixtureController drives GPIO/ADC, fixture wired |
| 3 | **Stage 4 proof** | 64 PRDTST tests pass on debug build, 64 pass on release build |
| 4 | Comparison | Debug/release discrepancies documented, power budget compared |

---

## What This Plan Does NOT Build (and Why)

These components belong to Stage 3 or the FUOTA validation flow. They are
designed in the architecture docs and can be layered on after Stage 4 proves
out. Nothing here is discounted — it's deferred.

| Component | Why Deferred | How It Plugs In Later |
|-----------|-------------|----------------------|
| `concord_harness` Zephyr module | Stage 3 only (harness macros, shell) | Add to alpha_fw manifest, build integration overlay |
| HarnessTransport | Stage 3 only (shell commands over UART) | Add to TestContext as `ctx.harness` |
| FUOTA 12-step validation flow | Requires FUOTA plan API + `.cfw` upload | Phase 5 of this plan (documented, not executed) |
| Alpha firmware overlay changes | No harness overlay needed for Stage 4 | Stream B of combined plan adds harness overlay |

### TestContext Extensibility

The TestContext is designed with Stage 3 in mind:

```python
class TestContext:
    mtib: MtibV1Client          # MTIB hardware control (updated in Phase 1)
    cloud: CloudClient          # CoreCloud polling (Phase 2)
    fixture: FixtureController  # Physical stimulus (Phase 2)
    uart: UartDemuxer           # UART log capture (Phase 2)
    power: PowerProfiler        # Power measurement (Phase 2)
    logs: LogBuffer             # UART log access (Phase 2)
    # --- Stage 3 adds these later ---
    # harness: HarnessTransport # Shell command API (Stage 3)
```

Adding Stage 3 means adding `HarnessTransport` to TestContext and upgrading
the `UartDemuxer` to route `[CONCORD:RSP]` and `[CONCORD:EVT]` prefixes.
No other changes needed.

---

## Known Limitations

1. **1 Alpha unit** — dev parallelizes, testing serializes
2. **Charging untestable** — same MTIB source for DUT + CHG (29 tests deferred)
3. **Power resolution ~mA** — INA219 cannot measure µA sleep current
4. **Fixture mapping TBD** — GPIO/ADC assignments need Alpha B0 schematic verification
5. **CoreCloud URL TBD** — Stage 4 blocked until environment URL is known
6. **18 Config Value tests deferred** — waiting on GroundModeConfigV2 endpoint
7. **7 GNSS tests deferred** — scaffold is indoors, no GPS signal source
8. **No BLE** — deferred from this POC
9. **Device personalization required** — nRF9151 needs certs/keys for LTE+CoreCloud
10. **FUOTA not in initial proof** — requires `.cfw` upload endpoint + FUOTA plan API

---

## Key References

| Document | What |
|----------|------|
| `architecture/stage4-product-tests.md` | Stage 4 requirements, test definitions, fixture profile |
| `architecture/stage4-fuota-validation-flow.md` | 12-step FUOTA lifecycle (Phase 5 of this plan) |
| `architecture/corecloud-library-architecture.md` | CoreCloud SDK analysis, message types, query API |
| `plans/stage3-and-4/overview.md` | Combined Stage 3+4 plan (this plan extracts Stage 4) |
| `plans/mtib-server-redesign.md` | MTIB server redesign spec (23 RPCs, informs Phase 1) |

---

## Phase Documents

| Phase | Document | Streams |
|-------|----------|---------|
| 0 | [phases/phase-0-prerequisites.md](phases/phase-0-prerequisites.md) | — |
| 1 | [phases/phase-1-mtib-server-extension.md](phases/phase-1-mtib-server-extension.md) | M (peripheral-by-peripheral) |
| 2 | [phases/phase-2-test-infrastructure.md](phases/phase-2-test-infrastructure.md) | A, B |
| 3 | [phases/phase-3-product-test-proof.md](phases/phase-3-product-test-proof.md) | C |
| 4 | [phases/phase-4-comparison.md](phases/phase-4-comparison.md) | — |
| 5 | [phases/phase-5-fuota-flow.md](phases/phase-5-fuota-flow.md) | — (designed, not executed) |
