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

# Stage 3: Product CRUD

**Status:** Pending
**Dependencies:** Stage 2
**Estimated Tests:** ~50

---

## Test Files

### `e2e/stories/products/creation-wizard.spec.ts` (~15 tests)

```
test('Products page shows empty state when no products exist')
test('Create Product button visible for Admin/Maintainer')
test('Create Product button NOT visible for Developer')
test('clicking Create Product opens wizard modal')
test('Step 1: branch selector loads branches from ck_boards repo')
test('Step 1: selecting "main" branch proceeds to step 2')
test('Step 2: board family list populated from ck_boards discovery')
test('Step 2: selecting "alpha" board family proceeds to step 3')
test('Step 3: board revision config shows SoC fields')
test('Step 3: configuring nrf52840 (app, appId=109) + nrf9151 (comms, appId=108)')
test('Step 3: firmware repo slug validation (async check against Bitbucket)')
test('Step 3: repo existence indicator shows green check for valid repo')
test('Step 3: repo existence indicator shows red X for invalid repo')
test('Step 4: review page shows all configured values')
test('Step 4: confirm creates product and redirects to detail page')
```

### `e2e/stories/products/detail-tabs.spec.ts` (~12 tests)

```
test('product detail page loads with correct product name and description')
test('Overview tab shows product metadata (name, slug, repos, active status)')
test('Hardware tab shows board with revisions')
test('Hardware tab shows product targets per revision (app/comms with appIds)')
test('Assets tab shows firmware sets (empty initially)')
test('Manufacturing tab renders')
test('Validation tab shows 5 stage cards')
test('Validation tab shows stage enable/disable status')
test('tab navigation persists in URL hash')
test('breadcrumb navigation back to products list works')
test('product stage pills show correct enabled count on list page')
test('product card on list page shows board revision info')
```

### `e2e/stories/products/edit.spec.ts` (~8 tests)

```
test('Admin can edit product name inline')
test('Admin can edit product description')
test('Admin can edit firmware repo slug')
test('save button submits changes and shows success')
test('cancel button reverts changes')
test('Maintainer can edit product fields')
test('Developer cannot edit product fields (no edit button visible)')
test('editing slug to existing name shows conflict error')
```

### `e2e/stories/products/delete.spec.ts` (~8 tests)

```
test('delete button visible for Admin/Maintainer')
test('delete button NOT visible for Developer')
test('clicking delete shows confirmation dialog')
test('confirmation dialog requires typing product name')
test('confirming delete removes product from list')
test('product with build history cannot be deleted (409 shown in UI)')
test('product with no history can be deleted (cascades boards, stages)')
test('deleted product no longer appears in search')
```

### `e2e/stories/products/board-management.spec.ts` (~7 tests)

```
test('board revision list shows all revisions with version and status')
test('adding board revision creates new entry')
test('board revision shows targets (SoCs, appIds)')
test('editing board revision updates version and notes')
test('deprecating board revision changes lifecycle status')
test('sync-revisions from ck_boards updates board data')
test('revision with active fixtures cannot be deleted')
```

---

## Gate Criteria

- [ ] Product created via full 4-step wizard
- [ ] All 5 detail tabs render with correct data
- [ ] Edit/save/cancel works on product fields
- [ ] Delete succeeds for clean products, blocked for products with history
- [ ] Board revisions manageable through UI
- [ ] Role-based visibility correct (Admin/Maintainer can manage, Developer view-only)
- [ ] All 50 tests pass
