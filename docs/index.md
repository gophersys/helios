---
min_role: OPERATOR
---
# Concord

Concord turns firmware commits into tested, flashable artifacts and gets them onto production hardware. Push code, build hex files, validate across five stages, and flash devices on the manufacturing line — one pipeline, no gaps.

| Role | Start here |
|------|-----------|
| **Developer** | [Products](products/) to register hardware, [Builds](builds/) to compile firmware |
| **Operator** | [Manufacturing](manufacturing/) for factory-floor flashing and POST |
| **Maintainer** | [Fixtures](fixtures/) to configure test hardware, [Build Configuration](builds/build-configuration/) for recipes |
| **Admin** | [Administration](administration/) for users, roles, and platform settings |

The pipeline flows in order: define a [product](products/) and its board targets, [build](builds/) firmware from source, run [validation](validation/) (smoke through FUOTA), then [manufacture](manufacturing/) devices using approved artifacts. [Fixtures](fixtures/) are the test hardware that connects to your DUTs at each stage.

For API endpoints and system internals, see [Reference](reference/) and [Platform](platform/).
