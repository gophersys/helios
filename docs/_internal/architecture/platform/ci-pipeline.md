# Validation CI Pipeline — Architecture

**Date:** 2026-03-07
**Status:** Design

## End-to-End Flow

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│ Git Push /   │───►│ Concord API  │───►│ K8s Job      │───►│ Real-time     │
│ Manual       │    │ creates run  │    │ runs tests   │    │ Dashboard     │
│ Trigger      │    │ + triggers   │    │ on MTIB      │    │ (WebSocket)   │
└─────────────┘    └──────────────┘    └──────┬───────┘    └───────────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │  Reporter callbacks  │
                                   │  POST /report/start  │
                                   │  POST /report/test-* │
                                   │  POST /report/finish │
                                   └─────────────────────┘
```

## 1. Trigger Sources

### 1A. Manual (Concord UI)

```
User clicks "Run Validation" → POST /v2/validation/runs (creates Session)
                              → POST /v2/validation/runs/<id>/trigger (creates K8s Job)
```

### 1B. Bitbucket Webhook (future)

```
git push to firmware branch → Bitbucket webhook → POST /v2/webhooks/bitbucket
                             → Build Service compiles firmware
                             → POST /v2/validation/runs (auto-creates Session)
                             → POST /v2/validation/runs/<id>/trigger
```

### 1C. Scheduled (future)

```
Cron schedule → K8s CronJob → POST /v2/validation/runs + trigger
Daily regression suites, scheduled FUOTA tests, etc.
```

## 2. Backend Pipeline (Existing)

### Session Model

```
Session (run)
  ├── Product (alpha, sigma, etc.)
  ├── Config (nodeId, firmwareVariant, apiKey, etc.)
  ├── Status: ACTIVE → COMPLETED | FAILED | CANCELLED
  │
  └── Device (DUT being tested)
       ├── serialNumber (e.g., "0964")
       ├── Status: PENDING → IN_PROGRESS → PASSED | FAILED
       │
       └── TestExecution[] (one per test function)
            ├── Test definition (name, category, enabled)
            ├── Status: QUEUED → RUNNING → PASSED | FAILED | CANCELLED
            │
            └── TestResult[] (one per test-result callback)
                 ├── passed: bool
                 ├── result: { measurements, errorMessage, durationS }
                 └── stepIndex, groupIndex
```

### API Endpoints (Existing)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/validation/runs` | POST | Create a new validation run |
| `/v2/validation/runs` | GET | List runs (paginated, filterable) |
| `/v2/validation/runs/<id>` | GET | Run detail with executions |
| `/v2/validation/runs/<id>/trigger` | POST | Create K8s Job for run |
| `/v2/validation/runs/<id>/cancel` | POST | Cancel running tests |
| `/v2/validation/runs/<id>/executions` | GET | List test executions |
| `/v2/validation/runs/<id>/report/start` | POST | Reporter: session started |
| `/v2/validation/runs/<id>/report/test-start` | POST | Reporter: test started |
| `/v2/validation/runs/<id>/report/test-result` | POST | Reporter: test result |
| `/v2/validation/runs/<id>/report/finish` | POST | Reporter: session done |

### K8s Job Template

```yaml
# deploy/validation/alpha/deployment.yaml (simplified)
apiVersion: batch/v1
kind: Job
metadata:
  name: val-alpha-<run_id>
spec:
  template:
    spec:
      nodeSelector:
        kubernetes.io/hostname: <mtib-host>  # Pin to specific MTIB
      containers:
      - name: validation
        image: concord-validation:latest
        env:
        - name: MTIB_HOST
          value: "localhost"  # MTIB server runs on same node
        - name: DEVICE_ID
          value: "<device_id>"
        - name: CONCORD_RUN_ID
          value: "<run_id>"
        - name: CONCORD_API_URL
          value: "http://concord-api:9001"
        - name: CONCORD_API_KEY
          value: "<generated_api_key>"
        - name: FIXTURE_PROFILE_PATH
          value: "/app/fixtures/alpha_b0.json"
        command: ["pytest", "tests/stage4/", "-v", "--tb=short"]
```

## 3. Real-time Dashboard (To Build)

### WebSocket Events

Extend the existing `/kubernetes` Socket.IO namespace with validation events:

```
subscribe_validation_run { runId: "<id>" }
  → validation_test_start  { runId, testName, module, timestamp }
  → validation_test_result { runId, testName, passed, durationS, errorMessage, measurements }
  → validation_run_finish  { runId, total, passed, failed, errors, durationS }
```

### Implementation

