# Validation Architecture

> **Status:** Work-in-progress. Captures current validation test infrastructure and intended direction.

## Overview

Validation testing runs individual (depaneled) units through extended test suites to verify product behavior, reliability, and compliance. Unlike manufacturing -- which tests every unit on the production line in bulk -- validation tests a smaller number of units more thoroughly, often over longer durations.

Validation uses the same MTIB node hardware as manufacturing, but the fixture layout differs: individual units rather than multi-panel slots.

## How Validation Differs from Manufacturing

| Aspect | Manufacturing | Validation |
|--------|--------------|------------|
| **Purpose** | Production-line pass/fail | Design verification, compliance |
| **Volume** | Every unit produced | Sample units |
| **Duration** | Seconds to minutes per unit | Minutes to hours per test suite |
| **Fixture** | Multi-panel (4+ DUT slots) | Individual units |
| **Tests** | Electrical, FW flash, POST | Extended functional, stress, environmental |
| **Nodes** | Panel slots + stand-alone | Individual MTIB per DUT |

## Physical Layout

```
Validation Lab
|
+-- Sigma5 Validation Cluster
|   +-- MTIB Node 1: Individual unit under test
|   +-- MTIB Node 2: Individual unit under test
|   +-- ...
|
+-- ICLE Meter Validation
    +-- MTIB Node(s): Individual meter units
```

Each product's validation cluster has its own dedicated set of MTIB nodes. The nodes are identical hardware to manufacturing (Verdin iMX8M Mini + Mallow + MTIB carrier board) but are configured for single-unit testing.

## Software Architecture

### Kubernetes-Native Job Scheduling

Validation uses a different execution model than manufacturing. Instead of a persistent operator + test runner pair, validation tests are submitted as **Kubernetes batch Jobs**:

```
UI / API
  |
  POST /v2/validation/tests/run
  |
  HTTP API creates K8s Jobs via batch API
  |
  +-- Job 1: {product}-val-{hash}-electrical
  +-- Job 2: {product}-val-{hash}-app-post
  +-- Job 3: {product}-val-{hash}-comm-post
  |
  K8s scheduler assigns jobs to nodes
  (pod anti-affinity: max 1 job per node)
```

**Job Template:** `apps/backend/http-api/assets/templates/validation_job.yaml`

Placeholders substituted at runtime:
- `JOB_ID`, `JOB_NAME` -- Unique identifiers
- `PRODUCT` -- Target product
- `FIRMWARE_PATH` -- Firmware binary location
- `ENVIRONMENT` -- Runtime environment
- `MTIB_PORT` -- gRPC port for MTIB server
- Test-specific enable flags

**Job Naming:** `{product}-val-{hash(uuid+testname)}-{version}` (max 63 chars, RFC 1123)

### Test Types

| Type | Description |
|------|-------------|
| **Electrical** | Hardware functionality: power, voltage, current, GPIO |
| **App POST** | Application-level verification after firmware deployment |
| **Comm POST** | Communication verification: BLE, cellular, sensors |

### Execution Flow

```
1. Operator selects product and validation test suite in UI
2. API creates 3 Kubernetes Jobs (one per test type)
3. K8s scheduler assigns each job to an available node
   - Pod anti-affinity ensures one job per node
   - Node selectors target nodes with required hardware features
4. Each job container connects to the local MTIB server via gRPC
5. Tests execute against the DUT through MTIB hardware abstraction
6. Results are collected and stored
7. Jobs complete and are cleaned up by K8s
```

### Products with Validation

| Product | Location | Notes |
|---------|----------|-------|
| **Sigma5** | `apps/validation/sigma5/` | Primary validation target |
| **ICLE Meter** | `apps/validation/icle_meter/` | Metering device validation |
| **Test Steps** | `apps/validation/test_steps/` | Shared test step library |

## MTIB Capabilities Used in Validation

Validation tests typically exercise more MTIB capabilities than manufacturing, since tests are more thorough:

- **Power profiling** -- Extended current monitoring over time (V2: timestamped samples)
- **ADC measurements** -- Multi-channel voltage characterization
- **GPIO sequencing** -- Complex digital I/O patterns
- **Motion control** -- Positioning DUT for environmental/mechanical tests
- **Sensor monitoring** -- Temperature, pressure, humidity tracking during test
- **Debug probes** -- Zephyr shell access, thread monitoring, memory inspection (V2)
- **UART logging** -- Capture device console output throughout test

## Data Model

Validation uses the same Prisma models as manufacturing, with some differences:

```
Product ("Sigma5")
  └─ Fixture ("Sigma5 Validation Bench A", type=VALIDATION)
       └─ FixtureSlot (slotIndex=0, label="DUT 1") ─── Node (mtib-val-01)
       └─ FixtureSlot (slotIndex=1, label="DUT 2") ─── Node (mtib-val-02)

Session ("Sigma5 FW v2.3 Validation", target=null, fixture=above)
  └─ Device (serialNumber="SIG5-V-001", status=IN_PROGRESS)
       └─ TestExecution (test=Electrical, status=PASSED)
       └─ TestExecution (test=App POST, status=PASSED)
       └─ TestExecution (test=Comm POST, status=RUNNING)
       └─ TestExecution (test=Stress, status=QUEUED)
```

Key differences from manufacturing:
- `Session.targetCount` is often null (open-ended validation runs)
- `Session.fixtureId` may be null for ad-hoc validation sessions
- Fewer devices per session, but more test executions per device
- Test `category` values may include "stress", "environmental", "endurance"
- Test `sortOrder` matters more (longer dependency chains)
- Session `config` stores firmware version, environmental conditions, etc.

## Current State and Gaps

**Working:**
- Kubernetes Job-based test scheduling for Sigma5
- Basic electrical / app-POST / comm-POST test types
- MTIB hardware interaction via gRPC
- Product, Fixture, Session, Device data model in Prisma

**In Progress / Needs Work:**
- [ ] Validation-specific dashboard in the frontend
- [ ] Long-running test support (hours-long suites with progress tracking)
- [ ] Test suite composition (define which tests run in what order via sortOrder)
- [ ] Result comparison across validation runs (regression detection)
- [ ] Environmental test integration (temperature chambers, vibration)
- [ ] Pass/fail criteria management per product per test
- [ ] Firmware version tracking per validation run (Session.config)
- [ ] MTIB V2 protocol for advanced profiling and debugging
- [ ] Automated report generation for compliance documentation
- [ ] Historical trend analysis (drift detection over time)
- [ ] Audit trail for all validation operations
