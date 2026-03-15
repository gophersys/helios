# Stage 3 & 4 Proof — Overview

> **Goal:** Prove end-to-end firmware validation on real Alpha B0 hardware:
> - **Stage 3 (Integration):** Instrumented firmware with `concord_harness`
>   shell commands — software-driven stimulus and internal state observation
> - **Stage 4 (Product Validation):** Production firmware (debug + release)
>   with black-box verification via CoreCloud, MTIB GPIO/ADC physical stimulus,
>   and power measurement — zero instrumentation
>
> **Estimated Effort:** ~360h engineering + ~$450–1,600 hardware
>
> **Date:** 2026-02-25

---

## Repositories & Branch Strategy

| Repository | Hosting | Location | Base Branch |
|-----------|---------|----------|-------------|
| **concord** | Bitbucket | `~/work/concord/concord/` | `v2/init` |
| **concord_harness** | GitHub | `https://github.com/MateoSegura/concord_harness` | `main` |
| **alpha_fw** | Bitbucket | `~/work/firmware/alpha_fw/` | `feat/concord_integration_pod` |

Branch naming: `<type>/<description>` (feat, fix, chore, docs, test, refactor)

Merge flow: Feature branch → PR (human-reviewed, human-merged) → base branch.
Never auto-commit. No AI references in any git operation.

### Key Paths in Concord Monorepo

| Path | What |
|------|------|
| `apps/edge/mtib-server/` | MTIB server (redesigned) |
| `apps/validation/test-runner/` | Validation runner app (Nx project, env config, CLI) |
| `libs/protocols/mtib/mtib.proto` | Proto definition (23 RPCs) |
| `libs/corekinect/test/validation/` | Python test framework library |
| `libs/python/corekinect/core_cloud/` | CoreCloud SDK (exists) |
| `deploy/edge/mtib-server/` | K8s manifests |

---

## Hardware Topology

```
┌─────────────────────────────────────────────────────────────┐
│  LINEAR RAIL SCAFFOLD (X axis, 500mm travel, FluidNC ESP32) │
│                                                             │
│  Verdin iMX8M Mini (K3s node: verdin-imx8mm-15702160)     │
│  └── MTIB Carrier Board REV 1.2                            │
│      └── 48-pin DUT connector                              │
│          └── Fixture Board                                  │
│              └── Alpha B0 (nRF52840 + nRF9151)             │
└─────────────────────────────────────────────────────────────┘
```

| MTIB Resource | Count | Used For |
|--------------|-------|----------|
| GPIO (DUT) | 7 pins | Button sim, on-skin, charger relay |
| ADC | 8 channels | Photodiode, thermistor, signal taps |
| Power (DUT) | 1 ch, mA sense | Main device power (0.8-5.5V) |
| Power (CHG) | 1 ch, mA sense | Charger simulation (limited) |
| SWD | 2 J-Link (muxed) | Firmware flashing |
| UART | 2 ports | Shell/harness/logs (115200 baud) |
| Motion | 1 axis | Accelerometer stimulus |

---

## Firmware Builds

Alpha is a dual-MCU product: nRF52840 (app) + nRF9151 (comms/LTE). Both MCUs
must be built and flashed. The nRF9151 `comm_coproc_mfg` firmware is the same
across all variants. The nRF52840 app firmware has three overlay variants:

| Build | nRF52840 Config | nRF9151 | UART (nRF52840) | Stage |
|-------|----------------|---------|-----------------|-------|
| Integration | HARNESS=y, LOG=y, SHELL=y | comm_coproc_mfg (shared) | Shell + logs + events | 3 |
| Production Debug | HARNESS=n, LOG=y, SHELL=n | comm_coproc_mfg (shared) | Logs only | 4 |
| Production Release | HARNESS=n, LOG=n, SHELL=n | comm_coproc_mfg (shared) | Silent | 4 |

