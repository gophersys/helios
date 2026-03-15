# Phase 6: Orchestration, Visibility & CI/CD

> **Status:** PROPOSAL — extends the Stage 4 plan without modifying Phases 0-5.
> **When:** After Phase 3 tests pass on hardware (Phases 0-5 prove the test logic works).
> **Dependencies:** Phase 2A framework functional, Phase 3 tests passing.
> **Does NOT modify:** Any existing test module, framework component, MTIB server code, or firmware build tooling.

---

## Problem Statement

Phases 0-5 build the test *execution* engine — pytest runs 37 tests on real hardware,
verifies CoreCloud messages, measures power budgets. But there's no answer to:

- **How does a run get triggered?** (manual SSH? Concord UI? Bitbucket pipeline?)
- **How do you see progress?** (tail pytest output over SSH? poll K8s job status?)
- **Where do results go?** (terminal output? JUnit XML on disk?)
- **How do you compare runs?** (manually open two terminals?)
- **How does the build server fit?** (firmware build → upload → trigger tests)

The Concord platform already has the scaffolding for all of this — it's just unwired:

| What Exists | Where | Status |
|-------------|-------|--------|
| `Session`, `TestExecution`, `TestResult`, `Log` models | `prisma/schema.prisma` L406-576 | **Schema complete, zero writers** |
| `SessionStatus`, `TestExecutionStatus`, `DeviceStatus` enums | `prisma/schema.prisma` L38-58 | Complete |
| Validation run endpoint (creates K8s Jobs) | `src/api/v2/validation/tests/run.py` | **Skips DB entirely** (L308 comment) |
| Socket.IO on `/kubernetes` namespace | `src/main.py`, `src/api/v2/system/logs.py` | **6 subscription patterns, production-ready** |
| `/tests`, `/results`, `/statistics` frontend routes | `src/routes/tests/`, etc. | **Placeholder stubs** ("Coming in a future tier") |
| `ResourceTable`, `StatusIndicator`, `MetricCard`, `ProgressRing`, `PodLogs` | `src/lib/components/` | **Complete building blocks** |
| `log_audit()` | `src/lib/audit.py` | Production, used everywhere |
| MinIO firmware storage | `src/services/storage/` | Production, `firmware-raw/` and `firmware-builds/` prefixes |
| K8s Job creation from YAML template | `src/api/v2/validation/tests/run.py` | Production |

This phase wires these existing pieces together and adds the missing connective tissue.

---

## Architecture Overview

```
                                  ┌─────────────────────────────┐
                                  │     Concord Frontend         │
                                  │  /validation/runs            │
                                  │  /validation/runs/[id]       │
                                  │  (live progress via WS)      │
                                  └──────────┬──────────────────┘
                                             │ REST + Socket.IO
                                  ┌──────────▼──────────────────┐
                                  │     Concord HTTP API         │
                                  │  POST /v2/validation/runs    │
                                  │  GET  /v2/validation/runs    │
                                  │  WS: subscribe_validation    │
                                  └──────────┬──────────────────┘
                                             │
                           ┌─────────────────┼─────────────────────┐
                           │                 │                     │
                    ┌──────▼──────┐  ┌───────▼───────┐   ┌────────▼───────┐
                    │   Prisma    │  │  K8s Job API  │   │    MinIO       │
                    │  Session    │  │  pytest pod   │   │  artifacts/    │
                    │  Execution  │  │  on val node  │   │  power traces  │
                    │  Result     │  │               │   │  UART logs     │
                    │  Log        │  └───────┬───────┘   └────────────────┘
                    └─────────────┘          │
                                    ┌───────▼───────┐
                                    │  pytest run   │
                                    │  (conftest    │
                                    │   reporter    │
                                    │   plugin)     │
                                    └───────┬───────┘
                                            │ REST callbacks
                                            │ to Concord API
                                    ┌───────▼───────┐
                                    │  MTIB + DUT   │
                                    │  CoreCloud    │
                                    └───────────────┘

Bitbucket (optional):
  PR merge → webhook → Concord API → build firmware → create run → K8s Job
  K8s Job completes → Concord API → Bitbucket PR status check
```

---

## Sub-Phases

### 6A: Backend — Validation Run API (~24h)

Wire the existing Prisma schema to actual API endpoints. Follow the existing
`src/api/v2/` module pattern (see `apps-backend-http-api.md` rules).

**New module:** `src/api/v2/validation/runs/`

