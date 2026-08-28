> **Archived 2026-03-30.** UI design spec and Prisma data model proposal from early 2026. The validation flow UI has since been implemented; the data model was superseded by the backend overhaul (see `docs/specs/backend-overhaul.md`). Moved from `reference/` — design specs belong in `architecture/`.

# Validation Flow UI Design

> Visual canvas for firmware validation pipelines. Shows real-time progress
> through multi-step validation flows with expandable details.

---

## 1. Naming Convention

Replace numbered "Stage X" with descriptive names:

| ID | Name | Icon | Color | Description |
|----|------|------|-------|-------------|
| `SIM` | **Simulation** | 🖥️ | Blue | Native_sim tests, no hardware |
| `DRV` | **Driver** | ⚡ | Yellow | Single driver on real hardware |
| `INT` | **Integration** | 🔗 | Orange | Multi-component on real hardware |
| `PRD` | **Product** | 📦 | Red | Black-box + FUOTA lifecycle |

---

## 2. Data Model

### ValidationDesign (the "template")

Defines a reusable validation flow as a directed graph of steps.

```prisma
model ValidationDesign {
  id          String   @id @default(cuid())
  name        String   // "Alpha B0 Full Validation"
  product     String   // "alpha"
  board       String   // "alpha_b0"
  description String?

  // Graph definition (JSON)
  nodes       Json     // Array of step definitions
  edges       Json     // Array of connections

  // Metadata
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  createdBy   String?

  // Relations
  runs        ValidationRun[]
}
```

**Node schema:**
```json
{
  "id": "flash_mfg",
  "type": "flash",           // flash | fuota | test | build | manual
  "label": "Flash MFG",
  "category": "PRD",         // SIM | DRV | INT | PRD
  "position": { "x": 100, "y": 200 },
  "config": {
    "matrixLabel": "mfg_base",
    "target": ["nrf52840", "nrf9151"],
    "requiresPersonalization": true
  }
}
```

**Edge schema:**
```json
{
  "id": "e1",
  "source": "flash_mfg",
  "target": "post_check",
  "condition": "success"     // success | failure | always
}
```

### ValidationRun (an instance)

An execution of a ValidationDesign.

```prisma
model ValidationRun {
  id          String   @id @default(cuid())
  designId    String
  design      ValidationDesign @relation(...)

  pipelineId  String?  // CI pipeline that triggered this

  status      ValidationRunStatus  // PENDING | RUNNING | PASSED | FAILED | CANCELLED

  // Execution context
  deviceId    String?  // DUT device ID
  nodeId      String?  // MTIB node running this

  // Timing
  startedAt   DateTime?
  finishedAt  DateTime?

  // Relations
  steps       ValidationStep[]

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}

enum ValidationRunStatus {
  PENDING
  RUNNING
  PASSED
  FAILED
  CANCELLED
}
```

### ValidationStep (node execution)

Tracks each node's execution within a run.

```prisma
model ValidationStep {
  id          String   @id @default(cuid())
  runId       String
  run         ValidationRun @relation(...)

  nodeId      String   // References node.id in design.nodes

  status      ValidationStepStatus  // PENDING | RUNNING | PASSED | FAILED | SKIPPED

  // Timing
  startedAt   DateTime?
  finishedAt  DateTime?
  durationMs  Int?

  // Results
  summary     String?  // "12/12 tests passed"
  errorMessage String?

  // Detailed output (expandable in UI)
  logs        String?  @db.Text
  artifacts   Json?    // Links to uploaded artifacts
  metrics     Json?    // Power readings, timing data, etc.

  // Test results (for test-type nodes)
  testsTotal  Int?
  testsPassed Int?
  testsFailed Int?
  testsSkipped Int?

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}

enum ValidationStepStatus {
  PENDING
  BLOCKED      // Waiting for upstream node
  RUNNING
  PASSED
  FAILED
  SKIPPED
}
```

---

## 3. UI Components

### 3.1 Canvas View (Main)

A react-flow or svelte-flow based canvas showing the validation graph:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Alpha B0 Full Validation                              [Trigger] [Edit] │
│ Pipeline: cmmk9o8zh00008785xh9ltn0d                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐      ┌───────────┐      ┌──────────┐      ┌───────────┐ │
│   │  BUILD  │─────▶│ FLASH MFG │─────▶│   POST   │─────▶│ FUOTA MFG │ │
│   │    ✓    │      │     ✓     │      │  12/12   │      │  ⏳ 45%   │ │
│   └─────────┘      └───────────┘      └──────────┘      └───────────┘ │
│                                                                │        │
│   ┌─────────────────────────────────────────────────────────────┘        │
│   ▼                                                                     │
│   ┌───────────┐      ┌─────────────┐      ┌─────────────┐              │
│   │POST CHECK │─────▶│ FUOTA DEBUG │─────▶│ TEST DEBUG  │──────▶ ...  │
│   │     ○     │      │      ○      │      │      ○      │              │
│   └───────────┘      └─────────────┘      └─────────────┘              │
│                                                                         │
│   Legend: ✓ Passed  ✗ Failed  ⏳ Running  ○ Pending  ⊘ Skipped        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Node States

