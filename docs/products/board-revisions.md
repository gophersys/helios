---
min_role: DEVELOPER
---
# Board Revisions

PCBs change. Sensors get swapped, pin assignments shift, power rails move, MCU variants change. Each time the hardware changes in a way that affects firmware, create a new board revision so Concord builds and validates the correct firmware variant against the correct hardware.

A revision carries three pieces of information:

- **Revision name** — B0, B1, C0, etc.
- **Board target** — the Zephyr board definition used during compilation (e.g., `corekinect_alpha_nrf52840`)
- **Status** — active or retired

Active revisions show up in the build and validation pipelines. Retired revisions stay in history but stop triggering new builds.

To add a revision, open the product detail page and click **Add Revision**. Each revision inherits the product's firmware repo link but can override the board target and build recipe if the new hardware needs different compilation flags or overlays.
