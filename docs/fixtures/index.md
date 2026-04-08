---
min_role: MAINTAINER
---
# Fixtures

Every validation run and manufacturing session targets a physical device through a fixture — an MTIB controller wired to a specific product's DUT. The MTIB handles power, SWD programming via J-Link, UART, and GPIO; the fixture layer adds product-specific pin mapping and sensor wiring on top.

Fixtures are registered in Concord and assigned to validation benches or manufacturing stations. One MTIB can host multiple fixture instances if the wiring supports it.

**[Managing fixtures](managing-fixtures.md)** covers MTIB registration, fixture design, instance creation, and device assignment. **[Fixture designs](designs.md)** documents the hardware blueprint CRUD. **[Fixture instances](instances.md)** covers physical rig creation and types. **[Slots & deployment](slots-and-deployment.md)** explains how MTIB nodes connect to fixture positions and how K8s deployments are managed.
