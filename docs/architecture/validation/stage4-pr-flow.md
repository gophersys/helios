# Stage 4 PR Validation Flow — Complete Design

> The end-to-end firmware validation pipeline triggered when a PR is opened
> against `main` on `alpha_fw`. Proves that the firmware under test (FUT)
> works, can be delivered via FUOTA, survives every firmware transition path,
> and is compatible with the current production baseline.

---

## 1. Trigger

A pull request is opened against `main` that modifies `alpha_fw` (production
firmware). The validation pipeline runs automatically and blocks merge until
all phases pass.

---

## 2. Firmware Assets

Each validation run requires **8 firmware builds**, each producing 2 CFW files
(AppId 108 nRF9151 comms + AppId 109 nRF52840 app) = **16 CFW files** total.

### Naming Convention

| Label | Source | Version | Track | Purpose |
|-------|--------|---------|-------|---------|
| **MFG_BASE** | `alpha_mfg_fw` @ main | `{108,109}.0.5.{N}-PM` | Prod+Mfg | J-Link flash starting point |
| **MFG_BUMP** | Same code as MFG_BASE | `{108,109}.0.5.{N+1}-PM` | Prod+Mfg | FUOTA sanity target (same code, bumped build) |
| **FUT_DEBUG_A** | `alpha_fw` @ PR branch | `{108,109}.0.8.{M}-ED` | Eng+Debug | Firmware Under Test, debug variant, version A |
| **FUT_DEBUG_B** | Same code as FUT_DEBUG_A | `{108,109}.0.8.{M+1}-ED` | Eng+Debug | Same FUT debug, bumped build (proves FUOTA on debug prod) |
| **FUT_RELEASE_A** | `alpha_fw` @ PR branch | `{108,109}.0.8.{M}-P` | Production | Firmware Under Test, release variant, version A |
| **FUT_RELEASE_B** | Same code as FUT_RELEASE_A | `{108,109}.0.8.{M+1}-P` | Production | Same FUT release, bumped build (proves FUOTA on release prod) |
| **MAIN_BASELINE** | `alpha_fw` @ main | `{108,109}.0.8.{K}-P` | Production | Current production baseline |
| **MAIN_MERGED** | `alpha_fw` @ main + PR | `{108,109}.0.8.{K+1}-P` | Production | Simulated merge result |

### Version Numbering

- `Major.Minor` comes from `version.conf` (`CONFIG_APP_FW_MAJOR_VERSION`, `CONFIG_APP_FW_MINOR_VERSION`)
- `Build` comes from `VersionDevice.h` (`BUILD_NUM`)
- To produce "same code, different version", the build system patches `BUILD_NUM` before the second build
- Each build produces `zephyr.signed.encrypted.bin` which is wrapped into `.cfw` via `corekinect.firmware.cfw.generate_cfw_from_build()`

### Build Matrix

For each firmware label, the build system must:
1. Set `BUILD_NUM` in `src/VersionDevice.h` AND `comm_coproc_mfg/src/VersionDevice.h`
2. Set `IS_MANUFACTURING` (1 for mfg, 0 for production)
3. Set variant overlay (`--variant debug` or default release)
4. Build with `--mtib-rev 1.2`
5. Collect `zephyr.signed.encrypted.bin` from both MCU builds
6. Generate 2 CFW files (AppId 108 + 109)

---

## 3. The Flow

