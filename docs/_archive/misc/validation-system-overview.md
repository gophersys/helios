# Validation System Architecture

Complete architecture for the Concord validation system: test definitions, execution, reporting, and UI.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              VALIDATION SYSTEM                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐           │
│  │   Test Catalog   │    │   Test Runner    │    │    Reporter      │           │
│  │  (catalog.yaml)  │───▶│   (pytest)       │───▶│   (plugin)       │           │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘           │
│          │                       │                        │                      │
│          ▼                       ▼                        ▼                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐           │
│  │   HTTP API       │    │   K8s Job        │    │   WebSocket      │           │
│  │  /v2/validation  │◀───│   (execution)    │───▶│   (live events)  │           │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘           │
│          │                                                │                      │
│          ▼                                                ▼                      │
│  ┌──────────────────┐                          ┌──────────────────┐             │
│  │   PostgreSQL     │                          │   Frontend       │             │
│  │   (Prisma ORM)   │◀─────────────────────────│   (SvelteKit)    │             │
│  └──────────────────┘                          └──────────────────┘             │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Test Catalog (`catalog.yaml`)

Machine-readable test definitions that drive everything:

```yaml
# apps/validation/alpha/catalog.yaml
version: "1.0.0"
product: alpha
board: alpha_b0

stages:
  gate:
    name: "Gate"
    description: "PR merge blocker (<15 min)"
    timing_budget_s: 900
    trigger: "pr"
    blocks_merge: true

  nightly:
    name: "Nightly"
    description: "Comprehensive validation (30-60 min)"
    timing_budget_s: 3600
    trigger: "cron"
    cron: "0 2 * * *"

  integration:
    name: "Integration"
    description: "Instrumented firmware (15-30 min)"
    timing_budget_s: 1800
    trigger: "manual"
    requires_harness: true

tests:
  - id: "GATE-ALPHA-001"
    name: "test_01_download_artifacts"
    stage: gate
    timeout_s: 60
    description: "Download firmware artifacts from pipeline"

  - id: "GATE-ALPHA-002"
    name: "test_02_flash_firmware"
    stage: gate
    timeout_s: 150
    description: "Flash all 3 targets via J-Link"
    hardware:
      - jlink
      - mtib
```

### 2. Test Runner (pytest)

Tests execute via pytest with the Concord reporter plugin:

```
apps/validation/alpha/
├── catalog.yaml          # Test definitions (source of truth)
├── conftest.py           # Root fixtures (ctx, mtib, cloud_client)
├── pytest.ini            # pytest config
└── tests/
    ├── common/           # Shared code
    │   ├── timing.py     # Timing constants
    │   └── assertions.py # Common assertions
    ├── gate/             # Stage 5: PR validation
    │   ├── conftest.py   # Gate fixtures
    │   └── test_gate.py  # Gate tests
    ├── nightly/          # Stage 4: Comprehensive
    │   ├── test_power.py
    │   ├── test_sensors.py
    │   └── ...
    └── integration/      # Stage 3: Instrumented
        └── test_harness.py
```

### 3. Execution Environment

Tests run in K8s Jobs with full hardware access:

```yaml
# Execution context passed to K8s Job
env:
  CONCORD_RUN_ID: "clxyz..."        # ValidationRun ID
  CONCORD_API_URL: "https://..."    # Reporter callback URL
  CONCORD_API_KEY: "ck_run_..."     # Auth for callbacks

  # Hardware access
  MTIB_ADDRESS: "10.4.45.33"
  DEVICE_SNR: "0964"
  FIXTURE_PROFILE_PATH: "/profiles/alpha_b0.json"

  # Firmware from CI pipeline
  PIPELINE_ID: "clxyz..."
  FIRMWARE_BUCKET_FILE_PATH: "..."

  # CoreCloud for FUOTA
  VAL_1_0_API_KEY: "..."
  VAL_1_0_REST_SERVER_HOST_NAME: "val.office.corekinect.cloud"
```

### 4. Reporter Plugin

The reporter sends real-time updates to the API:

```python
# libs/python/corekinect/test/validation/reporter.py
class ConcordReporter:
    """Pytest plugin that reports to Concord API."""

    def pytest_sessionstart(self, session):
        # POST /v2/validation/runs/{id}/report/start

    def pytest_runtest_logstart(self, nodeid, location):
        # POST /v2/validation/runs/{id}/report/test-start

    def pytest_runtest_logreport(self, report):
        # POST /v2/validation/runs/{id}/report/test-result

    def pytest_sessionfinish(self, session):
        # POST /v2/validation/runs/{id}/report/finish
```

### 5. Database Schema

```prisma
// ValidationDesign - template defining the test flow
model ValidationDesign {
  id          String   @id
  name        String   // "Alpha B0 Gate"
  slug        String   @unique
  product     String   // "alpha"
  board       String   // "alpha_b0"
  version     String   // "1.0.0" - catalog version
  stages      Json     // Stage definitions from catalog
  tests       Json     // Test definitions from catalog
}

// ValidationRun - execution instance
model ValidationRun {
  id          String   @id
  designId    String
  design      ValidationDesign
  pipelineId  String?  // Links to CI pipeline
  status      ValidationRunStatus
  deviceId    String?  // DUT DevEUI
  nodeId      String?  // MTIB node

  // Progress
  stepsTotal  Int
  stepsPassed Int
  stepsFailed Int

  // Timing
  startedAt   DateTime?
  finishedAt  DateTime?
}

// ValidationStep - individual test execution
model ValidationStep {
  id          String   @id
  runId       String
  testId      String   // "GATE-ALPHA-001"
  testName    String   // "test_01_download_artifacts"
  stage       String   // "gate"
  status      ValidationStepStatus

  // Results
  durationMs  Int?
  logs        String?
  metrics     Json?    // Measurements, power data
  errorMessage String?
}
```

