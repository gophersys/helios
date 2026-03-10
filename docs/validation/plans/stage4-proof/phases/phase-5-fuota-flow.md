# Phase 5: FUOTA Validation Flow

> **Status:** Designed, blockers resolved. Ready for implementation.
> **Previously blocked by:** `.cfw` upload endpoint, FUOTA plan CRUD API
> **Blockers resolved:** 2026-03-06 — Jared confirmed REST API endpoints exist (see below)
> **When:** After Phase 4 completes
> **Effort:** ~40-60h (estimated)

---

## Purpose

This phase extends the Stage 4 proof from "does the production firmware
meet spec?" to "does the firmware update lifecycle work end-to-end?" It
validates every firmware transition path on real hardware using real
CoreCloud FUOTA infrastructure.

**This is documented here so nothing is discounted.** Phases 0-4 prove the
product tests work. Phase 5 proves the firmware delivery mechanism works.
Both are part of Stage 4 — they are sequenced, not competing.

---

## Blocker Resolution (2026-03-06)

Both infrastructure blockers have been resolved. Jared confirmed the CoreCloud
REST API endpoints for FUOTA management:

1. **CFW upload endpoint** — `POST /singleton/firmwareimages`
   - Multipart/form-data with field `image` containing the `.cfw` file
   - Base URL: `https://val.office.corekinect.cloud:2018` (no `/api` prefix)

2. **FUOTA plan CRUD API** — `POST /singleton/firmwareupdates/plans`
   - JSON body with `stages`, `description`, `deviceTypeId`, `deviceVariantId`
   - Each stage has `targets` array of CFW version strings (e.g., `["108.0.8.0-P", "109.0.8.0-P"]`)

3. **Device assignment** — `POST /singleton/firmwareupdates/settings/devices`
   - JSON body with `planId`, `enableFuota`, `maxStage`, `deviceIds`

4. **Progress monitoring** — `GET /singleton/firmwareupdates/progress?deviceId=<DevEUI>`

**Note:** These endpoints use the `/singleton/` path prefix, NOT `/api/`. The
`CoreCloudRestInterface` needs extension to support multipart file uploads
(currently only supports `json=` parameter).

---

## The 12-Step FUOTA Validation Flow

> Full specification: `architecture/stage4-fuota-validation-flow.md`

For each new firmware build, this sequence executes on each validation DUT:

```
Step 1:  Electrical Test
Step 2:  Flash Manufacturing FW (J-Link)
Step 3:  POST + Personalization
Step 4:  FUOTA Mfg → Mfg (same version sanity check)
Step 5:  Re-run POST (verify FUOTA didn't break hardware)
Step 6:  FUOTA Mfg → Production Debug          ← Factory transition
Step 7:  Run Stage 4 Validation Tests (Debug)   ← Phase 3 tests
Step 8:  FUOTA Prod Debug → Prod Debug (same version)
Step 9:  FUOTA Prod Debug → Production Release  ← Shipping binary
Step 10: Run Stage 4 Validation Tests (Release) ← Phase 3 tests
Step 11: Flash Previous Production Release (J-Link)
Step 12: Upgrade Path Test (prev → new)         ← Field upgrade
```

**Steps 7 and 10 reuse the exact test modules from Phase 2.** The FUOTA
flow wraps them with firmware transition orchestration.

### FUOTA Plans Required

| Plan | Step | From | To | Purpose |
|------|------|------|-----|---------|
| **A** | 4 | Mfg v1.0.0-PM | Mfg v1.0.0-PM | FUOTA mechanism sanity |
| **B** | 6 | Mfg v1.0.0-PM | Prod Debug v1.0.0-PD | Factory transition |
| **C** | 8 | Prod Debug v1.0.0-PD | Prod Debug v1.0.0-PD | Prod FUOTA client works |
| **D** | 9 | Prod Debug v1.0.0-PD | Prod Release v1.0.0-P | Debug → release |
| **E** | 12a | Prev Prod vA.B.C-P | New Debug vX.Y.Z-PD | Field upgrade path |
| **F** | 12b | New Debug v1.0.0-PD | New Release v1.0.0-P | Final upgrade |