| State | Icon | Color | Ring |
|-------|------|-------|------|
| PENDING | ○ | Gray | Dashed |
| BLOCKED | ⏸ | Gray | Solid |
| RUNNING | ⏳ | Blue | Animated pulse |
| PASSED | ✓ | Green | Solid |
| FAILED | ✗ | Red | Solid |
| SKIPPED | ⊘ | Yellow | Dashed |

### 3.3 Node Detail Panel (Expandable)

Click a node to expand details:

```
┌─────────────────────────────────────────────────────────┐
│ POST Check                                    [Collapse] │
├─────────────────────────────────────────────────────────┤
│ Status: PASSED                                          │
│ Duration: 2m 34s                                        │
│ Tests: 12/12 passed                                     │
├─────────────────────────────────────────────────────────┤
│ ✓ test_boot_current         0.8s                       │
│ ✓ test_uart_output          1.2s                       │
│ ✓ test_shell_lock           0.3s                       │
│ ✓ test_personalization      45.2s                      │
│ ✓ test_key_upload           2.1s                       │
│ ... (expand for more)                                   │
├─────────────────────────────────────────────────────────┤
│ Power Profile:                                          │
│ ┌──────────────────────────────────────────────────┐   │
│ │  Ch0: ████████░░ 17.3mA avg                      │   │
│ │  Ch1: ██░░░░░░░░  2.1mA avg                      │   │
│ └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│ Artifacts: [power.parquet] [uart_log.txt]              │
└─────────────────────────────────────────────────────────┘
```

### 3.4 FUOTA Progress (Special Node)

FUOTA nodes show page delivery progress:

```
┌─────────────────────────────────────────────────────────┐
│ FUOTA MFG → MFG_BUMP                          ⏳ 45%   │
├─────────────────────────────────────────────────────────┤
│ Target: 108.0.5.1-BMD, 109.0.5.1-BMD                   │
│ Pages: 234/512 delivered                                │
│ ████████████████░░░░░░░░░░░░░░░░░░ 45%                 │
│                                                         │
│ Timeline:                                               │
│   18:23:45  Plan created (id=31)                       │
│   18:24:01  Device assigned                             │
│   18:25:33  First page delivered                        │
│   18:45:12  234 pages delivered (45%)                   │
│   ...waiting for device uplink...                       │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Real-time Updates

### WebSocket Events

The backend emits events to `/validation` namespace:

```typescript
// Step status change
{
  event: "validation_step_update",
  data: {
    runId: "...",
    stepId: "...",
    nodeId: "flash_mfg",
    status: "RUNNING",
    progress: 45,         // Optional percentage
    summary: "Flashing nRF52840...",
  }
}

// Test result within a step
{
  event: "validation_test_result",
  data: {
    runId: "...",
    stepId: "...",
    testName: "test_boot_current",
    status: "PASSED",
    durationMs: 800,
    message: "Boot current 17.3mA (expected >5mA)",
  }
}

// FUOTA progress
{
  event: "validation_fuota_progress",
  data: {
    runId: "...",
    stepId: "...",
    pagesDelivered: 234,
    pagesTotal: 512,
    percentComplete: 45,
  }
}

