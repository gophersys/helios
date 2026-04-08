<!-- AGENT RECOVERY PROTOCOL
If you are reading this after context compaction:
1. You are working on this specific stage
2. Read STATUS.md to find your progress within this stage
3. Read MEMORY.md for all decisions and gotchas
4. Read ORCHESTRATOR.md if you need the overall system or recovery steps
5. Continue from where STATUS.md says you left off
6. UPDATE STATUS.md after every significant action
7. Commit your work with descriptive messages (NO AI attribution)
8. When this stage is COMPLETE:
   a. Run the Post-Stage Reconciliation Protocol (see ORCHESTRATOR.md)
   b. Write a ## Reconciliation section at the bottom of THIS file
   c. Do a Global Coherence Check against SPEC.md
   d. Update any downstream stage files if your work changed assumptions
   e. Update STATUS.md and MEMORY.md
   f. THEN exit
-->

# Stage 11: Manufacturing Frontend (IMPLEMENTATION)

**Status:** Pending
**Type:** IMPLEMENT (new feature, TDD)
**Dependencies:** Stage 10 (Manufacturing Backend)
**Estimated Unit Tests:** ~20

---

## Objective

Build the manufacturing frontend: fixture list, session runner with QR input, live panel results per unit, session history. Replace the placeholder `/manufacturing` page.

---

## Pages

### `/manufacturing` — Manufacturing Hub

**Layout:**
- PageHeader: "Manufacturing"
- Two tabs: "Fixtures" and "Sessions"

**Fixtures Tab:**
- List manufacturing fixtures with: name, product, slot count, status (AVAILABLE/LOCKED), active session indicator
- Each fixture card shows:
  - Fixture name and product
  - Number of slots (e.g., "4 slots")
  - Status badge (AVAILABLE = green, LOCKED = yellow)
  - "New Session" button (if AVAILABLE, requires manufacturing:run)
  - Active session link (if LOCKED)

**Sessions Tab:**
- Paginated list of manufacturing sessions
- Columns: ID, product, fixture, operator, panel count, pass/fail, status, started, duration
- Status filter: ACTIVE, COMPLETED, CANCELLED
- Click row → navigate to session detail

### `/manufacturing/session/[id]` — Live Session Runner

**Layout:**
- Session header: product, fixture, operator, status, started time, elapsed timer
- Panel input section (top):
  - QR code text input field (placeholder: "Scan or enter panel QR code")
  - "Run Panel" button (disabled while panel is running)
  - "End Session" button (confirmation dialog)
- Active panel section (middle):
  - Panel QR code displayed
  - Grid of unit cards (one per fixture slot):
    - Slot label
    - Unit serial number (if discovered)
    - Stage progress (Electrical → Flash → POST)
    - Per-stage status indicator (spinner/check/X)
    - Overall unit status badge
    - Duration
    - Error message (if failed)
  - Panel summary bar: "3/4 units passed" with progress
- Panel history section (bottom):
  - Accordion list of completed panels
  - Each shows: QR code, pass/fail count, duration
  - Expand to see unit details

### `/manufacturing/sessions` — Session History

**Layout:**
- Same as Sessions tab on `/manufacturing` but as a standalone page
- Full pagination and filtering
- Deep link support

---

## Components

| Component | File | Purpose |
|-----------|------|---------|
| `ManufacturingFixtureCard` | `components/manufacturing/fixture-card.svelte` | Fixture with status and "New Session" |
| `ManufacturingSessionCard` | `components/manufacturing/session-card.svelte` | Session summary in list |
| `PanelRunner` | `components/manufacturing/panel-runner.svelte` | QR input + Run Panel + End Session |
| `UnitCard` | `components/manufacturing/unit-card.svelte` | Per-DUT stage progress |
| `UnitStageProgress` | `components/manufacturing/unit-stage-progress.svelte` | Electrical→Flash→POST progress bar |
| `PanelResultsGrid` | `components/manufacturing/panel-results-grid.svelte` | Grid of UnitCards |
| `PanelHistory` | `components/manufacturing/panel-history.svelte` | Accordion of past panels |
| `SessionHeader` | `components/manufacturing/session-header.svelte` | Session info + elapsed timer |

---

## Real-time Updates (WebSocket)

Subscribe to `/manufacturing` namespace on session detail page:

```typescript
// On mount:
socket.emit('subscribe_manufacturing_session', { sessionId });

// Listen for:
socket.on('manufacturing_unit_start', (data) => {
  // Add/update unit card — show spinner for active stage
});
socket.on('manufacturing_stage_result', (data) => {
  // Update stage indicator (check/X) on unit card
});
socket.on('manufacturing_unit_result', (data) => {
  // Update unit card overall status
});
socket.on('manufacturing_panel_complete', (data) => {
  // Move panel to history, update summary counts
  // Re-enable "Run Panel" button
});
```

---

## Permission Gating

```svelte
<!-- Fixtures tab: New Session button -->
{#if auth.hasPermission('manufacturing:run')}
  <button on:click={startSession}>New Session</button>
{/if}

<!-- Session runner: Run Panel button -->
{#if auth.hasPermission('manufacturing:run')}
  <PanelRunner {session} />
{/if}

<!-- View-only mode for manufacturing:view without manufacturing:run -->
<!-- Shows session data but no action buttons -->
```

---

## Vitest Unit Tests (TDD)

```typescript
// components/manufacturing/fixture-card.test.ts
test('shows fixture name and product')
test('shows AVAILABLE status when fixture not locked')
test('shows LOCKED status with active session link')
test('New Session button visible with manufacturing:run')
test('New Session button hidden without manufacturing:run')

// components/manufacturing/unit-card.test.ts
test('shows slot label and serial number')
test('shows stage progress indicators')
test('updates stage from RUNNING to PASSED')
test('shows error message on FAILED')

// components/manufacturing/panel-runner.test.ts
test('QR input field accepts text')
test('Run Panel disabled while panel is running')
test('End Session shows confirmation dialog')
test('panel results grid shows correct unit count')

// routes/manufacturing/+page.test.ts
test('renders fixtures tab by default')
test('sessions tab shows session list')
test('permission check redirects if no manufacturing:view')
```

---

## Gate Criteria

- [ ] `/manufacturing` page shows fixtures and sessions tabs
- [ ] Fixture cards show correct status and "New Session" button
- [ ] Session runner page loads with QR input and panel grid
- [ ] Unit cards update in real-time via WebSocket
- [ ] Panel history shows completed panels
- [ ] Permission gating works (manufacturing:run for actions, manufacturing:view for read)
- [ ] All 20 vitest unit tests pass
