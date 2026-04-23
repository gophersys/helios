# FUOTA Constraints

**Last reviewed:** 2026-03-31
**Status:** Active

Reference constraints for building and delivering firmware via FUOTA (Firmware Update Over The Air) through CoreCloud.

## 1. D-Flag Constraint

CoreCloud silently strips the `D` (debug) flag from FUOTA plan targets. When a CFW is uploaded as `109.0.8.0-BMD`, the FUOTA plan stores the target as `109.0.8.0-BM` (D removed). The device then requests `109.0.8.0-BM`, but only the BMD image exists on the server, so **FUOTA delivery never starts**.

This is a confirmed CoreCloud behavior, not a bug that will be fixed soon. All FUOTA builds must avoid the D flag entirely.

**Rule:** CFWs with the D flag will never be FUOTA-delivered. Never set the D flag in CFW track flags for any build intended for FUOTA.

See: [Confluence - CK Firmware Versioning](https://corekinect.atlassian.net/wiki/spaces/EN/pages/2704080902)

## 2. Track Flags vs Binary Config

Two independent axes control firmware behavior:

### Binary variant (compile-time configuration)
- `debug` variant: `CONFIG_LOG=y` in Kconfig, UART boot logs visible
- `release` variant: `CONFIG_LOG=n` in Kconfig, no UART output

### CFW track flags (CoreCloud version matching)
- `B` = Bench, `E` = Engineering, `P` = Production
- `M` = Manufacturing
- `D` = Debug (MUST NOT be used -- see D-Flag Constraint above)

These axes are **independent**. A debug binary (CONFIG_LOG=y) can and should use a non-debug CFW track (e.g., `BM` instead of `BMD`). The track flags control how CoreCloud matches firmware versions during FUOTA delivery. The binary variant controls what the firmware actually does at runtime.

For Alpha validation, all FUOTA builds use the `BM` track regardless of whether the binary is debug or release. The `config_log` field in `StageBuildDef` captures the binary configuration independently of the track.

## 3. Verbose vs Quiet Naming Convention

The validation framework uses "verbose" and "quiet" to describe firmware behavior, not build variant names:

| Term | CONFIG_LOG | UART boot logs | Version detection | Verification method |
|------|-----------|---------------|-------------------|-------------------|
| **Verbose** | `y` | Yes, both processors emit version strings | UART BootVersionDetector | UART version match + cloud check-in |
| **Quiet** | `n` | No UART output at all | Not possible | Boot current measurement + cloud check-in only |

Both verbose and quiet builds use the `BM` track for Alpha. The D flag is never set.

The naming convention applies to build labels:
- `FUT_VERBOSE_A` / `FUT_VERBOSE_B` -- debug variant, CONFIG_LOG=y, UART visible
- `FUT_QUIET_A` / `FUT_QUIET_B` -- release variant, CONFIG_LOG=n, silent

## 4. CoreCloud FUOTA Rules

From the CK Firmware Versioning Confluence specification:

1. **Versions only increase** -- FUOTA will not deliver a firmware with a lower version number than what is currently running, except when transitioning from MFG firmware to non-MFG firmware (different fw_type).

2. **No release track switching** -- A device on track `B` cannot be FUOTA-updated to track `P` in a single plan. Track changes require a re-flash via J-Link.

3. **No production images with debug logging** -- The D flag is stripped (see constraint #1), so debug-flagged CFWs are effectively blocked from FUOTA delivery.

4. **All stages must have the same target count** -- A FUOTA plan with multiple stages must include the same number of firmware targets in each stage.

5. **All App IDs must be present in each stage** -- For a dual-processor device (e.g., Alpha with App IDs 108 and 109), every stage of the FUOTA plan must include both App IDs.

## 5. Alpha Build Matrix

All 8 FUOTA builds defined in `stage_defs.py` for the FUOTA validation stage:

| Label | fw_type | variant | config_log | Track | produces_hex | produces_cfw | Purpose |
|-------|---------|---------|-----------|-------|-------------|-------------|---------|
| `MFG_BASE` | mfg | mfg | yes | BM | yes | yes | J-Link flash base + MFG-to-MFG FUOTA source |
| `MFG_BUMP` | mfg | mfg | yes | BM | yes | yes | MFG-to-MFG FUOTA target (version-bumped) |
| `FUT_VERBOSE_A` | app | debug | yes | BM | yes | yes | Verbose FUOTA source, UART verification |
| `FUT_VERBOSE_B` | app | debug | yes | BM | yes | yes | Verbose FUOTA target (A->B), UART verification |
| `FUT_QUIET_A` | app | release | no | BM | yes | yes | Quiet FUOTA source, cloud-only verification |
| `FUT_QUIET_B` | app | release | no | BM | yes | yes | Quiet FUOTA target (A->B), cloud-only verification |
| `MAIN_BASELINE` | app | debug | yes | -- | yes | no | Mainline regression baseline (boot check only) |
| `MAIN_MERGED` | app | debug | yes | -- | yes | no | Post-merge build verification |

Version bump builds (`MFG_BUMP`, `FUT_VERBOSE_B`, `FUT_QUIET_B`) start in BLOCKED status and unblock when their base build completes. The build worker then bumps the build number to create a second version for the A->B transition test.

## 6. FUOTA Test Transition Matrix

| Test | Description | Flash label | FUOTA label(s) | Verification |
|------|-------------|-------------|----------------|-------------|
| `test_01` | MFG-to-MFG sanity check | `MFG_BASE` | `MFG_BUMP` | UART version + POST |
| `test_02` | MFG-to-Prod verbose | `MFG_BASE` | `FUT_VERBOSE_A` | UART version + cloud check-in |
| `test_03` | MFG-to-Prod quiet | `MFG_BASE` | `FUT_QUIET_A` | Boot current + cloud check-in |
| `test_04` | Prod-to-Prod verbose (2-phase) | `MFG_BASE` | `FUT_VERBOSE_A` then `FUT_VERBOSE_B` | UART version after each + cloud check-in |
| `test_05` | Prod-to-Prod quiet (2-phase) | `MFG_BASE` | `FUT_QUIET_A` then `FUT_QUIET_B` | Boot current after setup + cloud check-in after upgrade |

Tests 01-03 are single-phase: flash MFG, then FUOTA to target.

Tests 04-05 are two-phase: flash MFG, FUOTA to A variant (setup), then FUOTA from A to B variant (the actual test). This validates the real-world OTA upgrade path where a device already running production firmware receives a newer version.

All tests share the same setup steps: J-Link flash, boot verify, POST, personalize, cloud check-in. The differentiation is in what firmware is delivered via FUOTA and how success is verified.
