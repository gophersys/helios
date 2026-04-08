---
min_role: DEVELOPER
---
# Validation

Every firmware change runs through 5 stages before it ships. Stage 1 catches logic bugs in seconds on a CI runner. Stages 2-4 flash real boards on MTIB fixtures and exercise drivers, subsystems, and full product behavior. Stage 5 pushes firmware over the air via CoreCloud and confirms the device boots on the new image.

A PR cannot merge until stages 1, 2, 3, and 5 pass. Stage 4 runs nightly as a longer regression suite.

| Stage | Focus | Hardware | Time |
|-------|-------|----------|------|
| **1 -- Smoke** | Application logic on `native_sim` | None | 1-2 min |
| **2 -- Driver** | SPI/I2C/GPIO drivers on dev kits | Dev kit + MTIB | 5-15 min |
| **3 -- Integration** | Cross-MCU IPC, sensor orchestration | Product board + MTIB | 15-30 min |
| **4 -- Regression** | Full product characterization, GPS, charger, motion | Product board + MTIB + CoreCloud | 30-60 min |
| **5 -- FUOTA** | OTA delivery, MCUboot swap, post-update boot | Product board + MTIB + CoreCloud | < 15 min |

Read the [stages overview](stages-overview.md) for what each stage tests, how it triggers, and where the test code lives. [Running validation](running-validation.md) covers triggering runs from the UI and API. [Writing tests](writing-tests.md) walks through the `corekinect` test framework, fixture controllers, and package structure. [Results](results.md) explains how to read outcomes and compare runs. The [validation queue](queue.md) manages scheduling and priority when multiple builds compete for fixtures. [Run detail](run-detail.md) documents the session page layout, and [real-time view](realtime.md) covers WebSocket-driven live updates during active sessions.
