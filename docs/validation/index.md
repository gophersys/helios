---
min_role: DEVELOPER
---
# Validation

Five stages test firmware on real hardware before it ships.

| Stage | Focus | Hardware | Time |
|-------|-------|----------|------|
| **1 — Smoke** | Application logic | None (native_sim) | 1-2 min |
| **2 — Driver** | SPI/I2C/GPIO drivers | Dev kit + MTIB | 5-15 min |
| **3 — Integration** | Cross-MCU IPC, sensors | Product board + MTIB | 15-30 min |
| **4 — Regression** | Full product characterization | Product board + MTIB + CoreCloud | 30-60 min |
| **5 — FUOTA** | OTA delivery, MCUboot swap | Product board + MTIB + CoreCloud | < 15 min |

A PR cannot merge until stages 1, 2, 3, and 5 pass. Stage 4 runs nightly.

## Sections

- **[Stages overview](stages-overview.md)** — what each stage tests, triggers, test code location
- **[Running validation](running-validation.md)** — trigger runs from UI and API
- **[Writing tests](writing-tests.md)** — corekinect test framework, fixture controllers, package structure
- **[Results](results.md)** — read outcomes, compare runs
- **[Queue](queue.md)** — scheduling and priority when builds compete for fixtures
- **[Run detail](run-detail.md)** — session page layout
- **[Real-time](realtime.md)** — WebSocket live updates during active sessions