```
Phase 1: Hardware Baseline
  1.1  Electrical test (power rails, current draw)
  1.2  Flash MFG_BASE via J-Link (app + comms + modem)
  1.3  POST + Personalization (lock shells, assign device ID, generate keys)
  1.4  Register device with CoreCloud VAL

Phase 2: FUOTA Mechanism Sanity (Mfg → Mfg)
  2.1  Upload MFG_BASE + MFG_BUMP CFW files
  2.2  Create FUOTA plan (stage 0: MFG_BASE, stage 1: MFG_BUMP)
  2.3  Assign DUT, wait for FUOTA completion
  2.4  Verify device is on MFG_BUMP (boot_reason="Fuota", correct version)
  2.5  Run POST (prove FUOTA didn't break hardware)

Phase 3: Debug Production Validation
  3.1  Upload FUT_DEBUG_A + FUT_DEBUG_B CFW files
  3.2  Create FUOTA plan (stage 0: MFG_BUMP, stage 1: FUT_DEBUG_A)
  3.3  Assign DUT, wait for FUOTA completion
  3.4  Verify device is on FUT_DEBUG_A
  3.5  Run THOROUGH validation tests (full test suite on debug build)
  3.6  Create FUOTA plan (stage 0: FUT_DEBUG_A, stage 1: FUT_DEBUG_B)
  3.7  Assign DUT, wait for FUOTA completion
  3.8  Verify device is on FUT_DEBUG_B
  3.9  Run BASIC validation tests (sanity after same-code FUOTA)

Phase 4: Release Production Validation
  4.1  Upload FUT_RELEASE_A + FUT_RELEASE_B CFW files
  4.2  Create FUOTA plan (stage 0: FUT_DEBUG_B, stage 1: FUT_RELEASE_A)
  4.3  Assign DUT, wait for FUOTA completion
  4.4  Verify device is on FUT_RELEASE_A
  4.5  Run BASIC validation tests (release build black-box)
  4.6  Create FUOTA plan (stage 0: FUT_RELEASE_A, stage 1: FUT_RELEASE_B)
  4.7  Assign DUT, wait for FUOTA completion
  4.8  Verify device is on FUT_RELEASE_B
  4.9  Run BASIC validation tests (sanity after same-code FUOTA)

Phase 5: Upgrade Path (Main → Merge)
  5.1  Flash MAIN_BASELINE via J-Link (chip erase)
  5.2  Re-personalize (new EC key, register with CoreCloud)
  5.3  Run BASIC validation tests (confirm main baseline works)
  5.4  Upload MAIN_BASELINE + MAIN_MERGED CFW files
  5.5  Create FUOTA plan (stage 0: MAIN_BASELINE, stage 1: MAIN_MERGED)
  5.6  Assign DUT, wait for FUOTA completion
  5.7  Verify device is on MAIN_MERGED
  5.8  Run BASIC validation tests

VERDICT: All phases pass → PR approved for merge
```

---

## 4. What Each Phase Proves

| Phase | Question Answered | Failure Meaning |
|-------|-------------------|-----------------|
| 1 | Does the hardware work? | Dead board / solder defect |
| 2 | Does FUOTA mechanism work on mfg FW? | FUOTA client broken in mfg build |
| 3 (FUOTA in) | Can mfg FW transition to debug prod? | Cross-track FUOTA broken |
| 3 (thorough tests) | Does debug FUT meet spec? | Regression in PR code |
| 3 (same-ver FUOTA) | Does FUOTA work on debug prod FW? | FUOTA client broken in debug build |
| 4 (FUOTA in) | Can debug transition to release? | Release build linkage / config issue |
| 4 (basic tests) | Does release FUT work? | Release-only regression |
| 4 (same-ver FUOTA) | Does FUOTA work on release FW? | FUOTA client broken in release build |
| 5 (flash main) | Does current production work? | Baseline already broken (pre-existing) |
| 5 (FUOTA to merge) | Can deployed devices upgrade to PR? | Upgrade path broken |

---

## 5. FUOTA Transitions Summary

| # | From | To | FUOTA Plan Type |
|---|------|----|-----------------|
| 1 | MFG_BASE | MFG_BUMP | Mfg → Mfg (same code, version bump) |
| 2 | MFG_BUMP | FUT_DEBUG_A | Mfg → Debug Prod (cross-track) |
| 3 | FUT_DEBUG_A | FUT_DEBUG_B | Debug → Debug (same code, version bump) |
| 4 | FUT_DEBUG_B | FUT_RELEASE_A | Debug → Release (strip debug) |
| 5 | FUT_RELEASE_A | FUT_RELEASE_B | Release → Release (same code, version bump) |
| 6 | MAIN_BASELINE | MAIN_MERGED | Prod → Prod (field upgrade simulation) |

J-Link flash cycles: 2 (Phase 1.2, Phase 5.1)
Re-personalization cycles: 2 (Phase 1.3, Phase 5.2)

---

## 6. Test Suite Tiers

| Tier | When Used | Tests | Duration |
|------|-----------|-------|----------|
| **THOROUGH** | Phase 3.5 (debug build, first validation) | All Stage 4 tests: boot, power, button, motion, environmental, biometric, NFC, CoreCloud integration | ~15-30 min |
| **BASIC** | Phases 3.9, 4.5, 4.9, 5.3, 5.8 (sanity checks) | Boot test, power test, button test, CoreCloud connectivity | ~5 min |
| **POST** | Phases 1.3, 2.5 (hardware verification) | Accelerometer, altimeter, BLE, modem, LED, current draw | ~2 min |

---