The reporter POST endpoints already write to the DB. Add WebSocket emission
after each DB write:

```python
# In reporter.py, after db.testexecution.update():
socketio.emit("validation_test_result", {
    "runId": run_id,
    "testName": data.test_name,
    "passed": data.passed,
    "durationS": data.duration_s,
    "errorMessage": data.error_message,
}, namespace="/kubernetes")
```

### Frontend Components

```
ValidationRunPage
├── RunHeader (status badge, product, device, firmware variant)
├── TestTimeline (vertical list of tests, GitHub Actions style)
│   ├── TestRow (name, status icon, duration, expandable)
│   │   ├── green checkmark / red X / yellow spinner / gray pending
│   │   └── ErrorDetail (collapsible, shows assertion message)
│   └── ... (one per test)
├── RunSummary (pass/fail/skip counts, total duration)
├── ArtifactLinks (UART logs, power traces, CSV downloads)
└── PowerChart (real-time power trace if Joulescope connected)
```

## 4. Test Matrix Coverage

### Stub Tests (CI — runs on every PR, no hardware)

```
libs/python/corekinect/test/tests/test_test_logic.py
  98 tests, ~0.3s execution time

  Dimensions:
    profile:  battery × batteryless
    variant:  debug × release
    scenario: pass × fail_<reason>

  Categories:
    TestPowerMatrix        — 20 tests (budget assertions × profile × variant)
    TestTraceAnomalies     — 12 tests (per-sample anomaly detection)
    TestButtonStateMachine — 28 tests (state transitions × profile × variant)
    TestCloudSequencing    —  8 tests (message present/missing/wrong)
    TestEnvironmentalMatrix— 22 tests (sensor readings × rail failures)
    TestFixtureOrdering    —  5 tests (stimulus cleanup verification)
    TestRegressions        —  4 tests (known hardware bugs)
```

### Mock Tests (CI — runs on every PR, no hardware)

```
apps/validation/alpha/tests/stage4/ with MOCK_CLOUD=1
  96 tests, ~1s execution time
  Uses MockCloudClient + ScenarioEngine for cloud message simulation
```

### Hardware Tests (K8s — runs on trigger, requires MTIB)

```
apps/validation/alpha/tests/stage4/ in hardware mode
  96 tests, ~30-60min execution time
  Requires: MTIB, DUT, fixture wiring, CoreCloud connectivity
```

## 5. Pipeline Stages

```
Stage 1: Stub Tests (PR gate, 0.3s)
  └── pytest libs/python/.../tests/test_test_logic.py
  └── Verifies test logic correctness across full matrix
  └── MUST pass before merge

Stage 2: Mock Tests (PR gate, 1s)
  └── MOCK_CLOUD=1 pytest apps/validation/alpha/tests/stage4/
  └── Verifies test + harness integration
  └── MUST pass before merge

Stage 3: Hardware Validation (post-merge or manual trigger)
  └── Triggered by firmware build or manual
  └── K8s Job on MTIB node
  └── Real-time results via WebSocket
  └── Artifacts uploaded to MinIO

Stage 4: FUOTA Regression (scheduled, future)
  └── Flash production firmware
  └── FUOTA to new version
  └── Verify OTA success via CoreCloud
```

## 6. What Needs To Be Built

### Already Done

- [x] Backend: Session/Device/TestExecution/TestResult CRUD
- [x] Backend: Reporter callback endpoints (start, test-start, test-result, finish)
- [x] Backend: K8s Job trigger endpoint
- [x] Backend: WebSocket infrastructure (Socket.IO on /kubernetes namespace)
- [x] Client: ConcordReporter pytest plugin
- [x] Client: Stub test infrastructure (stubs.py)
- [x] Client: 98-test verification matrix (test_test_logic.py)
- [x] Client: Mock mode with ScenarioEngine
- [x] Client: Fixture controller with physical stimulus model

### To Build

- [ ] Backend: WebSocket emission from reporter endpoints (broadcast test results)
- [ ] Backend: Log streaming (K8s pod logs → WebSocket → frontend)
- [ ] Backend: Bitbucket webhook handler for auto-trigger
- [ ] Frontend: ValidationRunPage with GitHub Actions-style test timeline
- [ ] Frontend: Real-time test status updates via WebSocket
- [ ] Frontend: Artifact viewer (UART logs, power traces)
- [ ] Client: PWM RPC for servo control (MTIB server + proto change)
- [ ] Client: HR LED pulsing background thread
- [ ] Client: Session capture (continuous UART + power recording)
- [ ] Infra: Docker image for validation runner
- [ ] Infra: CI config for stub + mock tests on PR