Build system: `west build --sysbuild` with board `alpha_b0`. Existing
`build_all.sh` / `flash_all.sh` scripts handle multi-chip builds.
nRF9151 build requires FIPS hash recalculation and encryption keys.

---

## BOM Components Summary

| ID | Component | Repo/Location | Kit | Effort |
|----|-----------|--------------|-----|--------|
| F-01 | concord_harness module | concord_harness | embedded-zephyr | 29.5h |
| F-02 | alpha_fw overlays + accessors | alpha_fw | embedded-zephyr | 34h |
| F-03 | FW harness integration | alpha_fw | embedded-zephyr | 30h |
| I-01 | MTIB server (redesign) | concord/apps/edge/mtib-server/ | cloud-python | 40h |
| I-02 | MTIB proto + bindings | concord/libs/protocols/mtib/ | cloud-python | 4h |
| I-03 | Python test framework (lib) | concord/libs/corekinect/test/ | cloud-python | 58h |
| I-04 | Fixture profile JSON | concord/libs/corekinect/test/ | cloud-python | 4h |
| I-05 | Stage 4 Python infra | concord/libs/corekinect/test/ | cloud-python | 36h |
| T-01 | Stage 3 test modules | concord/libs/corekinect/test/ | cloud-python | 28h |
| T-02 | Stage 4 test modules | concord/libs/corekinect/test/ | cloud-python | 64h |
| H-01 | Alpha B0 board | — | — | $200-400 |
| H-02 | Fixture wiring | — | — | 32h + parts |
| H-03 | Motion scaffold | — | — | $200-1,000 |

**Engineering total:** 29.5 + 34 + 30 + 40 + 4 + 58 + 4 + 36 + 28 + 64 + 32 (fixture) = **~360h**

Full interface definitions and system requirements for each component are
in the phase documents where the component is built.

---

## Work Streams & Dependency Graph

```
Phase 0 ──► Phase 1 (parallel) ──► Phase 2 ──► Phase 3 ──► Phase 4-5 ──► Phase 6
             │                       │
             ├── Stream A (harness)  ├── Stream E (FW integration)
             ├── Stream B (alpha)    ├── Stream F (Python framework)
             ├── Stream C (fixture)  │
             ├── Stream D (MTIB)     │
             └── Stream G (S4 infra) │
                                     │
                              E depends on A, B, D
                              F depends on D
```

| Stream | Phase | Effort | Dependencies |
|--------|-------|--------|-------------|
| A: concord_harness | 1 | 29.5h | None |
| B: alpha_fw changes | 1 | 34h | A (for harness overlay compile) |
| C: fixture wiring | 1 | 32h | Hardware arrived |
| D: MTIB server | 1 | 44h | None |
| G: Stage 4 Python infra | 1 | 36h | CoreCloud access |
| E: FW harness integration | 2 | 30h | A, B, D |
| F: Python test framework | 2 | 58h | D |
| H: Stage 3 tests | 3 | 28h | E, F |
| J: Stage 4 tests | 4-5 | 64h | G, F, C |

**Critical path:** D (44h) → F (58h) → H (28h) → J (64h) = **194h sequential (~5 weeks)**

---

## Verification Checkpoints

| Phase | Checkpoint | Pass Criteria | Status |
|-------|-----------|--------------|--------|
| 0 | Infra ready | K3s, registry, repos accessible | **PASS** |
| 1 | Foundation | Harness builds, FW compiles, MTIB deployed, fixture wired | **PASS** (fixture partially wired) |
| 2 | Integration | Shell commands work over MTIB UART on real Alpha | **PASS** |
| 3 | **Stage 3 proof** | 25 integration tests pass on hardware | Deferred (Stage 4 first) |
| 4-5 | **Stage 4 proof** | 64 PRDTST tests pass on debug + release builds | **IN PROGRESS** — 24P/23F/67S. 16 failures fixable in code (ch0→ch0+ch1 power). 7 need hardware wiring. |
| 6 | Comparison | Debug/release discrepancies documented | Pending Phase 4-5 |
| 6B | **Platform Integration** | Live results in UI, artifact downloads, run history | Backend + frontend built, wiring pending |