## 7. Timing Estimate

| Activity | Count | Time Each | Total |
|----------|-------|-----------|-------|
| Firmware build | 8 | ~5-10 min | ~40-80 min |
| J-Link flash cycle | 2 | ~3 min | ~6 min |
| Personalization | 2 | ~2 min | ~4 min |
| FUOTA transition | 6 | ~15-60 min (depends on uplink interval) | ~90-360 min |
| Thorough test suite | 1 | ~15-30 min | ~15-30 min |
| Basic test suite | 5 | ~5 min | ~25 min |
| POST | 2 | ~2 min | ~4 min |

**Total estimated: ~3-8 hours** (dominated by FUOTA wait times)

### Optimization: Can We Speed Up FUOTA?

FUOTA requires a device uplink. Options:
1. **Power cycle** — forces immediate boot + uplink (~30s)
2. **Button press** — some FW versions trigger position report
3. **Reduce PSM timer** — shorter sleep = more frequent uplinks
4. **Wait** — default LTE-M PSM cycle (15-60 min)

If we can trigger immediate uplinks via power cycle after each FUOTA
assignment, transitions drop to ~5-10 min each (download + apply + reboot).

---

## 8. Abstraction Layers

### Repeating Patterns

These operations repeat across phases and must be clean, tested abstractions:

```python
class FirmwareBuildManager:
    """Builds firmware, patches version numbers, generates CFW files.

    Wraps: build.sh + VersionDevice.h patching + cfw.generate_cfw_from_build()
    """
    def build(self, source: str, build_num: int, variant: str,
              is_manufacturing: bool) -> BuildArtifacts: ...
    def generate_cfw(self, artifacts: BuildArtifacts,
                     release_track: int) -> CfwPair: ...

class FuotaClient:
    """FUOTA plan lifecycle via CoreCloud /singleton/ REST API.

    Wraps: upload CFW, create plan, assign device, poll progress.
    """
    def upload_cfw(self, cfw_path: str) -> None: ...
    def create_plan(self, stages: list, description: str) -> int: ...
    def assign_device(self, plan_id: int, device_id: str,
                      max_stage: int) -> None: ...
    def wait_for_completion(self, device_id: str,
                           timeout_s: float) -> FuotaProgress: ...
    def disable_device(self, device_id: str) -> None: ...

class DeviceFlasher:
    """J-Link flash + power cycle via MTIB.

    Wraps: upload hex, flash, power cycle, verify boot.
    """
    def flash(self, app_hex: str, comms_hex: str,
              modem_zip: str = None) -> None: ...
    def power_cycle(self) -> None: ...
    def verify_boot(self, expected_current_ma: float = 5.0) -> None: ...

class DevicePersonalizer:
    """Already exists. Wraps CoreOps + shell lock + key upload."""

class ValidationRunner:
    """Runs pytest test suites at different tiers.

    Wraps: pytest invocation with marker selection.
    """
    def run_post(self) -> TestResult: ...
    def run_basic(self) -> TestResult: ...
    def run_thorough(self) -> TestResult: ...

class Stage4Orchestrator:
    """Top-level flow coordinator.

    Composes all above classes to execute the 5-phase flow.
    Implements checkpoint/resume for long-running validation.
    """
    def execute(self, pr_config: PrValidationConfig) -> ValidationVerdict: ...
```

### CfwPair

Each firmware build produces TWO CFW files. Always pass them as a pair:

```python
@dataclass
class CfwPair:
    """A matched pair of CFW files (one per MCU)."""
    comms: str   # AppId 108, nRF9151
    app: str     # AppId 109, nRF52840

    @property
    def version_string_comms(self) -> str: ...  # e.g., "108.0.8.0-ED"

    @property
    def version_string_app(self) -> str: ...    # e.g., "109.0.8.0-ED"

    @property
    def targets(self) -> list[str]:
        """Stage targets for FUOTA plan."""
        return [self.version_string_comms, self.version_string_app]
```

---

## 9. FUOTA Plan Strategy

### Option A: One Plan Per Transition (Recommended)

Create a separate 2-stage plan for each transition. Simpler, easier to debug,
clear ownership.

- Plan 1: [MFG_BASE → MFG_BUMP]
- Plan 2: [MFG_BUMP → FUT_DEBUG_A]
- Plan 3: [FUT_DEBUG_A → FUT_DEBUG_B]
- Plan 4: [FUT_DEBUG_B → FUT_RELEASE_A]
- Plan 5: [FUT_RELEASE_A → FUT_RELEASE_B]
- Plan 6: [MAIN_BASELINE → MAIN_MERGED]