| Endpoint | Method | What |
|----------|--------|------|
| `/v2/validation/runs` | POST | Create a Session + Device + Test definitions. Returns `run_id`. |
| `/v2/validation/runs` | GET | List runs with pagination, status filter, product filter. |
| `/v2/validation/runs/<id>` | GET | Run detail: session, device, all executions + results. |
| `/v2/validation/runs/<id>/cancel` | POST | Cancel a running session (sets status CANCELLED). |
| `/v2/validation/runs/<id>/executions` | GET | All test executions for this run. |
| `/v2/validation/runs/<id>/executions/<eid>/results` | GET | Step results for one execution. |
| `/v2/validation/runs/<id>/artifacts` | GET | List artifacts (UART logs, power traces) from MinIO. |
| `/v2/validation/runs/<id>/artifacts/<name>` | GET | Download specific artifact (presigned URL). |

**Internal callback endpoints** (called by the pytest reporter plugin running inside the K8s Job):

| Endpoint | Method | What |
|----------|--------|------|
| `/v2/validation/runs/<id>/report/start` | POST | pytest session started — set Session ACTIVE, record start time. |
| `/v2/validation/runs/<id>/report/test-start` | POST | Individual test started — create/update TestExecution to RUNNING. |
| `/v2/validation/runs/<id>/report/test-result` | POST | Individual test finished — create TestResult, update TestExecution to PASSED/FAILED. |
| `/v2/validation/runs/<id>/report/finish` | POST | pytest session finished — update Session counts, set COMPLETED. Upload artifacts. |

**How it maps to existing schema:**

| Schema Model | Role in Stage 4 |
|--------------|----------------|
| `Session` | One per validation run. `config` JSON holds firmware variant, MTIB node, DEVICE_ID. |
| `Device` | The Alpha B0 DUT. `serialNumber` = DEVICE_ID hex. One per session. |
| `Test` | Static definitions seeded once: "test_boot.test_power_cycle_produces_bootmsg", etc. `category` = module name. |
| `TestExecution` | One per test per firmware variant. `nodeId` = MTIB K8s node. Links Test + Device + Node. |
| `TestResult` | One per test assertion. `stepIndex` = 0 for single-assert tests. `result` JSON holds measurements, thresholds, actual values. |
| `Log` | pytest log output per execution. Linked via `executionId`. |

**Implementation notes:**
- The POST `/runs` endpoint replaces the current `run.py` approach (which skips the DB).
  The current `run.py` continues to work unchanged for manufacturing — this is a new path.
- Reporter callbacks use an API key (not user JWT) since they run inside K8s pods.
  Add a `CONCORD_REPORTER_API_KEY` env var to the job template.
- Socket.IO: add `subscribe_validation_run` / `unsubscribe_validation_run` events
  to the `/kubernetes` namespace. The report endpoints emit events after each DB write.

### 6B: pytest Reporter Plugin (~8h)

A pytest plugin that lives alongside the test framework and reports results back to
the Concord API in real-time. Zero changes to existing test modules — it hooks into
pytest's built-in hook system.

**File:** `libs/python/corekinect/test/validation/reporter.py`

```python
# Activated via conftest.py or pytest_plugins when CONCORD_RUN_ID is set.
# If CONCORD_RUN_ID is not set, the reporter does nothing (offline mode).

class ConcordReporter:
    """pytest plugin that reports results to Concord HTTP API."""

    def pytest_sessionstart(self, session):
        # POST /runs/<id>/report/start

    def pytest_runtest_logstart(self, nodeid, location):
        # POST /runs/<id>/report/test-start {test_name, module, variant}

    def pytest_runtest_makereport(self, item, call):
        # POST /runs/<id>/report/test-result {test_name, passed, duration, measurements}

    def pytest_sessionfinish(self, session, exitstatus):
        # POST /runs/<id>/report/finish {total, passed, failed, duration}
        # Upload artifacts (UART logs, power traces) to MinIO via Concord API
```

**Key design:**
- Reporter is opt-in: only activates when `CONCORD_RUN_ID` and `CONCORD_API_URL` env vars are set.
- When running pytest locally (SSH / dev), no reporter — pure terminal output. Zero behavior change.
- When running via Concord UI → K8s Job, the job template injects the env vars.
- Reporter extracts power measurements from `ctx.power` and attaches to TestResult JSON.
- UART logs are uploaded as artifacts to MinIO after session finishes.

### 6C: Frontend — Validation Pages (~32h)

Fill the placeholder routes (`/tests`, `/results`) and add a new `/validation/runs` section.
Uses existing building blocks — no new component primitives needed.

**Routes:**