---

## Known Limitations

1. ~~**1 Alpha unit**~~ → **2 Alpha units** (SNR 0964 REV 1.2, SNR 097D REV 1.1) — enables parallel rev testing
2. **Charging untestable** — same MTIB source for DUT + CHG (29 tests deferred)
3. **Power resolution ~mA** — INA219 cannot measure µA sleep current
4. ~~**Fixture mapping TBD**~~ → **RESOLVED:** GPIO assignments in `alpha_b0.json`: SWD=0+1, button=2, on_skin=3, peltier=4, charger=5
5. ~~**CoreCloud URL TBD**~~ → **RESOLVED:** `dev.office.corekinect.cloud`
6. **18 Config Value tests deferred** — waiting on GroundModeConfigV2 endpoint (Jarred's branch)
7. **7 GNSS tests deferred** — scaffold is indoors, no GPS signal source
8. **No BLE** — deferred from this POC
9. ~~**Device personalization required**~~ → **RESOLVED:** Automated via DevicePersonalizer in conftest.py
10. ~~**Re-personalization required after every flash**~~ → **RESOLVED:** Automated in `firmware_build` fixture
11. ~~**Alpha mfg firmware build blocked**~~ → **RESOLVED:** `encryption_key.pem` auto-generated
12. **Release FW cannot be re-personalized** — no mfg shell. Strategy: personalize on debug, then flash release without re-personalization
13. **LED/photodiode not wired** — ADC reads 0V for LED color tests (4 test failures)
14. **Power budgets may be design targets** — idle 5mA budget vs 36mA operational (active modem draws significant current)

---

## Key References

| Document | What |
|----------|------|
| `plans/mtib-server-redesign.md` | MTIB server interface spec (23 RPCs, proto definition) |
| `architecture/stage3-integration-tests.md` | concord_harness design spec |
| `architecture/stage4-product-tests.md` | Stage 4 requirements |
| `libs/protocols/mtib_v2/DESIGN.md` | MTIB carrier board hardware reference |
| `project/bom-validation-pipeline.md` | Full BOM (this plan extracts Stage 3+4 subset) |
| [device-registry.md](device-registry.md) | Validation device info (SNR, Device ID, IMEI, keys) |
| [corecloud-integration.md](corecloud-integration.md) | CoreCloud API surface, DB schema, FUOTA tables, shell commands |
| `.claude/rules/repersonalization-workflow.md` | Standard re-personalization procedure |
| `.claude/rules/mtib-hardware.md` | MTIB hardware rules (power, UART, J-Link, revisions) |
| `apps/firmware/products/results.json` | Manufacturing batch data for validation devices |
| `apps/manufacturing/alpha/src/tests/post/step_9.py` | Reference: personalization code (CoreOps API calls) |

---

## Phase Documents

| Phase | Document | Streams | Status |
|-------|----------|---------|--------|
| 0 | [phases/phase-0-prerequisites.md](phases/phase-0-prerequisites.md) | — | Complete |
| 1 | [phases/phase-1-parallel-foundation.md](phases/phase-1-parallel-foundation.md) | A, B, C, D, G | Complete (C partial) |
| 2 | [phases/phase-2-harness-integration.md](phases/phase-2-harness-integration.md) | E, F | Complete |
| 3 | [phases/phase-3-stage3-proof.md](phases/phase-3-stage3-proof.md) | H | Deferred |
| 4-5 | [phases/phase-4-5-stage4-proof.md](phases/phase-4-5-stage4-proof.md) | J | **In progress** |
| 6 | [phases/phase-6-comparison.md](phases/phase-6-comparison.md) | — | Pending |
| 6B | [status.md § Phase 6B](status.md#phase-6b-concord-platform-integration-ui-live-results-artifacts) | — | Backend built, wiring pending |
