# CI Testing Gap Analysis & Roadmap

**Last reviewed:** 2026-04-13
**Status:** Active

Honest assessment of what we test, what we don't, and what to build next.

---

## Current State

```
Test inventory: 4,133 test functions across 407 files
  Python backend:  2,604 functions (153 files)
  TypeScript frontend: 949 functions (16 files)
  Playwright E2E: 522 functions (54 files)
  WebSocket: 72 functions (6 files)

CI stages: 33 stages across 5 pipelines (pr, main, release, nightly, weekly)
AI review: 5 Claude-powered stages + auto-fix + architecture drift detection
```

---

## Level 1: Static Analysis — SOLID

| Check | Status | Stage | Notes |
|-------|--------|-------|-------|
| TypeScript type checking | Done | `typecheck` | svelte-check + tsc |
| Python type checking | Done | `typecheck-python` | mypy on build-service, git-poller |
| Linting | Done | `lint` | ESLint on affected projects |
| Security scanning | Done | `security` | bandit (Python), high-severity only |
| Dependency audit | Done | `dep-audit` | pip-audit for CVEs |
| Secret detection | Done | `secret-scan` | detect-secrets with baseline |
| Complexity gates | Done | `complexity` | Cyclomatic complexity thresholds |
| Schema validation | Done | `schema-check` | Prisma field name verification |
| Dependency pinning | Done | `dep-pin` | Warns on unpinned versions |
| API compatibility | Done | `api-compat` | Backward compat diffing (advisory) |
| Docstring coverage | Done | `docstrings` | interrogate (90% threshold) |
| Docs build | Done | `docs-build` | MkDocs validates links/pages |
| Container image scan | Done | `image-scan` | Trivy vulnerability check |
| Migration safety | Done | `migration-safety` | Prisma schema diff analysis |
| AI completeness | Done | `ai-review-completeness` | Schema propagation chain check |
| AI security | Done | `ai-review-security` | OWASP scan via Claude |
| AI docs staleness | Done | `ai-review-docs` | Code changed but docs didn't |
| AI blast radius | Done | `ai-review-blast-radius` | Cross-project impact report |
| AI architecture | Done | `ai-review-architecture` | God objects, coupling, circular deps |
| Proto sync | Done | `proto-sync` | Generated stubs match .proto files |
| Serializer check | Done | `serializer-check` | Serializer keys vs OpenAPI schema |
| Type generation | Done | `types-sync` | OpenAPI → TypeScript drift check |

**Verdict:** Comprehensive. No gaps worth filling here.

---

## Level 2: Unit Tests — GOOD, ONE GAP

| Service | Tests | Coverage Threshold | Assessment |
|---------|-------|-------------------|------------|
| http-api | 2,116 functions | 65% | **TOO LOW** — 35% of code is untested |
| build-service | 347 functions | 90% | Good |
| git-poller | 141 functions | 90% | Good |
| frontend | 949 functions | **none enforced** | **GAP** — could regress to 0% silently |

### What to do

- [ ] **Raise http-api coverage to 75%** — incremental, not overnight. The service has 2,116 tests already; the gap is in newer endpoints (assets, API keys, auth) that were added without full coverage.
- [ ] **Add frontend coverage threshold at 50%** — start low, raise quarterly. Currently no enforcement at all.
- [ ] **Expand mutation testing** — currently only tests `build_trigger.py`. Add 4-5 more high-risk modules: `build_run_service.py`, `queue_scheduler.py`, `auth/jwt.py`, `storage/client.py`. Run nightly, keep advisory.

**Effort:** Small. Config changes + a few dozen new test functions.
**Value:** Medium. Catches regressions in under-tested code.

---

## Level 3: Integration Tests — THE REAL GAP

**Current state: 5 test files, 44 test functions for the entire platform.**

This is the biggest gap. Unit tests mock the database. Integration tests use a real DB + real MinIO + real services. The 5 existing tests cover:
- Auth flow (login, token, permissions)
- Build lifecycle (create, list, status)
- Product management (create, update, board revisions)
- Recipe workflow (create, execute)
- Database seed verification

### What's missing (high value, achievable)

- [ ] **MinIO storage round-trip** — Upload a firmware artifact, download it, verify bytes match. Catches: storage config issues, presigned URL bugs, CORS problems.
  ```
  Effort: 1 test file, ~30 lines
  Where: tests/integration/test_storage.py
  What it catches: S3 config drift, broken presigned URLs, CORS issues
  ```

- [ ] **Build-service task execution** — Submit a build job via the API, wait for build-service to pick it up, verify the artifact appears in MinIO.
  ```
  Effort: 1 test file, ~80 lines (needs build-service running in compose)
  Where: tests/integration/test_build_execution.py
  What it catches: Queue processing bugs, artifact upload failures, status tracking errors
  ```