| Route | What | Building Blocks |
|-------|------|----------------|
| `/validation/runs` | Run list: table of sessions with status, product, date, pass/fail counts. Poll at 5s. | `ResourceTable`, `StatusBadge`, `usePolling` |
| `/validation/runs/[id]` | Run detail: header with MetricCards (total/pass/fail/running), test execution table with live status updates, tabs for Results / Power / Logs / Artifacts. | `MetricCard`, `Tabs`, `StatusIndicator`, `ProgressRing`, Socket.IO `subscribe_validation_run` |
| `/validation/runs/[id]` — Results tab | Test-by-test pass/fail table. Expandable rows show TestResult JSON (measurements, thresholds, assertions). Group by module. Filter by variant (debug/release). | `ResourceTable`, `CollapsibleSection` |
| `/validation/runs/[id]` — Power tab | Power measurement charts per test. Canvas 2D line charts (follow `power-monitor-card.svelte` pattern). Compare debug vs release side-by-side. | Canvas chart (existing pattern from MTIB/ICLE) |
| `/validation/runs/[id]` — Logs tab | UART log viewer for debug builds. Scrollable, searchable, downloadable. | `PodLogsInline` pattern |
| `/validation/runs/[id]` — Artifacts tab | List of downloadable artifacts (UART dumps, power CSVs, JUnit XML). | File list with presigned download URLs |
| `/validation/runs/new` | Create new run: select product, MTIB node, firmware variant, test filter. Submit → POST /runs. | `Modal` or page form, `Select`, `TextInput` |

**Live progress pattern:**
```
1. User creates run → POST /v2/validation/runs → run_id
2. Frontend subscribes: subscribe_validation_run(run_id)
3. K8s Job starts pytest → reporter calls /report/start
4. API writes Session ACTIVE → emits WS event {type: "session_started"}
5. Each test starts → reporter calls /report/test-start
6. API writes TestExecution RUNNING → emits WS event {type: "test_started", name: "..."}
7. Each test finishes → reporter calls /report/test-result
8. API writes TestResult → emits WS event {type: "test_result", name: "...", passed: true/false}
9. Frontend updates table row in real-time (green check / red X)
10. pytest finishes → reporter calls /report/finish
11. API writes Session COMPLETED → emits WS event {type: "session_finished"}
12. Frontend shows final summary
```

This is identical in structure to the existing `subscribe_icle` pattern — just a different
event payload.

**Wire into existing layout:**
- Add "Validation" section to sidebar nav (between "Tests" and "Results")
- The existing `/tests` placeholder becomes the test definition management page
  (CRUD for Test model — which tests are enabled for which product)
- The existing `/results` placeholder becomes a redirect to `/validation/runs`
- `/statistics` placeholder becomes a dashboard with aggregate pass rates, trend charts

### 6D: Build Server & Firmware Pipeline (~16h)

Connect firmware builds to the validation flow. The build server produces hex files,
uploads them to Concord/MinIO, and optionally triggers a validation run.

**Build server requirements:**
- Docker (for `ctl.sh` firmware builds — needs `ncs-fw-dev:2.7.0` image)
- `kubectl` access to the K3s cluster (for triggering K8s Jobs)
- Network access to Concord API and MinIO

**Pipeline flow:**

```
Developer pushes to Bitbucket
        │
        ▼
Bitbucket Pipeline (or manual trigger)
        │
        ├── 1. Build firmware
        │     ctl.sh build-all alpha
        │     → 12 hex files in artifacts/
        │
        ├── 2. Upload to Concord
        │     POST /v2/catalog/<product>/firmware-builds/upload
        │     (existing endpoint — already supports hex upload + MinIO storage)
        │
        ├── 3. Upload to MTIB
        │     For each validation node:
        │       grpc UploadFwFile → /var/fw_files/<hex>
        │     (or: K8s Job that does this as an init container)
        │
        └── 4. Trigger validation run
              POST /v2/validation/runs
              {product: "alpha", firmware_build_id: "...", node: "10.4.45.33"}
              → K8s Job created → pytest runs → results stream back
```

**Bitbucket integration (two options):**

| Option | How | Complexity |
|--------|-----|------------|
| **A: Webhook (push model)** | Bitbucket sends POST to Concord API on PR merge. Concord triggers build + run. | New webhook endpoint + build orchestration in backend. Higher complexity. |
| **B: Pipeline-initiated (pull model)** | Bitbucket Pipeline runs `ctl.sh build-all`, then calls Concord API to upload + trigger. Pipeline polls for results. | New `bitbucket-pipelines.yml` + thin API script. Lower complexity. Recommended for Stage 4. |

**Recommendation: Option B** for Stage 4 proof.
- The pipeline script is a 50-line bash/Python script that calls existing Concord API endpoints.
- No webhook infrastructure needed.
- Results visible in both Concord UI and Bitbucket pipeline output.
- Status check back to Bitbucket PR via `bb` CLI or Bitbucket API from the pipeline.