### 6. API Endpoints

```
# Catalog management
GET  /v2/validation/catalog/{product}           # Get test catalog
POST /v2/validation/catalog/{product}/sync      # Sync from catalog.yaml

# Run management
GET  /v2/validation/runs                        # List runs
POST /v2/validation/runs                        # Create run
GET  /v2/validation/runs/{id}                   # Get run details
POST /v2/validation/runs/{id}/trigger           # Start K8s job

# Reporter callbacks (internal)
POST /v2/validation/runs/{id}/report/start
POST /v2/validation/runs/{id}/report/test-start
POST /v2/validation/runs/{id}/report/test-result
POST /v2/validation/runs/{id}/report/finish

# WebSocket (real-time)
/validation namespace
  - join: { runId } → subscribe to run updates
  - validation_run_start
  - validation_test_start
  - validation_test_result
  - validation_run_finish
```

### 7. Frontend Views

```
/validation
├── /catalog                    # Browse test catalog
│   └── /{product}              # Product test definitions
├── /runs                       # Run history
│   ├── /[id]                   # Run detail (GitHub Actions style)
│   └── /compare                # Compare runs
├── /designs                    # ValidationDesign templates
└── /benches                    # Test bench management
```

## Versioning

### Test Suite Version

Each product's test suite has a semver version:

```yaml
# apps/validation/alpha/catalog.yaml
version: "1.2.0"  # MAJOR.MINOR.PATCH
```

- **MAJOR**: Breaking changes (test removed, ID changed)
- **MINOR**: New tests added
- **PATCH**: Test fixes, timing adjustments

### Version in Runs

Every run records which catalog version it used:

```json
{
  "id": "run_xyz",
  "catalogVersion": "1.2.0",
  "catalogCommit": "abc123f",
  "tests": [...]
}
```

### Version Comparison

Frontend can compare runs across versions:
- Same version: direct comparison
- Different versions: highlight added/removed tests

## Deployment

### Where Things Run

| Component | Location | Notes |
|-----------|----------|-------|
| Test definitions | Git repo | `apps/validation/{product}/` |
| K8s Job template | Git repo | `apps/backend/http-api/assets/templates/` |
| Test execution | K8s cluster | Pod with MTIB network access |
| API server | K8s cluster | `concord-http-api` deployment |
| Database | K8s cluster | PostgreSQL |
| Frontend | K8s cluster | `concord-ui` deployment |

### Execution Flow

```
1. PR merged / Cron trigger / Manual trigger
           │
           ▼
2. API creates ValidationRun (PENDING)
           │
           ▼
3. API creates K8s Job with:
   - Test image (contains pytest + tests)
   - Environment (MTIB, firmware, auth)
   - Resource limits
           │
           ▼
4. K8s schedules Job on node with MTIB access
           │
           ▼
5. Job runs pytest:
   - pytest tests/gate/ -v
   - Reporter sends updates to API
   - WebSocket broadcasts to UI
           │
           ▼
6. Job completes:
   - API marks run COMPLETED/FAILED
   - Artifacts uploaded to MinIO
   - Bench lock released
```

### Environments

| Environment | Trigger | MTIB Access | Purpose |
|-------------|---------|-------------|---------|
| Development | Manual | Local docker | Developer testing |
| Staging | PR/Manual | staging MTIB | Pre-prod validation |
| Production | Cron/Manual | prod MTIBs | Live hardware testing |

## Test Categories

### Gate Tests (Stage 5)
- **Timing**: < 15 minutes total
- **Trigger**: Every PR
- **Purpose**: Merge blocker
- **Scope**: Flash + boot + personalize + FUOTA

### Nightly Tests (Stage 4)
- **Timing**: 30-60 minutes
- **Trigger**: Cron (2 AM daily)
- **Purpose**: Comprehensive validation
- **Scope**: All sensors, power profiles, charger, GPS

### Integration Tests (Stage 3)
- **Timing**: 15-30 minutes
- **Trigger**: Manual / special firmware
- **Purpose**: Internal state verification
- **Scope**: State machine, IPC, harness commands

## Best Practices

### Test IDs
- Format: `{STAGE}-{PRODUCT}-{CATEGORY}-{NUMBER}`
- Examples: `GATE-ALPHA-001`, `NIGHTLY-ALPHA-PWR-003`

### Timing
- Every test has explicit timeout via `@pytest.mark.timeout()`
- Use `Timing.GATE.XXX` constants from `tests/common/timing.py`
- Stage total must not exceed budget

### Assertions
- Use helpers from `tests/common/assertions.py`
- Include measurements in results for trending

### Logging
- Use `corekinect.utils.Logger`
- Logs captured by reporter and stored with results

### Cleanup
- Use pytest fixtures with cleanup
- Register FUOTA cleanup handlers
- Release bench locks on finish (automatic)

## Migration from Legacy

### Before (stage4/)
```
tests/
└── stage4/
    ├── test_boot.py
    ├── test_power.py
    └── test_fuota.py
```

### After (gate/ + nightly/)
```
tests/
├── gate/
│   └── test_gate.py      # FUOTA + quick validation
└── nightly/
    ├── test_power.py     # Full power profiling
    ├── test_sensors.py   # All sensor tests
    └── test_boot.py      # Extended boot tests
```

### Migration Steps
1. Identify which tests belong to gate vs nightly
2. Move tests to appropriate directories
3. Update test IDs to new format
4. Add timeout markers
5. Remove legacy stage4/ directory
6. Update catalog.yaml
