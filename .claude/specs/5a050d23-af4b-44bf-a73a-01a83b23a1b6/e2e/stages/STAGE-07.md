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

# Stage 7: Fixture & MTIB Deployment Fixes (IMPLEMENTATION + TEST)

**Status:** Pending
**Type:** IMPLEMENT + TEST
**Dependencies:** Stage 2
**Estimated Tests:** ~45

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

## MTIB Server Deployment (IMPLEMENTATION)

### Architecture

Development runs entirely on docker-compose locally (http-api, postgres, minio, etc.). The ONLY K8s interaction is deploying MTIB server pods to edge nodes. This is the same across all environments — only the K8s namespace differs:

| Environment | Backend Services | MTIB Server | K8s Namespace |
|-------------|-----------------|-------------|---------------|
| Development | docker-compose (local) | K8s pod on edge node | `development` |
| Staging | K8s (staging namespace) | K8s pod on edge node | `staging` |
| Production | K8s (production namespace) | K8s pod on edge node | `production` |

The http-api container (whether local docker-compose or K8s pod) has kubeconfig access to the office K3s cluster at 10.4.45.10:6443.

### Infrastructure Changes Required

**New files in `infrastructure/clusters/office/`:**

1. `namespaces/development.yaml` — Create `development` namespace
2. `rbac/bindings-development.yaml` — RBAC for concord-api SA in development namespace
3. Update `bootstrap.sh` to apply development namespace + RBAC

These follow the exact same pattern as existing staging/production namespace manifests.

### Node Discovery Flow

```
MTIB hardware boots → joins K8s as node with role=edge (already done)
    ↓
Concord API: POST /v2/devices/mtibs/discover (sync_nodes_from_k8s)
    → K8s API: list nodes with role=edge
    → Compares against registered DB nodes
    → Returns: registered[], discovered[] (not yet in DB), offline[]
    ↓
Fixture creation UI: shows dropdown of discovered/registered nodes
    → User selects node → POST /v2/fixtures/{id}/slots/{sid}/assign
    ↓
Backend:
    1. Labels K8s node: corekinect.com/managed-by=concord
    2. Creates K8s Deployment in environment-specific namespace
       (development/staging/production) pinned to that node hostname
    3. Waits for pod ready (gRPC :50053 responding)
    4. Updates Node record (status=ONLINE, deployment_name in metadata)
    5. Updates FixtureSlot (nodeId assigned)
```

### Dev MTIB Identity

```
K8s hostname:  verdin-imx8mm-15005665
IP:            10.4.45.33
Role:          edge
gRPC port:     50053 (via hostPort on K8s Deployment)
J-Link App:    821009543 (NRF52)
J-Link Comms:  821009541 (NRF91)
DUT:           Alpha B0, SNR 0964, no battery, ch0 @ 4.5V
```

### What already works

- `_deploy_mtib_for_slot()` in `fixtures/fixtures.py:522` — creates K8s Deployment, stores deploy name in Node.metadata
- `_undeploy_mtib_for_slot()` in `fixtures/fixtures.py:548` — deletes K8s Deployment, clears metadata
- `assign_slot_node()` in `fixtures/fixtures.py:486` — assigns node, auto-deploys MTIB
- `_unassign_slot_node()` in `fixtures/fixtures.py:468` — unassigns node, auto-undeploys MTIB
- `sync_nodes_from_k8s()` in `nodes/nodes.py:157` — discovers ARM64 nodes from K8s cluster
- `create_mtib_deployment()` in `services/kubernetes/mtib_deployments.py:11` — creates K8s Deployment
- `delete_mtib_deployment()` in `services/kubernetes/mtib_deployments.py:93` — deletes K8s Deployment

### What needs to be fixed

**Infrastructure (new files):**
1. **Create `development` namespace** — `infrastructure/clusters/office/namespaces/development.yaml` following the pattern of existing staging/production namespace manifests.
2. **RBAC for development** — `infrastructure/clusters/office/rbac/bindings-development.yaml` granting concord-api SA permission to manage deployments/pods in development namespace.
3. **Update `bootstrap.sh`** — apply the new namespace + RBAC manifests.

**Backend (fix existing code):**
4. **Namespace awareness** — `create_mtib_deployment()` in `mtib_deployments.py:79` hardcodes `namespace="default"`. Must read from env: `MTIB_NAMESPACE` (default `development` for dev, matches environment for staging/production). Same for `delete_mtib_deployment()` and `get_mtib_deployment_status()`.
5. **Node delete doesn't undeploy** — `nodes.py:300` has TODO. Wire up `delete_mtib_deployment()` using `metadata["deployment_name"]` before deleting the DB record.
6. **Node type change doesn't redeploy** — `nodes.py:278` has TODO. If type changes, undeploy old + deploy new.
7. **K8s node labeling** — On assign: label K8s node with `corekinect.com/managed-by=concord`. On unassign: remove label. Use K8s API `patch_node()`.
8. **gRPC health check after deploy** — After K8s Deployment created, poll gRPC port 50053 on the node IP until responding (with timeout). Currently `_deploy_mtib_for_slot()` returns immediately without verifying server started.

### Unit Tests

```python
# tests/api/fixtures/test_mtib_deployment.py
test_discover_returns_unlabeled_nodes()
test_assign_node_creates_k8s_deployment()
test_assign_node_labels_k8s_node()
test_unassign_node_deletes_k8s_deployment()
test_unassign_node_removes_label()
test_deploy_targets_correct_namespace()
test_deploy_waits_for_pod_ready()
test_undeploy_handles_404_gracefully()
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
