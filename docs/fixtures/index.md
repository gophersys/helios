---
min_role: MAINTAINER
---
# Fixtures

Physical test stations. Each fixture connects an MTIB controller to a device under test via power, SWD/J-Link, UART, and GPIO. Fixture designs define the hardware layout. Instances are the actual rigs registered in Concord.

## Sections

- **[Managing fixtures](managing-fixtures.md)** — MTIB registration, instance creation, device assignment
- **[Designs](designs.md)** — hardware blueprints (auto-extracted from test packages)
- **[Instances](instances.md)** — physical rigs, validation vs manufacturing types
- **[Slots & deployment](slots-and-deployment.md)** — MTIB node assignment and K8s deployment