### What Each FUOTA Step Verifies

| Step | Verification | Method |
|------|-------------|--------|
| 4 | FUOTA mechanism itself | BootMsgV2 with boot_reason=2 (FUOTA complete) |
| 5 | No hardware regression | Re-run POST (electrical + sensor tests) |
| 6 | Factory transition works | Device reconnects with production debug FW version |
| 7 | Debug build meets spec | Phase 2 test suite (64 tests) |
| 8 | FUOTA works on prod FW | BootMsgV2 with boot_reason=2 |
| 9 | Release delivery works | Device reconnects with release FW version |
| 10 | Shipping binary meets spec | Phase 2 test suite (64 tests) |
| 12 | Field upgrade path works | Device upgrades from previous release to new |

---

## Infrastructure Needed (Beyond Phase 2)

| Component | What | Effort |
|-----------|------|--------|
| **FuotaClient** | Create/monitor FUOTA plans via API (REST or DB ORM) | 12h |
| **CfwUploader** | Upload `.cfw` packages to CoreCloud | 4h |
| **FuotaOrchestrator** | Step sequencer for the 12-step flow | 16h |
| **Manufacturing shell integration** | Lock shell, run POST (reuse manufacturing patterns) | 8h |

**Estimated total:** 40h framework + variable test/debug time

### FuotaClient Interface

```python
class FuotaClient:
    """FUOTA plan management for Stage 4 validation.

    Creates FUOTA plans, monitors progress, and verifies completion
    via CoreCloud REST API (/singleton/ endpoints).

    Base URL: https://val.office.corekinect.cloud:2018
    Auth: Same Bearer token + X-API-KEY as /api/ endpoints.
    """

    def upload_cfw(self, cfw_path: str) -> None:
        """Upload .cfw firmware package.

        POST /singleton/firmwareimages (multipart/form-data, field: image)
        Server parses CFW v2 header to extract version metadata.
        """

    def create_plan(
        self,
        stages: list[dict],
        description: str,
        device_type_id: int = 2,
        device_variant_id: int = 3,
    ) -> int:
        """Create FUOTA plan. Returns planId.

        POST /singleton/firmwareupdates/plans
        Each stage: {"targets": ["108.x.y.z-P", "109.x.y.z-P"], "description": "...", "isSkippable": bool}
        """

    def assign_device(
        self,
        plan_id: int,
        device_ids: list[str],
        max_stage: int,
        enable: bool = True,
    ) -> None:
        """Assign device(s) to FUOTA plan.

        POST /singleton/firmwareupdates/settings/devices
        DANGER: Only pass test DUT device IDs. Never production devices.
        """

    def get_progress(self, device_id: str) -> dict:
        """Poll FUOTA progress.

        GET /singleton/firmwareupdates/progress?deviceId=<DevEUI>
        """

    def wait_for_completion(
        self, device_id: str, timeout_s: float = 3600
    ) -> dict:
        """Poll progress until stage advancement or timeout.

        FUOTA depends on device uplink cycle (15-60 min for LTE-M PSM).
        Default timeout is 1 hour.
        """
```

### FuotaOrchestrator Interface

```python
class FuotaOrchestrator:
    """12-step FUOTA validation flow sequencer.

    Executes each step in order, with checkpoints and failure handling.
    Steps 7 and 10 delegate to the Phase 2 pytest test suite.
    """

    async def execute(self, config: FuotaFlowConfig) -> FuotaFlowResult:
        """Run the full 12-step flow. Returns per-step results."""

    async def execute_commit_subset(self, config: FuotaFlowConfig) -> FuotaFlowResult:
        """Run commit-level subset: steps 2, 3, 6, 7, 9, 10 only.
        Skips same-version FUOTA (4, 8) and upgrade path (11, 12)."""
```

---

