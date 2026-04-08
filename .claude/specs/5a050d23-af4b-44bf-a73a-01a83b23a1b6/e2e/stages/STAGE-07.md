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

# Stage 7: Fixture Management

**Status:** Pending
**Dependencies:** Stage 2
**Estimated Tests:** ~40

---

## Test Files

### `e2e/stories/fixtures/designs.spec.ts` (~10 tests)

```
test('Designs tab shows empty state when no designs exist')
test('create design: name="Alpha E2E v1.2", boardRevision=Alpha B0')
test('design appears in list with correct name and revision')
test('design detail shows capabilities and profile template')
test('edit design: update revision and notes')
test('duplicate design name returns conflict error')
test('delete design with no fixture instances succeeds')
test('delete design with active fixture instances blocked (409)')
test('Admin/Maintainer can manage designs')
test('Developer can view but not manage designs')
```

### `e2e/stories/fixtures/instances.spec.ts` (~12 tests)

```
test('Fixtures tab shows empty state when no fixtures exist')
test('create VALIDATION fixture: name, product, board revision, design, stationId')
test('fixture appears in list with correct product and type')
test('fixture detail page shows slots section')
test('fixture status is AVAILABLE after creation')
test('create MANUFACTURING fixture for same product')
test('manufacturing fixture appears with correct type badge')
test('edit fixture: update name and description')
test('fixture stationId must be unique (conflict error on duplicate)')
test('Admin/Maintainer can create fixtures')
test('Developer cannot create fixtures (no button/403)')
test('Operator cannot see fixtures page (redirected)')
```

### `e2e/stories/fixtures/slots.spec.ts` (~8 tests)

```
test('fixture created with initial slots (based on config)')
test('add additional slot to fixture')
test('slot has label and slotIndex')
test('slot shows "unassigned" when no node linked')
test('remove slot when no test executions linked')
test('remove slot blocked when it has test execution history')
test('slot assignment UI shows available nodes')
test('slot shows assigned node after assignment')
```

### `e2e/stories/fixtures/deployment.spec.ts` (~5 tests)

```
test('create Node: hostname="mtib-e2e-dev", type=VALIDATION, ip=10.4.45.33')
test('assign node to fixture slot → MTIB deployment triggered')
test('fixture deploy-status shows slot deployment state')
test('deploy all slots button deploys all assigned slots')
test('undeploy fixture removes all MTIB deployments')
```

### `e2e/stories/fixtures/deletion.spec.ts` (~5 tests)

```
test('fixture with no sessions can be deleted')
test('fixture with session history cannot be deleted (409)')
test('fixture with LOCKED status cannot be deleted')
test('delete fixture cascades to slots')
test('after fixture deletion, node is unassigned and available')
```

---

## MTIB Node Configuration

For the dev pool MTIB (10.4.45.33):

```typescript
const DEV_MTIB_NODE = {
  hostname: 'mtib-e2e-dev',
  type: 'VALIDATION',
  ipAddress: '10.4.45.33',
  hardwareRevision: 'REV1.2',
  metadata: {
    jlinkAppSerial: '821009543',
    jlinkCommsSerial: '821009541',
    uartAppPath: '/dev/verdin-uart2',
    uartCommsPath: '/dev/verdin-uart1',
    dutSnr: '0964',
    dutDeviceId: '70B3D584C01E1FCC',
  },
};
```

---

## Gate Criteria

- [ ] Fixture design CRUD works through UI
- [ ] Fixture instance CRUD works with product/board binding
- [ ] Slot management works (add, remove, assign node)
- [ ] Node assignment triggers MTIB deployment
- [ ] Deletion constraints enforced correctly
- [ ] Role-based access correct (Admin/Maintainer manage, Developer view)
- [ ] All 40 tests pass