- [ ] **Git-poller webhook trigger** — Simulate a Bitbucket webhook payload, verify git-poller creates a build run.
  ```
  Effort: 1 test file, ~50 lines
  Where: tests/integration/test_git_poller_trigger.py
  What it catches: Webhook parsing bugs, authentication issues, event deduplication failures
  ```

- [ ] **WebSocket event delivery** — Connect a socket.io client, trigger a build status change, verify the event arrives.
  ```
  Effort: 1 test file, ~60 lines
  Where: tests/integration/test_websocket_events.py
  What it catches: Broken real-time updates, missed events, connection handling bugs
  ```

- [ ] **Database migration round-trip** — Apply all migrations to a fresh DB, seed, verify the API serves correct data.
  ```
  Effort: Already partially covered by test_seed.py, extend it
  Where: tests/integration/test_migrations.py
  What it catches: Migration ordering bugs, data loss during schema changes
  ```

**Effort:** 5 test files, ~250 lines total. Medium effort.
**Value:** HIGH. These catch the bugs that actually break production — the service-to-service interactions that unit tests can't see.

---

## Level 4: Contract Tests — ADEQUATE WITH AI

| What | Status | Notes |
|------|--------|-------|
| API response shapes | 12 tests across 8 files | Catches serializer regressions |
| API backward compat | Advisory stage | Warns on removed endpoints |
| Schema propagation | AI review (completeness) | Catches missing type updates |
| Proto compat | proto-sync stage | Verifies generated stubs match |
| Frontend types | types-sync stage | Advisory drift detection |
| Serializer coverage | serializer-check | AST comparison vs OpenAPI |

### What's missing

- [ ] **Consumer-driven contracts (Pact)** — The frontend makes assumptions about API response shapes that aren't validated. Pact would formalize: "the frontend expects `GET /v2/products` to return `{data: [{id, name, slug, ...}]}`" and fail if the backend changes the shape.
  ```
  Effort: High (new tooling, new workflow)
  Value: Medium — AI completeness review already catches most of this
  Recommendation: SKIP for now. AI review is cheaper and catches more.
  ```

- [ ] **gRPC contract tests** — The MTIB proto interface between backend and edge devices should have contract tests verifying backward compatibility when protos change.
  ```
  Effort: Medium (need proto backward compat checker like buf)
  Value: Medium — proto-sync already catches stale stubs
  Recommendation: Add buf lint to proto-sync stage. 1 hour of work.
  ```

**Verdict:** AI review stages cover most of what Pact would catch. Add buf lint for proto compat and call it done.

---

## Level 5: E2E Tests — FRAMEWORK EXISTS, NEEDS GOLDEN PATH

**Current state: 54 Playwright files, 522 test functions covering major user workflows.**

The E2E suite is actually quite comprehensive. It covers auth, products, builds, validation, manufacturing, fixtures, users, and Bitbucket integration. But it's missing the ONE test that matters most:

### What's missing

- [ ] **Critical path workflow test** — One test that exercises the entire golden path:
  ```
  Login as admin
    → Create a product with a board revision
    → Configure a build stage
    → Trigger a build
    → Wait for build to complete
    → Verify artifact exists
    → Create a validation stage
    → Run validation
    → Check results
  ```
  This is the test that catches "the system works end-to-end as a user experiences it."
  ```
  Effort: 1 test file, ~150 lines
  Where: apps/frontend/app/e2e/stories/critical-path.spec.ts
  Value: VERY HIGH — this is the test you run before every release
  ```

- [ ] **Mobile viewport tests** — Currently Desktop Chrome only. Add tablet (768px) and mobile (375px) viewports.
  ```
  Effort: Small (add projects to playwright.config.ts)
  Value: Medium — depends on how many mobile users you have
  ```

- [ ] **Visual regression baseline** — One `pages.spec.ts` exists but covers very few pages. Expand to all major routes.
  ```
  Effort: Medium (screenshot every route, maintain baselines)
  Value: Medium — catches CSS regressions
  ```

- [ ] **Accessibility (a11y) tests** — Use `@axe-core/playwright` to check WCAG compliance.
  ```
  Effort: Small (add axe to existing tests)
  Value: Medium-high if you have compliance requirements
  ```

**Recommendation:** Build the critical path test first. It's the single highest-value E2E test you can write.

---

## Level 6: Performance & Resilience — NOT STARTED

Nothing exists here today. This is expected for the current stage of the product, but these become critical as you scale.

### What to build when ready

- [ ] **API response time baselines** — Add `--durations` to pytest, record p95 for key endpoints (list products, create build, get results). Fail if p95 exceeds 500ms.
  ```
  Effort: Small (pytest plugin + threshold check)
  Where: .ci/stages/performance.sh (new stage)
  Value: Catches slow queries before production
  When: When you notice production getting slower
  ```