## Commit-Run Optimization

For per-commit validation, skip non-critical FUOTA steps:

| Step | Full Run | Commit Run | Why Skip |
|------|----------|------------|----------|
| 1 | Yes | Yes | Quick, always verify hardware |
| 2 | Yes | Yes | Must flash mfg FW |
| 3 | Yes | Yes | Must run POST |
| 4 | Yes | **Skip** | Same-version FUOTA is a mechanism test |
| 5 | Yes | **Skip** | POST after same-version is redundant |
| 6 | Yes | Yes | Critical: factory transition |
| 7 | Yes | Yes | Must run product tests (debug) |
| 8 | Yes | **Skip** | Same-version on prod FW is a mechanism test |
| 9 | Yes | Yes | Critical: release delivery |
| 10 | Yes | Yes | Must run product tests (release) |
| 11 | Yes | **Skip** | Upgrade path is weekly/release concern |
| 12 | Yes | **Skip** | Upgrade path is weekly/release concern |

**Commit run:** 8 steps (~2-3 hours)
**Full run:** 12 steps (~4-6 hours)

---

## Re-personalization in the FUOTA Flow

**Critical rule:** Steps 2 (J-Link flash) and 11 (J-Link flash) require
re-personalization because chip erase wipes the personalization space.
FUOTA transitions (steps 4, 6, 8, 9, 12) do NOT require re-personalization
because FUOTA updates the app image without chip erase.

| Step | Flash Method | Re-personalization? |
|------|-------------|-------------------|
| 2 | J-Link (chip erase) | **YES** — full personalize cycle |
| 4 | FUOTA (OTA update) | No |
| 6 | FUOTA (OTA update) | No |
| 8 | FUOTA (OTA update) | No |
| 9 | FUOTA (OTA update) | No |
| 11 | J-Link (chip erase) | **YES** — full personalize cycle |
| 12 | FUOTA (OTA update) | No |

After J-Link flash + re-personalization, the EC public key changes. CoreCloud
must be updated with the new key for subsequent FUOTA plans to authenticate.

See `.claude/rules/repersonalization-workflow.md` for the full sequence.

---

## Validation Devices

| Device | SNR | Device ID | MTIB Node |
|--------|-----|-----------|-----------|
| Alpha B0 REV 1.2 | 0964 | `70B3D584C01E1FCC` | 10.4.45.33 |
| Alpha B0 REV 1.1 | 097D | `70B3D584C01E20A2` | 10.4.45.32 |

CoreCloud server: `dev.office.corekinect.cloud`

---

## Open Decisions

| Decision | Options | Status |
|----------|---------|--------|
| FUOTA API access method | REST API (`/singleton/` endpoints) | **Resolved** — REST API confirmed |
| `.cfw` upload mechanism | `POST /singleton/firmwareimages` | **Resolved** — multipart upload |
| Test device lifecycle | Persistent DUTs (reuse) vs fresh per-run | Persistent (reuse) |
| Multi-plan consolidation | 6 separate plans vs fewer combined plans | Evaluate after stabilization |
| `/singleton/` auth | Same Bearer+APIKey as `/api/`? | **Needs verification** |
| CoreCloudRestInterface extension | Add `files=`/`data=` to `request()` | **Needs implementation** |

---

## Phase 5 Checkpoint

| Check | Status |
|-------|--------|
| `.cfw` upload endpoint available | Confirmed (2026-03-06) |
| FUOTA plan CRUD API available | Confirmed (2026-03-06) |
| `/singleton/` auth verified (read-only probe) | |
| CoreCloudRestInterface extended for multipart | |
| FuotaClient implemented | |
| FuotaOrchestrator implemented | |
| CFW files uploaded to VAL server | |
| FUOTA plan created for test device | |
| Device assigned to plan | |
| FUOTA progress monitored | |
| All FUOTA transitions verified (boot_reason="Fuota") | |
| Phase 3 tests pass after each FUOTA transition | |
| Commit-run subset verified | |