After each transition completes, assign device to next plan.

### Option B: Multi-Stage Plans

Fewer plans but more complex. Stage advancement controlled by `maxStage`.
Risk: harder to insert test runs between stages.

**Recommendation: Option A.** Clarity > cleverness.

---

## 10. Safety Invariants

1. **Device ID is hardcoded** — `70B3D584C01E1FCC`. Never dynamically resolved.
2. **Plan names include run ID** — e.g., `"Stage4 PR#42 run-abc123 Phase2 MFG→MFG"`
3. **One device per plan** — never batch-assign multiple devices
4. **Cleanup on exit** — always POST `enableFuota: false` in finally block
5. **No plan reuse** — each run creates fresh plans
6. **Assert before assign** — verify device has no active FUOTA before assignment
7. **Version verify after FUOTA** — read UART `Running FW version X.Y.Z` to confirm

---


## 11. Open Questions — Status

### Answered

**Q1: Version bumping mechanism** — DECIDED
Firmware source files must remain untouched. The build system injects
`BUILD_NUM` at compile time via `-DBUILD_NUM=N` compiler flag, passed through
`build.sh --build-num N`. This requires `VersionDevice.h` to guard the
default with `#ifndef BUILD_NUM`. This is a one-time, non-breaking change to
the firmware submodule. The same mechanism will be used by the gRPC build
service. See Section 12 for design.

**Q6: FUOTA speed** — YES
Power cycle the DUT after assigning a FUOTA plan to force immediate uplink.
Cuts transition time from ~30 min to ~5 min.

**Q7: Build server integration** — PARALLEL TASK
A dual-interface (gRPC + HTTP) build service is designed at
`docs/architecture/build-service.md`. Architecture: library-first — all
business logic in `BuildEngine` class, wrapped by gRPC and HTTP transports.
Protocol under `libs/protocols/build/`, server under `apps/backend/build/`.
Triggered by Bitbucket webhooks. Stores artifacts in MinIO. Queryable by
both gRPC clients and REST API. Like a headless TeamCity.

**Q9: Test suite tiers** — RUN EVERYTHING
If the full test suite runs in 10-15 minutes, run it every time. No need for
basic/thorough tiers. Thoroughness and correctness are paramount. Only split
into tiers if tests exceed ~15 min total.

### Requires Testing to Verify

**Q2: IS_MANUFACTURING flag** — UNKNOWN
`IS_MANUFACTURING = 1` in both `alpha_fw` and `alpha_mfg_fw`. This may be
intentional (early dev) or a bug. **Must run tests to verify assumptions:**
- Build with `IS_MANUFACTURING = 0` for production firmware
- Verify FUOTA plan targeting still works
- Confirm CFW flag byte correctly distinguishes mfg from prod
- Document results to get real answers

**Q3: Cross-track FUOTA** — LIKELY BLOCKED, MUST TEST

Confluence research (2026-03-07) found the following rules in
`docs/validation/research/06-fuota-corecloud-v1.md` (lines 257-280):

1. **No general track switching.** "A device on the Production track cannot
   receive Engineering or Bench firmware via FUOTA."
2. **Exception: Mfg → Prod.** "Manufacturing firmware (M flag) can be replaced
   by production firmware of the same or higher version."
3. **No debug on production tracks.** "Debug builds are only valid on Bench
   and Engineering tracks."

**Impact on Transition 2 (MFG_BUMP → FUT_DEBUG_A):** This transition goes
from `-PM` (Production+Mfg) to `-ED` (Engineering+Debug). Per rule #1, this
*should* be blocked by the server. But rule #2 allows Mfg→Prod, and the
debug flag may be orthogonal to track.

**Must test empirically:**
- Create a plan with `-PM` → `-ED` stage transition
- If server rejects: redesign flow to use `-PM` → `-P` first, then `-P` → `-ED`
- If server allows: document that cross-track is permissive in practice
- The alternative flow (if blocked) would insert an extra stage:
  `MFG_BUMP (-PM)` → `FUT_RELEASE_A (-P)` → `FUT_DEBUG_A (-ED)`

**Q4: Socket immediately closed** — NEEDS INVESTIGATION
Device on mfg v0.5.1 with default IPC keys. Socket connects then closes.
**Action plan:**
- Re-flash latest mfg firmware and re-personalize properly
- If socket still closes, extend POST tests with LTE debug diagnostics:
  - AT+CEREG? (registration status)
  - AT+COPS? (operator info)
  - AT+CGDCONT? (PDP context)
  - Socket server TLS handshake debug