// Log line (for live log streaming)
{
  event: "validation_log",
  data: {
    runId: "...",
    stepId: "...",
    line: "[18:45:12] FUOTA page 234 delivered",
    level: "INFO",
  }
}
```

---

## 5. Default Designs

### 5.1 Alpha B0 Full Validation

The 12-step FUOTA flow from `stage4-fuota-validation-flow.md`:

```json
{
  "name": "Alpha B0 Full Validation",
  "product": "alpha",
  "board": "alpha_b0",
  "nodes": [
    { "id": "build", "type": "build", "label": "Build Firmware", "category": "PRD" },
    { "id": "flash_mfg", "type": "flash", "label": "Flash MFG", "category": "PRD" },
    { "id": "post_1", "type": "test", "label": "POST", "category": "PRD" },
    { "id": "fuota_mfg", "type": "fuota", "label": "FUOTA MFG→MFG", "category": "PRD" },
    { "id": "post_2", "type": "test", "label": "POST Check", "category": "PRD" },
    { "id": "fuota_debug", "type": "fuota", "label": "FUOTA MFG→Debug", "category": "PRD" },
    { "id": "test_debug", "type": "test", "label": "Test Debug", "category": "PRD" },
    { "id": "fuota_debug2", "type": "fuota", "label": "FUOTA Debug→Debug", "category": "PRD" },
    { "id": "fuota_release", "type": "fuota", "label": "FUOTA Debug→Release", "category": "PRD" },
    { "id": "test_release", "type": "test", "label": "Test Release", "category": "PRD" },
    { "id": "flash_prev", "type": "flash", "label": "Flash Prev Release", "category": "PRD" },
    { "id": "upgrade_path", "type": "fuota", "label": "Upgrade Path", "category": "PRD" }
  ],
  "edges": [
    { "source": "build", "target": "flash_mfg" },
    { "source": "flash_mfg", "target": "post_1" },
    { "source": "post_1", "target": "fuota_mfg" },
    { "source": "fuota_mfg", "target": "post_2" },
    { "source": "post_2", "target": "fuota_debug" },
    { "source": "fuota_debug", "target": "test_debug" },
    { "source": "test_debug", "target": "fuota_debug2" },
    { "source": "fuota_debug2", "target": "fuota_release" },
    { "source": "fuota_release", "target": "test_release" },
    { "source": "test_release", "target": "flash_prev" },
    { "source": "flash_prev", "target": "upgrade_path" }
  ]
}
```

### 5.2 Alpha B0 Commit Validation (Fast)

Shortened flow for per-commit validation:

```json
{
  "name": "Alpha B0 Commit Validation",
  "product": "alpha",
  "board": "alpha_b0",
  "nodes": [
    { "id": "build", "type": "build", "label": "Build", "category": "PRD" },
    { "id": "flash_mfg", "type": "flash", "label": "Flash MFG", "category": "PRD" },
    { "id": "post", "type": "test", "label": "POST", "category": "PRD" },
    { "id": "fuota_debug", "type": "fuota", "label": "FUOTA→Debug", "category": "PRD" },
    { "id": "test_debug", "type": "test", "label": "Test Debug", "category": "PRD" },
    { "id": "fuota_release", "type": "fuota", "label": "FUOTA→Release", "category": "PRD" },
    { "id": "test_release", "type": "test", "label": "Test Release", "category": "PRD" }
  ],
  "edges": [
    { "source": "build", "target": "flash_mfg" },
    { "source": "flash_mfg", "target": "post" },
    { "source": "post", "target": "fuota_debug" },
    { "source": "fuota_debug", "target": "test_debug" },
    { "source": "test_debug", "target": "fuota_release" },
    { "source": "fuota_release", "target": "test_release" }
  ]
}
```

---

## 6. API Endpoints

### Designs

```
GET    /v2/validation/designs                 # List designs
POST   /v2/validation/designs                 # Create design
GET    /v2/validation/designs/:id             # Get design
PUT    /v2/validation/designs/:id             # Update design
DELETE /v2/validation/designs/:id             # Delete design
```

### Runs

```
GET    /v2/validation/runs                    # List runs (with filters)
POST   /v2/validation/runs                    # Create/trigger run
GET    /v2/validation/runs/:id                # Get run with steps
GET    /v2/validation/runs/:id/steps          # Get steps only
GET    /v2/validation/runs/:id/steps/:stepId  # Get step detail
POST   /v2/validation/runs/:id/cancel         # Cancel run
```

### Reporter (from test runner)

```
POST   /v2/validation/runs/:id/steps/:nodeId/start   # Step started
POST   /v2/validation/runs/:id/steps/:nodeId/result  # Test result
POST   /v2/validation/runs/:id/steps/:nodeId/finish  # Step finished
POST   /v2/validation/runs/:id/steps/:nodeId/log     # Log line
```

---

## 7. Frontend Routes

```
/validation                       # Dashboard (recent runs, designs)
/validation/designs               # Design library
/validation/designs/:id           # Design editor (canvas)
/validation/designs/:id/edit      # Edit mode
/validation/runs                  # Run history
/validation/runs/:id              # Run detail (canvas + live updates)
```

---

## 8. Implementation Plan

### Phase 1: Data Model + Basic UI
- [ ] Add Prisma models (ValidationDesign, ValidationRun, ValidationStep)
- [ ] Backend CRUD endpoints for designs/runs
- [ ] Basic canvas component (static, no editing)
- [ ] Run detail page with step states

### Phase 2: Real-time Updates
- [ ] WebSocket events for step updates
- [ ] Live log streaming
- [ ] FUOTA progress animation

### Phase 3: Design Editor
- [ ] Drag-and-drop node placement
- [ ] Edge drawing
- [ ] Node configuration panel
- [ ] Save/load designs

### Phase 4: Integration
- [ ] Connect to existing ValidationRun trigger
- [ ] Reporter plugin updates for step-based reporting
- [ ] CI pipeline integration

---

## 9. Tech Stack

| Component | Technology |
|-----------|------------|
| Canvas | Svelte Flow (svelte-flow) |
| State | Svelte 5 runes ($state, $derived) |
| WebSocket | Socket.IO (existing) |
| Backend | Flask + existing patterns |
| DB | Prisma + PostgreSQL |
