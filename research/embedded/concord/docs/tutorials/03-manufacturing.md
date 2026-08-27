---
min_role: OPERATOR
---

# Tutorial 3: Manufacturing

**Duration:** ~10 minutes
**Audience:** Operators, Maintainers, System Admins
**Format:** Presentation + live session demo + optional external camera showing fixture

---

## Slide Outline

### Slide 1 — Title

**Visual:** Manufacturing session page screenshot

**Content:**

> Manufacturing: From Panel Scan to Tested Unit

**Speaker notes:**
This tutorial covers the manufacturing workflow in Concord. By the end you'll understand how a manufacturing session works, what happens when you scan a panel, and how to read results.

---

### Slide 2 — The Manufacturing Goal

**Visual:** Simple flow

**Content:**

```
Blank PCB → Flash firmware → Run POST tests → Tested unit (pass/fail per device)
```

Manufacturing in Concord:
- Flashes the correct firmware version onto every processor
- Runs Power-On Self Test (POST) on each device
- Records pass/fail with detailed telemetry per test
- Tracks every unit by serial number

**What changes from before:** Full traceability. Every unit that leaves the fixture has a complete test record — what passed, what failed, what measurements were taken, who ran it, when.

**Speaker notes:**
Before Concord, we had pass/fail with limited detail. Now we have per-test, per-device, per-measurement data. If a unit fails in the field, we can pull its manufacturing record and see exactly what happened during production.

---

### Slide 3 — Session Lifecycle

**Visual:** State diagram

**Content:**

```
[Admin creates session] → ACTIVE → [Admin ends session] → ENDED
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               Run Panel  Run Panel  Run Panel ...
```

| Action | Who | What happens |
|--------|-----|--------------|
| Create session | System Admin | Selects product + fixture + firmware. Deploys runner pod. |
| Run panel | Any operator | Scans QR code. Tests execute on all slots in parallel. |
| End session | System Admin | Shuts down runner. No more panels can be run. |

**Speaker notes:**
A session is a "shift." Admin starts it at the beginning of production, operators run panels throughout the day, admin ends it when production is done. The runner pod stays alive the whole time — it's always ready for the next panel.

---

### Slide 4 — What Happens When You Scan a Panel

**Visual:** Sequence diagram

**Content:**

1. Operator scans panel QR code (or types the identifier)
2. Concord creates a **run** with one **target** per fixture slot
3. Runner receives the panel assignment via WebSocket
4. For each slot **in parallel**:
   - Power cycle the DUT
   - Open UART streams
   - Lock the manufacturing shell (within 2s boot window)
   - Execute all test modules sequentially
5. Results stream back to the UI in real-time
6. Run completes — pass/fail per slot

**Speaker notes:**
The parallel execution is key. A 4-slot fixture tests 4 devices simultaneously. Each slot is independent — if slot 2 fails, slots 0, 1, and 3 continue. You don't lose a whole panel because one device has an issue.

---

### Slide 5 — Test Stages in Manufacturing

**Visual:** Three sequential blocks

**Content:**

Manufacturing tests run in three stages:

| Stage | What it does | Duration |
|-------|-------------|----------|
| **Electrical** | Power rails, ADC readings, current draw verification | ~10s |
| **Firmware Flash** | Erase + flash app and comms firmware via J-Link | ~30s |
| **POST (Power-On Self Test)** | Full functional verification after flash | ~60s |

POST includes:
- Chip ID verification
- BLE MAC address read
- IMEI / ICCID read (modem)
- IPC communication between processors
- Personalization (CoreOps key exchange)
- NFC verification
- Accelerometer/sensor checks

**Speaker notes:**
These stages run sequentially because they depend on each other. You can't POST a device that hasn't been flashed. You can't flash a device that failed electrical. If a stage fails, that slot stops — the device is marked failed and the operator can see exactly which test broke.

---

### Slide 6 — Reading Results

**Visual:** Screenshot of run results page

**Content:**

The results page shows:

- **Per-slot status** — green/red per device position
- **Per-test breakdown** — which specific test passed or failed
- **Measurements** — actual values (current, voltage, signal strength) with pass/fail thresholds
- **Duration** — how long each test took
- **Error messages** — if a test failed, what went wrong

