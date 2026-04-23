---
min_role: DEVELOPER
---
# Board Revisions

Track PCB changes. Each revision builds and validates independently.

## What a revision defines

- **Version** — B0, B1, C0
- **`ck_boards` name** — maps to the Zephyr board definition, overlays, and devicetree
- **SoC targets** — one per processor, each with a role and AppID
- **Status** — ACTIVE or DEPRECATED

Deprecated revisions stop triggering builds. Validation stage configs tied to a deprecated revision are disabled automatically.

## Managing revisions

Product detail → **Hardware** tab. Add, edit, or deprecate from there.
