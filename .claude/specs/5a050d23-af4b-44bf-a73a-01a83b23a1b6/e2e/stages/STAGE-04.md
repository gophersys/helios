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

# Stage 4: Stage Configuration

**Status:** Pending
**Dependencies:** Stage 3
**Estimated Tests:** ~30

---

## Test Files

### `e2e/stories/products/stage-config-wizard.spec.ts` (~15 tests)

```
test('clicking stage card opens Stage Config Wizard')
test('Step 1: board revision dropdown populated with product revisions')
test('Step 1: selecting Alpha B0 revision enables next step')
test('Step 1: watch branch defaults to "concord-main"')
test('Step 1: trigger types checkboxes (manual, cron, pr_push)')
test('Step 1: cron expression input appears when cron selected')
test('Step 2: signing key dropdown shows available secrets')
test('Step 2: can create new signing key inline')
test('Step 3: recipe editor loads with syntax highlighting')
test('Step 3: recipe validate button checks YAML syntax')
test('Step 3: invalid recipe shows error feedback')
test('Step 3: test build button triggers real build with live terminal')
test('Step 3: test build terminal shows streaming log output')
test('Step 4: confirmation shows all configured values')
test('Step 4: save enables the stage (stage pill turns active)')
```

### `e2e/stories/products/recipe-editor.spec.ts` (~8 tests)

```
test('recipe editor shows line numbers')
test('loading recipe template populates editor')
test('recipe history shows previous versions')
test('recipe diff view compares two versions')
test('saving recipe increments version number')
test('publishing recipe makes it the active version')
test('recipe validation catches common YAML errors')
test('recipe variables section shows substitution tokens')
```

### `e2e/stories/products/build-matrix.spec.ts` (~7 tests)

```
test('build matrix shows default entries for stage')
test('each matrix entry has label, fwType, variant, configLog fields')
test('adding matrix entry appends to list')
test('removing matrix entry removes from list')
test('reordering matrix entries updates sortOrder')
test('Stage 5 (FUOTA) matrix has 7-8 entries by default')
test('reset matrix button restores defaults')
```

---

## Gate Criteria

- [ ] All 5 stages configurable via wizard
- [ ] Recipe editor works with syntax highlighting and validation
- [ ] Test build triggers real build with live log streaming
- [ ] Build matrix configurable per stage
- [ ] Signing keys assignable to stages
- [ ] All 30 tests pass
