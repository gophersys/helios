# E2E Project Memory

## Decisions

### D1: No Test Tiering (2026-04-08)
User explicitly rejected tiered testing (UI-only / full pipeline / hardware-in-loop tiers). Every test run exercises the full stack including real hardware. "Real stuff always, it's ok if it takes long."

### D2: Real Builds Always (2026-04-08)
Firmware builds use real compilation (5-20 min per target). No mocked or stubbed builds. Build caching is separately verified.

### D3: Fresh DB + Cumulative (2026-04-08)
Each suite run starts with a fresh database (migrate, NO seed). Tests are ordered and cumulative within a run — test A creates product, test B uses it.

### D4: 4 Full Role Stories (2026-04-08)
Each role (Admin, Maintainer, Developer, Operator) gets a complete end-to-end user story. Not just permission checks — full workflows per role.

### D5: Manufacturing = Validation Mirror (2026-04-08)
Manufacturing workflow is nearly identical to validation but with 1 stage and type=MANUFACTURING. Builds auto-cache from validation if same fingerprint exists.

### D6: Full Cleanup Required (2026-04-08)
Everything must be cleaned up: DB, CoreCloud, Bitbucket branches/PRs, MinIO artifacts. Only purposeful post-analysis artifacts are kept.

### D7: Dev MTIB Assignment (2026-04-08)
Dedicated dev pool MTIB: 10.4.45.33 (REV 1.2), DUT SNR 0964 (Alpha B0 without battery, ch0 only at 4.5V). This MTIB is exclusively for development/E2E — never used by validation or production.

### D8: Bitbucket Real Repos (2026-04-08)
Tests use real `alpha_fw` and `alpha_mfg_fw` repos. Must keep `concord-main` synced with `main` as part of test setup.

### D9: Excluded Features (2026-04-08)
Out of scope: ICLE device management, waveform analyzer, inventory (components/assemblies).

### D11: Manufacturing is a FULL BUILD, not just tests (2026-04-08)
Manufacturing module must be implemented from scratch: backend endpoints, frontend pages, setup wizard. It is NOT like validation (which auto-triggers from builds). Manufacturing is operator-driven: start session → scan QR → run panel → repeat → end session. Results grouped by session, per-unit pass/fail. 3 stages: Electrical → Flash → POST.

### D12: Manufacturing needs same wizard/setup flow as validation (2026-04-08)
Product detail page needs a Manufacturing tab with setup wizard, similar to validation stage config. Configure stages, firmware source, personalization, pass criteria.

### D13: MTIB deploy/undeploy must be fixed (2026-04-08)
Current MTIB auto-deploy works but auto-undeploy has TODOs. Must fix for both Docker (development) and K8s (staging/production).

### D14: Operator role must work for manufacturing (2026-04-08)
Operator can: start manufacturing sessions, view manufacturing fixtures, enter QR codes, run panels, view results. The manufacturing:run permission must gate actual endpoints.

### D10: MTIB Reachability Constraint (2026-04-08)
Dev machine (172.22.x.x codespace) can reach CoreCloud and Bitbucket but NOT the MTIB directly (10.4.45.33 unreachable). Tests requiring MTIB must run from office network or K8s pod. Other 10.4.45.x hosts (.31, .32) are reachable — .33 was offline during check.

## Review Findings (2026-04-08 — Post-Review Pass)

### Fixed CRITICAL Issues:
- **C1:** Kubernetes sidebar gated on `system:view`, not `kubernetes:view` — fixed permission note
- **C2:** View-As requires `window.location.reload()`, not reactive — fixed test expectations
- **C3:** Operator HAS `manufacturing:manage` — fixed permission matrix and removed wrong 403 test
- **C4:** Model count is 36, not 34 — fixed
- **C5:** No dedicated manufacturing endpoints — uses session endpoints — documented

### Fixed HIGH Issues:
- **H1:** Added missing pages: `/builds/settings`, build failure tests
- **H2:** View-As only in dev environment — documented
- **H3/H4:** Dev login uses `POST /v2/auth/dev-login` with `@concord.dev` emails — documented difference from existing `@concord.local` auth helper
- **H6:** Separated BuildJob vs BuildRun status enums

### Acknowledged MEDIUM Issues (to address during implementation):
- **M2:** WebSocket testing via DOM observation, not raw Socket.IO
- **M3-M6:** Cleanup expanded to include Secrets, PollCache, AuditLog (excluded)
- **M9:** Concurrent fixture access test deferred to implementation
- **M10:** Build failure path added to Stage 6

### D15: Sidebar toggle interaction required (2026-04-08)
Admin/System sections in sidebar are behind expandable toggle buttons. Tests must CLICK the toggle before checking if Users or Kubernetes items are visible. The spec originally omitted this step.

### D16: Developer HAS builds:manage (2026-04-08)
The permission matrix in SPEC.md section 4.2 was CORRECT — Developer has builds:manage. Confirmed in permissions.py line 107. Developer has full build pipeline control.

### D17: Maintainer CAN see Users sidebar link (2026-04-08)
Sidebar gates Users link on `users:view`, which Maintainer HAS. Maintainer sees the link but cannot perform manage operations (create/edit/delete require `users:manage`). SPEC section 4.3 was WRONG about this.

### D18: docker-compose.test.yaml needs config changes (2026-04-08)
Test compose has `BITBUCKET_POLLER_ENABLED=false` and `CK_BOARDS_REPO_URL=""`. Must configure these for E2E tests that need git-poller and product creation wizard. Test compose uses port 9010 (not 9001).

### D19: Stage config trigger type is "schedule" not "cron" (2026-04-08)
The actual UI uses "schedule" as the trigger type name, not "cron". Fixed in stage files.

### D20: Session reporter uses bare @require_auth (2026-04-08)
Reporter endpoints (`/report/test-result`, etc.) use `@require_auth` only — any valid API key holder can post results, no specific permission required. This is intentional (CI runner needs to report).

## Errors Encountered

(None yet — spec phase)

## Learnings

### L1: Existing E2E Infrastructure (2026-04-08)
Significant Playwright infrastructure already exists:
- `e2e/fixtures.ts` — Custom fixture with JS error collection
- `e2e/helpers/auth.ts` — Fast API login (~50ms) + UI login
- `e2e/helpers/api.ts` — Typed API helpers with CI admin key
- 60+ existing tests across 8 spec files
- `docker-compose.test.yaml` — Isolated test stack (ephemeral)

New E2E tests should extend these patterns, not reinvent them.

### L2: Dev Login Users Pre-Seeded (2026-04-08)
The seed script creates 4 dev users: admin@concord.dev, maintainer@concord.dev, developer@concord.dev, operator@concord.dev. BUT — our tests start from a fresh DB with NO seed. We'll need to either:
- Run seed as part of test setup (creates the dev users)
- OR create users via API during test setup
Decision: Run seed for platform data (roles, permissions, dev users) but NOT product data.

### L3: WebSocket Namespaces (2026-04-08)
Two Socket.IO namespaces:
- `/validation` — session events (test_start, test_result, run_finished)
- `/kubernetes` — observability, ICLE, pod logs, pod exec
Tests need WebSocket client helpers to subscribe and assert on events.

### L4: Build Matrix Complexity (2026-04-08)
Stage 5 (FUOTA) build matrix can have 7-8 jobs. Stage 1 (Smoke) may have only 1-2. E2E tests need to understand the matrix structure to verify correct job counts.
