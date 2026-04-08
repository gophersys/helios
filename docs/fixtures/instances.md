---
min_role: MAINTAINER
---
# Fixture Instances

A fixture instance is a physical test rig. It exists on a bench, has cables plugged into a DUT, and runs validation or manufacturing sessions. Every instance is bound to a product and classified as one of two types.

## Types

| Type | Purpose |
|------|---------|
| **VALIDATION** | Automated testing during CI. Runs pytest suites against DUTs through MTIB hardware. |
| **MANUFACTURING** | Factory POST. Executes manufacturing test sequences during production. |

A single product can have multiple instances of each type -- one validation rig per bench, one manufacturing station per line.

## Creating an instance

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique label for this rig (e.g., "Alpha Val Bench 1") |
| `productId` | string | The product this fixture tests |
| `type` | enum | `VALIDATION` or `MANUFACTURING` |

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Notes about this specific rig |
| `stationId` | string | External station identifier (must be unique if provided) |
| `slots` | array | Initial slot configuration (see [Slots & deployment](slots-and-deployment.md)) |

```bash
curl -X POST https://concord.local/v2/fixtures \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alpha Val Bench 1",
    "productId": "<product-id>",
    "type": "VALIDATION",
    "stationId": "VAL-001",
    "slots": [{ "slotIndex": 0, "label": "Primary DUT" }]
  }'
```

A newly created instance starts with status **AVAILABLE**, meaning the scheduler can assign queue entries to it.

### Uniqueness constraints

Both `name` and `stationId` must be unique across all fixtures. Duplicating either returns a **409 Conflict** error. This prevents two rigs from sharing the same identity or station code.

## Listing instances

```bash
curl https://concord.local/v2/fixtures \
  -H "Authorization: Bearer <token>"
```

Returns all instances with their product and type. Filter by product or type using query parameters.

## Instance detail

```bash
curl https://concord.local/v2/fixtures/<fixture-id> \
  -H "Authorization: Bearer <token>"
```

The detail response includes the instance metadata plus a `slots` array showing each slot's index, label, and assigned node (if any). This is the primary view for checking which MTIB nodes are connected.

## Editing an instance

Update the name or description of an existing fixture:

```bash
curl -X PATCH https://concord.local/v2/fixtures/<fixture-id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alpha Val Bench 1 (Updated)",
    "description": "Moved to rack B, slot 3"
  }'
```

## Status

| Status | Meaning |
|--------|---------|
| **AVAILABLE** | Fixture is idle and can accept queue assignments |
| **LOCKED** | A validation session is actively using this fixture |
| **DRAFT** | Fixture is configured but not yet ready for scheduling |

The scheduler only assigns queue entries to AVAILABLE fixtures. When a session starts, the fixture moves to LOCKED and returns to AVAILABLE when the session completes.

---

See also: [Fixture designs](designs.md) for the blueprint that defines a rig's hardware spec, [Slots & deployment](slots-and-deployment.md) for connecting MTIB nodes to fixture slots, [Managing fixtures](managing-fixtures.md) for the end-to-end fixture workflow, [Manufacturing station setup](../manufacturing/station-setup.md) for MANUFACTURING-type fixtures.