- Verify Verizon network registration for this IMEI/ICCID
- Document findings regardless — this is foundational infrastructure

**Q5: Comms coprocessor versioning** — ANSWERED (Confluence research 2026-03-07)

Complete App ID mapping found in `docs/validation/plans/stage4-proof/corecloud-complete-reference.md`
(lines 224-243):

| App ID | Name | Chipset | MCU |
|--------|------|---------|-----|
| 108 | Comms | Alpha Bx | nRF9151 |
| 109 | Alpha | Alpha Bx | nRF52840 |
| 100/101 | Sigma5 Cx | nRF9160/nRF52840 |
| 102/103 | Alpha Ax | nRF9160/nRF52840 |
| 106/107 | Theta Cx | nRF9151/nRF52840 |

Key: App IDs change when firmware is incompatible (different bootloader).
Manufacturing firmware shares the same App ID as production firmware
(enables mfg→prod FUOTA). Comms (108) and app (109) are always paired
in FUOTA plans — both targets in every stage.

**Q6b: Modem firmware in FUOTA** — LIKELY NO
FUOTA updates app + comms only (MCUboot secondary slot). Modem firmware
(`mfw_nrf91x1_*.zip`) requires J-Link flash. Need to confirm.

### Future Design Decisions

**Q10: Checkpoint/resume** — DEFER
The full flow takes hours. Implement checkpoint/resume after the basic flow
works end-to-end. State: current phase, device FW version, completed steps.

**Q11: Multi-DUT parallelism** — DESIGN FOR IT
Use abstractions that accept device context (MTIB address, device ID, probe
serial) as parameters. Don't hardcode. But don't over-engineer the parallel
execution layer until we have 2+ MTIBs active.

---

## 12. Build Number Injection Design

### Problem

`BUILD_NUM` is defined as `#define BUILD_NUM 1` in `VersionDevice.h` inside
the firmware submodule. We need to inject different build numbers for "same
code, different version" builds WITHOUT modifying source files.

### Solution: Compiler Flag Override

**Step 1** (one-time firmware change): Guard the default in `VersionDevice.h`:
```c
#ifndef BUILD_NUM
#define BUILD_NUM 1
#endif
```

This is a non-breaking change — existing builds still default to `BUILD_NUM=1`.
Same pattern for `IS_MANUFACTURING`.

**Step 2**: Add `--build-num N` and `--is-mfg 0|1` to `build.sh`:
```bash
BUILD_NUM="${BUILD_NUM:-1}"
IS_MFG="${IS_MFG:-1}"
# ...
west build ... -- ... \
    -DCONFIG_COMPILER_OPT="-DBUILD_NUM=${BUILD_NUM} -DIS_MANUFACTURING=${IS_MFG}"
```

**Step 3**: The CFW generator reads the version from the built binary's
metadata (already embedded by the firmware at compile time), so no additional
plumbing needed.

### Why This Approach

- Firmware source untouched (except the one-time `#ifndef` guard)
- Works with the existing `west build` toolchain
- Same mechanism used by Docker build server (pass build number as env var)
- `build.sh` remains the single source of truth for how to build
- No Kconfig hacks or CMake cache pollution

---

## 13. LTE Debug Extension (If Socket Issues Persist)

If re-flash + re-personalize doesn't fix the socket issue, extend the POST
test suite with LTE diagnostics:

```python
class TestLteConnectivity:
    """LTE-M network registration and socket server connectivity."""

    def test_modem_firmware_version(self, ctx):
        """Verify modem firmware is expected version."""
        # Read UART for "FW version: mfw_nrf91x1_2.0.2"

    def test_sim_detection(self, ctx):
        """Verify SIM card detected and ICCID readable."""
        # Read UART for "IMEI,ICCID" line

    def test_network_registration(self, ctx):
        """Verify CEREG=1 (registered, home network)."""
        # Read UART for "+CEREG: 1" within 60s of boot

    def test_socket_connection(self, ctx):
        """Verify socket connects AND stays connected."""
        # Read UART for "Socket connected" and NO "Socket closed" within 10s

    def test_uplink_sent(self, ctx):
        """Verify at least one uplink message sent to CoreCloud."""
        # Poll /System/Devices/Status for boot recordId change
```

This is a side quest but worth it — it proves the network stack works before
attempting FUOTA (which requires successful uplinks).
