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

# Stage 12: Manufacturing Setup Wizard (IMPLEMENTATION)

**Status:** Pending
**Type:** IMPLEMENT (new feature, TDD)
**Dependencies:** Stages 10, 11
**Estimated Unit Tests:** ~15

---

## Objective

Add a Manufacturing tab to the product detail page with a setup wizard — similar to the validation stage configuration wizard. Allows Admin/Maintainer to configure manufacturing stages, firmware source, personalization settings, and pass criteria for a product.

---

## Product Detail: Manufacturing Tab

**Location:** Add to existing product detail tabs (after Validation tab)

**Tab Content:**
- Manufacturing enabled/disabled toggle
- Board revision selector
- Manufacturing stages configuration (Electrical, Flash, POST)
- Firmware source configuration
- Personalization settings
- Pass criteria editor

---

## Manufacturing Config Wizard (multi-step modal)

### Step 1: Base Configuration

- Select board revision (dropdown, same as validation)
- Enable/disable manufacturing for this revision
- Select fixture design (dropdown — only MANUFACTURING designs for this board revision)

### Step 2: Stage Configuration

For each manufacturing stage (Electrical, Flash, POST):
- Enable/disable toggle
- Configuration parameters:

**Electrical Stage:**
- Power rail voltages (ch0, ch1)
- Expected current ranges (min/max mA)
- Bus scan targets (I2C addresses, SPI devices)
- GPIO check pins

**Flash Stage:**
- Firmware source: "Latest build" | "Specific version" | "Manual upload"
- If latest build: auto-selects from validation builds (same fingerprint = cached)
- If specific version: version picker from FirmwareSet list
- Flash targets: app (nRF52840), comms (nRF9151)
- J-Link speed: 4000 (default)

**POST Stage:**
- Enable/disable substeps (boot, chip ID, BMS, charger, GPS, modem, IMEI, flash R/W, personalize, IPC rekey)
- Personalization config:
  - CoreOps server URL
  - Device type, device variant
  - Default carrier
- IMEI/ICCID validation rules
- Power thresholds per substep

### Step 3: Pass Criteria

- Overall pass: all stages must pass? Or configurable?
- Per-stage pass criteria (thresholds, timing limits)
- Retry policy: how many retries per unit on failure?

### Step 4: Review & Save

- Summary of all configuration
- Save button → creates/updates ManufacturingConfig

---

## Components

| Component | File | Purpose |
|-----------|------|---------|
| `ManufacturingTab` | `components/products/tabs/manufacturing-tab.svelte` | Manufacturing config display + wizard trigger |
| `ManufacturingConfigWizard` | `components/products/manufacturing-config-wizard.svelte` | Multi-step config wizard |
| `ManufacturingStageConfig` | `components/products/manufacturing-stage-config.svelte` | Per-stage config form |
| `FirmwareSourcePicker` | `components/products/firmware-source-picker.svelte` | Latest/specific/upload firmware selector |

---

## Vitest Unit Tests (TDD)

```typescript
// components/products/tabs/manufacturing-tab.test.ts
test('shows "not configured" when no ManufacturingConfig exists')
test('shows config summary when configured')
test('configure button opens wizard for Admin/Maintainer')
test('configure button hidden for Developer')

// components/products/manufacturing-config-wizard.test.ts
test('Step 1: board revision dropdown populated')
test('Step 2: shows 3 manufacturing stages')
test('Step 2: firmware source picker shows options')
test('Step 3: pass criteria form renders')
test('Step 4: review shows all values')
test('save creates ManufacturingConfig via API')

// components/products/firmware-source-picker.test.ts
test('latest build option shows most recent build info')
test('specific version shows version dropdown')
test('manual upload shows file input')
```

---

## Gate Criteria

- [ ] Manufacturing tab appears on product detail page
- [ ] Config wizard creates ManufacturingConfig via API
- [ ] Firmware source picker works for all 3 modes
- [ ] Pass criteria configurable per stage
- [ ] Permission gating: manufacturing:manage required to configure
- [ ] All 15 vitest unit tests pass