**Real-time:** Results update live as tests execute. You don't wait for the whole panel to finish.

**Speaker notes:**
If something fails, the error message tells you what happened. "Expected current >5mA, got 0.2mA" means the power rail isn't reaching the device — check the probe contact. "Failed to lock shell within 20s" means the device didn't boot — check the firmware or the power connection.

---

### Slide 7 — Operator Workflow (Day-to-Day)

**Visual:** Numbered steps

**Content:**

Your daily workflow as an operator:

1. Open Concord in the browser
2. Navigate to the active manufacturing session
3. Load a panel into the fixture
4. Scan the panel QR code (or click "Run" and type the identifier)
5. Watch results come in (~90 seconds per panel)
6. If all green: remove panel, load next one
7. If red: note which slot failed, set aside that unit, continue with next panel
8. At end of shift: report any recurring failures to maintainer

**Speaker notes:**
That's it. You don't configure anything. You don't choose firmware versions. You don't start or stop sessions. You scan and watch. If something looks wrong, escalate — don't try to fix it yourself.

---

### Slide 8 — When Things Go Wrong

**Visual:** Common failure scenarios table

**Content:**

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| "Failed to lock shell" | DUT didn't boot. Bad probe contact or dead device. | Re-seat panel, retry once. If persistent, set unit aside. |
| "Expected current >5mA, got 0mA" | No power reaching DUT. Check fixture probe alignment. | Re-seat panel. If persistent, notify maintainer. |
| "Flash failed: no J-Link response" | SWD connection issue. Probe not making contact. | Re-seat. Check for debris on pads. |
| All slots fail simultaneously | Runner or fixture issue, not device issue. | Notify maintainer/admin immediately. |
| One slot always fails | That fixture position may have a hardware issue. | Notify maintainer — may need fixture repair. |

**Speaker notes:**
The pattern matters. If one unit fails occasionally — that's a defective unit, set it aside. If the same slot fails repeatedly — that's a fixture issue, escalate. If everything fails at once — that's a system issue, stop and escalate immediately.

---

### Slide 9 — What Admins Configure (Reference)

**Visual:** Setup checklist

**Content:**

Before manufacturing can start, a system admin must:

1. Product exists with board revision and targets configured
2. Asset set uploaded (the firmware to flash)
3. Test package uploaded via `corectl upload --release`
4. Fixture registered with correct MTIB addresses
5. Manufacturing session created (selects product + fixture + asset set)
6. Runner pod deployed and healthy (automatic on session create)

Once configured, sessions can run indefinitely until ended.

**Speaker notes:**
Operators don't do any of this. If you're an operator and something isn't working, it's a configuration issue — escalate to a maintainer or system admin. Don't try to debug the runner or the fixture yourself.

---

### Slide 10 — Summary

**Visual:** Three key takeaways

**Content:**

1. **Scan and watch.** Operators load panels, scan, and monitor. Configuration is someone else's job.
2. **Parallel and independent.** Each slot tests independently. One failure doesn't kill the panel.
3. **Full traceability.** Every unit has a complete test record. Every measurement is logged.

Next: Tutorial 4 covers Validation — how firmware gets automatically tested against hardware before it ever reaches manufacturing.

---

## Live Demo Script (3-4 min)

If a manufacturing session is active:

1. **Session page** �� "Here's the active session. Shows the fixture, the firmware version, the operator."
2. **Start a run** — "I scan or type the panel ID. Watch the targets appear."
3. **Real-time results** — "See the tests executing. Each slot is independent. Results stream in as they complete."
4. **Completed run** — "All green. Click into a slot — here are the individual test results with measurements."

If no session is active, show a completed run from history and walk through the results page.

---

## Key Points to Reinforce

- Manufacturing is the simplest Concord workflow for operators. Scan. Watch. Repeat.
- The complexity is hidden behind the setup. Admins configure once, operators run daily.
- Real-time visibility is the biggest upgrade from before — you know immediately what's wrong.
- Escalation is expected and encouraged. Don't debug — report.
