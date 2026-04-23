---
min_role: MAINTAINER
---
# Fixture Designs

A fixture design defines the hardware specification for a test rig before any physical instance exists. It captures which product the rig targets, which board revision it is wired for, and any notes about pin mapping or wiring. Think of it as the blueprint -- [fixture instances](instances.md) are the built rigs.

## Creating a design

A design requires three fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique human-readable label (e.g., "Alpha B0 REV 1.2") |
| `boardRevisionId` | string | References a board revision from the [product's revision list](../products/board-revisions.md) |
| `revision` | string | Design revision identifier (e.g., "1.2", "2.0") |

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Short explanation of the design's purpose |
| `notes` | string | Wiring notes, pin assignments, known issues |

```bash
curl -X POST https://concord.local/v2/fixtures/designs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alpha B0 REV 1.2",
    "boardRevisionId": "cmnqaxivu000otjnrfiu2x0l0",
    "revision": "1.2",
    "description": "Single-DUT validation rig for Alpha B0"
  }'
```

Design names must be unique. Attempting to create a second design with the same name returns a **409 Conflict** error.

## Listing designs

```bash
curl https://concord.local/v2/fixtures/designs \
  -H "Authorization: Bearer <token>"
```

Returns a paginated list of all designs.

## Design detail

```bash
curl https://concord.local/v2/fixtures/designs/<design-id> \
  -H "Authorization: Bearer <token>"
```

Returns the full design record including name, board revision reference, revision string, description, and notes.

## Updating notes

The primary updatable field on a design is `notes`. Use this for wiring change logs, known issues, or pin mapping corrections:

```bash
curl -X PATCH https://concord.local/v2/fixtures/designs/<design-id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "notes": "Swapped GPIO 2/3 per REV 1.2 errata" }'
```

## Deleting a design

Designs can only be deleted if no fixture instances reference them. If instances exist, the delete request is rejected -- you must delete or reassign all instances first.

```bash
curl -X DELETE https://concord.local/v2/fixtures/designs/<design-id> \
  -H "Authorization: Bearer <token>"
```

A successful delete returns 200. Attempting to fetch the design afterward returns 404.

---

See also: [Fixture instances](instances.md) for creating physical rigs from a design, [Managing fixtures](managing-fixtures.md) for the full fixture lifecycle, [Board revisions](../products/board-revisions.md) for the revision records that designs reference.