**`bitbucket-pipelines.yml` sketch:**
```yaml
pipelines:
  custom:
    validate-alpha:
      - step:
          name: Build Firmware
          image: containers.ad.corekinect.com/ncs-fw-dev:2.7.0
          script:
            - cd apps/firmware/products && bash ctl.sh build-all alpha
          artifacts:
            - apps/firmware/products/alpha/artifacts/**

      - step:
          name: Upload & Trigger Validation
          image: python:3.10
          script:
            - pip install requests
            - python scripts/trigger-validation.py
              --product alpha
              --artifacts apps/firmware/products/alpha/artifacts/
              --concord-url $CONCORD_API_URL
              --api-key $CONCORD_API_KEY
              --mtib-node 10.4.45.33
          # This script:
          # 1. Uploads hex files via POST /v2/catalog/.../upload
          # 2. Creates a run via POST /v2/validation/runs
          # 3. Polls GET /v2/validation/runs/<id> until COMPLETED
          # 4. Exits 0 if all tests pass, 1 if any fail
```

### 6E: Comparison Dashboard (~8h)

Phase 4 of the original plan requires comparing debug vs release results.
This sub-phase adds a comparison view to the frontend.

**Route:** `/validation/runs/compare?a=<run_id>&b=<run_id>`

**Features:**
- Side-by-side test result table (debug column | release column)
- Color-coded: both pass (green), both fail (red), mismatch (yellow — critical finding)
- Power measurement overlay chart (debug trace vs release trace on same axes)
- Summary: "N tests match, M mismatches, K power budget differences"
- Export to PDF/CSV for the formal Phase 4 report

This replaces the manual comparison described in Phase 4 of the original plan.

---

## Effort Summary

| Sub-Phase | What | Effort | Dependencies |
|-----------|------|--------|-------------|
| 6A | Backend validation run API | 24h | Prisma schema (exists), existing API patterns |
| 6B | pytest reporter plugin | 8h | Phase 2A conftest (exists) |
| 6C | Frontend validation pages | 32h | 6A API, existing components |
| 6D | Build server + pipeline | 16h | 6A API, Docker registry access |
| 6E | Comparison dashboard | 8h | 6C pages, Phase 4 data |
| **Total** | | **88h** | |

---

## What This Does NOT Change

- **Phase 0-5 code is untouched.** All test modules, framework components, MTIB server
  updates, firmware build tooling, and conftest fixtures remain exactly as written.
- **Offline mode works.** Running `pytest tests/stage4/ -v` from a terminal with no
  `CONCORD_RUN_ID` set produces the same output as today. The reporter plugin is opt-in.
- **Manufacturing flow is untouched.** The existing `run.py` (K8s Job creation, no DB)
  continues to work. Phase 6A is a parallel path, not a replacement.
- **Existing frontend pages are untouched.** New routes are added alongside existing ones.
  The placeholder stubs (`/tests`, `/results`, `/statistics`) can be wired later or
  redirected — no breaking changes.

---

## Implementation Order

```
Phase 3 tests passing on hardware (prerequisite)
        │
        ▼
6A: Backend API (24h)
  │       │
  │       ▼
  │   6B: Reporter plugin (8h)   ← can start after 6A report endpoints exist
  │       │
  │       ▼
  │   6D: Build pipeline (16h)   ← can start after 6A create/status endpoints exist
  │
  ▼
6C: Frontend pages (32h)         ← can start after 6A list/detail endpoints exist
  │
  ▼
6E: Comparison dashboard (8h)    ← after 6C + Phase 4 data available
```

6A is the critical path. 6B and 6D can start as soon as the report endpoints are up.
6C can start as soon as the list/detail endpoints are up. 6E comes last.

---

## Key Design Decisions (Proposed)

| Decision | Rationale |
|----------|-----------|
| Pipeline-initiated CI (Option B) over webhooks | Lower complexity for Stage 4 proof. Webhooks can be added later. |
| Reporter plugin opt-in via env var | Zero impact on existing pytest flow. Local dev stays simple. |
| Reuse existing Socket.IO namespace (`/kubernetes`) | One authenticated connection per client. Add `subscribe_validation_run` event alongside existing 6 patterns. |
| Write to existing Prisma schema (Session/TestExecution/TestResult) | Schema is already designed for this. Zero migrations needed — just start writing rows. |
| MinIO for artifacts (UART logs, power CSVs) | Existing `StoragePrefixes` pattern. Add `VALIDATION_ARTIFACTS = "validation-artifacts/"`. |
| API key auth for reporter callbacks | K8s Jobs don't have user JWTs. Single shared key in job template env. |
| Comparison as a page, not a separate tool | Keeps everything in the Concord UI. Users don't need to context-switch. |