- [ ] **WebSocket latency baseline** — Measure time from event emission to client receipt. Fail if p95 exceeds 200ms.
  ```
  Effort: Medium (need a test harness that measures timing)
  When: When real-time features become critical to users
  ```

- [ ] **Load testing** — Use k6 or locust to simulate concurrent users. Start with: 10 concurrent builds, 50 concurrent API requests, 100 concurrent WebSocket connections.
  ```
  Effort: Medium (new tooling, new test scripts)
  When: When you have >10 concurrent users
  ```

- [ ] **Chaos testing** — Kill a service mid-request. Verify the system recovers gracefully. Start with: kill http-api during a build, kill MinIO during an upload.
  ```
  Effort: High (need chaos injection framework)
  When: When uptime SLA matters
  ```

- [ ] **Database query performance** — Log slow queries (>100ms), fail if any new slow query appears in a PR.
  ```
  Effort: Small (Prisma logging + grep)
  When: When you notice DB-related slowdowns
  ```

**Recommendation:** Start with API response time baselines. It's the cheapest and catches the most common performance regression: someone adds a missing index or an N+1 query.

---

## Level 7: Production Observability — OUTSIDE CI

Not CI responsibility, but worth tracking what's needed:

- [ ] Error rate alerting (Sentry or similar)
- [ ] Response time monitoring (Grafana + Prometheus)
- [ ] Build queue depth alerts (when backlog > N)
- [ ] Deployment canary analysis (compare new vs old pod metrics)

---

## Priority Matrix

### Do Now (this week)

| Item | Effort | Value | Why now |
|------|--------|-------|---------|
| MinIO storage round-trip test | 30 lines | High | Your CI reports and build artifacts depend on MinIO. Zero tests for it. |
| API response time baselines | 50 lines | High | Catches slow queries before users complain. |
| Raise http-api coverage to 75% | Config change + tests | Medium | 35% untested code is a liability. |

### Do Next (this month)

| Item | Effort | Value | Why next |
|------|--------|-------|----------|
| Build-service task execution test | 80 lines | High | Validates the build pipeline end-to-end. |
| WebSocket event delivery test | 60 lines | High | Real-time updates are a core feature. |
| Critical path E2E test | 150 lines | Very High | The one test that proves the system works. |
| Frontend coverage threshold (50%) | Config change | Medium | Prevents silent regression. |
| Add buf lint to proto-sync | 10 lines | Medium | Proto backward compat at near-zero cost. |

### Do Later (next quarter)

| Item | Effort | Value | Why later |
|------|--------|-------|-----------|
| Expand mutation testing scope | Medium | Medium | Better test quality validation. |
| Mobile viewport E2E tests | Small | Medium | If mobile users are a priority. |
| Accessibility (a11y) tests | Small | Medium | If compliance matters. |
| Load testing framework (k6) | Medium | High | When scaling is a concern. |
| Visual regression expansion | Medium | Medium | When UI stability matters. |

### Don't Do Yet

| Item | Why not |
|------|---------|
| Consumer-driven contracts (Pact) | AI completeness review covers this cheaper. |
| Chaos testing | Premature until you have uptime SLAs. |
| Cross-browser E2E | Chrome-only is fine for an internal tool. |
| Full mutation testing suite | Hours of runtime for marginal benefit. |

---

## How to Add a New Test

### Integration test
```bash
# 1. Write the test
vim tests/integration/test_storage.py

# 2. Run locally (needs platform running)
nx start platform
pytest tests/integration/test_storage.py -v

# 3. It automatically runs in CI via test-integration stage
```

### E2E test
```bash
# 1. Write the test
vim apps/frontend/app/e2e/stories/critical-path.spec.ts

# 2. Run locally (needs platform + frontend running)
nx start platform && npx nx serve app
cd apps/frontend/app && npx playwright test e2e/stories/critical-path.spec.ts

# 3. It automatically runs in nightly via entrypoint.sh
```

### Performance baseline
```bash
# 1. Create the stage
vim .ci/stages/performance.sh

# 2. Add to nightly pipeline
# 3. Set thresholds based on first few runs
```

---

## Metrics to Track

| Metric | Current | Target | How to measure |
|--------|---------|--------|----------------|
| http-api coverage | 65% | 80% | `npx nx run http-api:coverage` |
| Frontend coverage | unknown | 50% | `npx nx run app:coverage` |
| Integration test count | 44 | 100+ | `pytest tests/integration/ --collect-only \| wc -l` |
| E2E test count | 522 | 600+ | Playwright test collector |
| Contract test count | 12 | 30+ | `pytest tests/contracts/ --collect-only` |
| Mutation score | 60% (1 file) | 70% (10 files) | `mutmut results` |
| CI pipeline duration (PR) | ~5 min | <7 min | `.ci/run pr` timing |
| AI review cost per PR | ~$0.30 | <$0.50 | Trend report |
