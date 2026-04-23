---
min_role: MAINTAINER
---
# Manufacturing Fixtures

Manufacturing fixtures are the physical stations on the factory floor. Each one is a fixture instance backed by an MTIB controller, wired to test a specific product's boards. Before operators can run sessions, a Maintainer needs to create the fixture design, spin up instances, and assign MTIB nodes to slots.

## Fixture Designs

A fixture design describes the hardware layout for a product and board revision. Create one through the Concord UI or the CLI.

For a manufacturing fixture, the design specifies which board revision it targets (e.g., Alpha B0) and what capabilities the physical hardware has -- power control, J-Link probes, UART ports, GPIO, and any product-specific sensors.

Navigate to **Fixtures > Designs** and click **Add Design**. Fill in the name (something descriptive like "Alpha B0 Manufacturing"), select the board revision, set the hardware revision string, and save.

## Creating Fixture Instances

A fixture instance ties a design to real hardware. Each instance represents one station on the floor.

Navigate to **Fixtures > Instances** and click **Add Instance**:

1. Select the fixture design you just created
2. Give it a name operators will recognize (e.g., "MFG Station 3 - Alpha B0")
3. Set the station ID -- a unique identifier for this physical location
4. Define slots -- each slot maps to one DUT position on the fixture. A two-up fixture gets two slots (`Slot 0`, `Slot 1`); a single-DUT fixture gets one

The fixture type must be **MANUFACTURING**. Concord separates manufacturing fixtures from validation fixtures because they serve different workflows -- manufacturing runs high-volume production sessions, validation runs engineering test suites.

## Assigning MTIB Nodes

Each slot on the fixture needs an MTIB node assigned to it. The MTIB handles the low-level hardware control: power rails, J-Link SWD programming, UART communication, and GPIO.

To assign a node to a slot, select the fixture instance, pick the slot, and choose an MTIB from the registered nodes list. The node must already be registered in Concord (see [Managing Fixtures](../fixtures/managing-fixtures.md) for MTIB registration).

If an MTIB is already assigned to another slot on a different fixture, Concord blocks the assignment. One MTIB per slot.

## Fixture Cards on the Manufacturing Page

Once a manufacturing fixture exists with at least one slot and an assigned MTIB, it appears on the **Manufacturing** page as a fixture card. The card shows:

- Fixture name
- Status badge -- **AVAILABLE** when idle, **LOCKED** when a session is running
- **New Session** button (visible to users with the `manufacturing:run` permission)

Operators see fixture cards too -- they need `manufacturing:view` to access the Manufacturing page -- but they can only start sessions if their permission set includes `manufacturing:run`.

## Permissions

| Action | Required permission |
|--------|-------------------|
| Create fixture designs and instances | `fixtures:manage` (Maintainer+) |
| Assign MTIB nodes to slots | `fixtures:manage` (Maintainer+) |
| View manufacturing fixtures | `manufacturing:view` (Operator+) |
| Start sessions on fixtures | `manufacturing:run` (Operator+ with session permission) |

## Related

- [Fixture instances](../fixtures/managing-fixtures.md) -- MTIB registration, design uploads, and device assignment
- [Fixture overview](../fixtures/index.md) -- how fixtures fit into validation and manufacturing
- [Manufacturing sessions](sessions.md) -- what happens after an operator clicks New Session
