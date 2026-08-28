---
min_role: MAINTAINER
---
# Slots & Deployment

Slots are the connection points between a fixture and the MTIB nodes that control DUTs. Each slot represents one physical position where an MTIB node can be wired in. Deployment is what happens after you assign a node to a slot -- Concord creates a K8s Deployment for the MTIB server so it can serve gRPC traffic to the test runner.

## Slots

### Initial configuration

Slots can be created at fixture creation time by passing a `slots` array:

```json
{
  "name": "Alpha Val Bench 1",
  "productId": "<product-id>",
  "type": "VALIDATION",
  "slots": [
    { "slotIndex": 0, "label": "Primary DUT" }
  ]
}
```

Each slot has a `slotIndex` (integer position, starting at 0) and a `label` (human-readable name like "Primary DUT" or "Secondary DUT").

### Adding slots

Add a slot to an existing fixture:

```bash
curl -X POST https://concord.local/v2/fixtures/<fixture-id>/slots \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "slotIndex": 1, "label": "Secondary DUT" }'
```

The `slotIndex` must be unique within the fixture. Attempting to reuse an index returns a **409 Conflict**.

### Unassigned state

A freshly created slot has `nodeId: null`. It appears in the fixture detail but cannot participate in validation until a node is assigned. The fixture detail endpoint returns each slot's assignment state, making it straightforward to see which positions are wired and which are empty.

### Removing slots

Delete a slot only when no test executions are linked to it. If the slot has historical test data, the delete is blocked to preserve audit integrity.

```bash
curl -X DELETE https://concord.local/v2/fixtures/<fixture-id>/slots/<slot-id> \
  -H "Authorization: Bearer <token>"
```

## Node assignment

### Assigning a node

Link an MTIB node to a slot:

```bash
curl -X PATCH https://concord.local/v2/fixtures/<fixture-id>/slots/<slot-id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "nodeId": "<node-id>" }'
```

After assignment, the slot's `nodeId` field points to the MTIB node. The fixture detail reflects the link immediately.

### Unassigning a node

Set `nodeId` to `null` to disconnect a node from a slot:

```bash
curl -X PATCH https://concord.local/v2/fixtures/<fixture-id>/slots/<slot-id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "nodeId": null }'
```

The slot reverts to unassigned state.

## MTIB nodes

Before you can assign a node to a slot, the node must exist in Concord. Create one with:

```bash
curl -X POST https://concord.local/v2/nodes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MTIB-REV1.2-33",
    "hostname": "mtib-rev12-33.local",
    "type": "VALIDATION",
    "ipAddress": "10.4.45.33",
    "hardwareRevision": "REV1.2"
  }'
```

Node fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable label |
| `hostname` | string | DNS-resolvable hostname or identifier |
| `type` | string | `VALIDATION` or `MANUFACTURING` |
| `ipAddress` | string | IP address of the Verdin module running MTIB server |
| `hardwareRevision` | string | Board revision (e.g., "REV1.2") |

## Deployment

Assigning a node to a slot triggers deployment metadata creation. Concord records which node is attached to which slot and exposes a deploy-status endpoint so you can check the state of MTIB server deployments across the fixture.

### Deploy status

```bash
curl https://concord.local/v2/fixtures/<fixture-id>/deploy-status \
  -H "Authorization: Bearer <token>"
```

Returns a `slots` array with each slot's deployment state -- whether the MTIB server K8s Deployment exists, its pod status, and readiness. In environments without K8s access (development, CI), this endpoint may return a 500 since it cannot reach the cluster.

### Undeploying

Remove the K8s Deployment for a fixture's MTIB servers:

```bash
curl -X POST https://concord.local/v2/fixtures/<fixture-id>/undeploy \
  -H "Authorization: Bearer <token>"
```

This tears down the Deployments but does not unassign nodes from slots. The slot-to-node mapping persists; only the running pods are removed.

---

See also: [Fixture instances](instances.md) for creating the fixture that holds slots, [Fixture designs](designs.md) for the hardware blueprint, [Run detail](../validation/run-detail.md) for how test sessions use the assigned nodes.
