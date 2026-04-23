---
min_role: OPERATOR
---

# Tutorial 2: Products

**Duration:** ~10 minutes
**Audience:** Everyone
**Format:** Presentation + live product page walkthrough

---

## Slide Outline

### Slide 1 — Title

**Visual:** Product page screenshot

**Content:**

> Products: The Container for Everything

**Speaker notes:**
In Tutorial 1 we covered the pipeline: Build → Validate → Manufacture. A product is the thing that flows through that pipeline. Everything in Concord — every build, every test, every manufacturing session — belongs to a product.

---

### Slide 2 — What is a Product?

**Visual:** Simple hierarchy diagram

**Content:**

A product represents a single hardware platform. It answers:

- What PCB are we building for?
- What processors are on it?
- What firmware goes on each processor?
- What tests verify it works?
- What fixtures manufacture it?

**One product = one hardware platform, managed end-to-end.**

Example: "Alpha" is a product. It has an nRF52840 (app processor) and an nRF9151 (comms coprocessor). It gets built, validated, and manufactured through Concord.

**Speaker notes:**
If you're building a new device — new PCB, new firmware — that's a new product in Concord. If you're revising an existing PCB (going from B0 to B1), that's a new board revision within the same product.

---

### Slide 3 — Product Hierarchy

**Visual:** Tree diagram

```
Product (e.g., "Alpha")
│
├── Board
│   └── Board Revision (e.g., "B0")
│       └── Product Targets
│           ├── App (nRF52840, AppID 108)
│           └── Comms (nRF9151, AppID 109)
│
├── Stage Configs (which stages are enabled)
│
├── Asset Sets (compiled firmware bundles)
│
├── Test Packages (uploaded test code)
│
├── Fixtures (physical test rigs)
│
└── Runs (validation + manufacturing results)
```

**Speaker notes:**
This tree is what you see on the product page. Each branch represents a different aspect of the product lifecycle. You don't need to understand all of them today — we'll cover manufacturing and validation in their own tutorials. The important thing is: it all lives under one product.

---

### Slide 4 — Board Revisions & Targets

**Visual:** Table showing revision → targets mapping

**Content:**

A board revision is a physical hardware version. When the PCB changes, you add a revision.

Each revision defines its **product targets** — the processors that need firmware:

| Revision | Target | SoC | Role | AppID |
|----------|--------|-----|------|-------|
| B0 | App | nRF52840 | Application processor | 108 |
| B0 | Comms | nRF9151 | Communications coprocessor | 109 |

**Why this matters:** When Concord builds firmware, it builds for each target. When it flashes a device, it knows which hex goes on which chip. When it validates, it knows what to expect from each processor.

**Speaker notes:**
The AppID connects to CoreCloud — that's how the device identifies itself to the cloud. The SoC determines which toolchain compiles the firmware. The role is how we distinguish "this hex goes on the app chip" from "this hex goes on the comms chip."

---

### Slide 5 — Asset Sets

**Visual:** Asset set as a "package" containing firmware files

**Content:**

An **asset set** is a versioned bundle of firmware — one binary per product target.

```
Asset Set: "v0.5.14 (debug)"
├── alpha_app_nrf52840.hex      (App target)
└── alpha_comms_nrf9151.hex     (Comms target)
```

Asset sets are the unit of work for everything downstream:
- Validation tests an asset set against hardware
- Manufacturing flashes an asset set onto production units
- FUOTA pushes an asset set to devices already in the field

**Where they come from:**
- Internal build service (automatic, from Git push)
- External CI upload (Temacity or other, via API)
- Manual upload (admin uploads pre-built files)

**Speaker notes:**
Think of an asset set like a release candidate. It's a complete, buildable, flashable version of your firmware. You don't validate individual hex files — you validate the set as a whole, because that's what ships.

---

### Slide 6 — Stage Configs

**Visual:** Stage config table from the product page

**Content:**

Stage configs control the validation pipeline for this product:

| Stage | Enabled | Branch | Purpose |
|-------|---------|--------|---------|
| Smoke | Yes | `main` | Boot + basic sanity |
| Driver | Yes | `main` | Peripheral verification |
| Integration | Yes | `develop` | End-to-end subsystem tests |
| Regression | No | — | Pre-release full suite |
| FUOTA | No | — | OTA update verification |

Each enabled stage watches a Git branch. When a new build lands, Concord automatically schedules validation for that stage.

**Speaker notes:**
This is where the automation lives. You configure it once: "for this product, run smoke tests on every main commit." From then on, Concord handles scheduling, hardware allocation, test execution, and result reporting — no human needed.

---

### Slide 7 — Test Packages

**Visual:** Test package upload flow

**Content:**

Test packages are Python test suites uploaded to Concord via `corectl`:

```bash
corectl upload --release    # Upload as released version
corectl upload              # Upload as dev version
```

A test package contains:
- `concord.yaml` — declares product, type, stages
- `tests/` — pytest modules organized by stage
- `pyproject.toml` — Python dependencies

Two types:
- **VALIDATION** — automated, scheduled by stage configs
- **MANUFACTURING** — operator-triggered, runs during sessions

**Speaker notes:**
The test code is separate from the firmware code. It lives in its own repo, has its own versioning, and gets uploaded independently. This means you can update tests without rebuilding firmware, and vice versa. Developers write these tests — Tutorial 4 (Validation) and Tutorial 3 (Manufacturing) cover how.

---

### Slide 8 — Fixtures

**Visual:** Photo of fixture hardware + slot diagram

**Content:**

A **fixture** is a physical test rig registered in Concord.

```
Fixture: "Alpha B0 Mfg Fixture 1"
├── Slot 0 — MTIB @ 10.4.45.36 (panel position 1)
├── Slot 1 — MTIB @ 10.4.45.39 (panel position 0)
├── Slot 2 — MTIB @ 10.4.45.37 (panel position 3)
├── Slot 3 — MTIB @ 10.4.45.34 (panel position 2)
└── Slot 4 — MTIB @ 10.4.45.33 (standalone)
```

Each slot has:
- Power control (programmable voltage)
- UART communication (two channels: app + comms)
- GPIO control
- J-Link access (for flashing)
- ADC measurements

**Speaker notes:**
Fixtures are configured by system admins. If you're an operator, you just need to know which fixture you're working with. If you're a developer writing tests, you interact with the fixture through the test framework — you call `slot.comms_shell.send_command()` and the framework handles the hardware layer.

---

### Slide 9 — Access Control

**Visual:** Permission flow diagram

**Content:**

Products have access control. Not everyone sees everything.

| Action | Required role |
|--------|--------------|
| View product & results | Any role with product access |
| Upload test packages | Developer+ |
| Edit stage configs | Maintainer+ |
| Upload asset sets | System Admin |
| Start/stop manufacturing sessions | System Admin |
| Run manufacturing panels | Operator+ (once session is active) |

Product access is granted per-user by system admins.

**Speaker notes:**
This isn't about gatekeeping — it's about not accidentally breaking production. Operators don't need to touch stage configs. Developers don't need to start manufacturing sessions. Everyone sees results. The escalation path is clear: Operator → Maintainer → System Admin.

---

### Slide 10 — Creating a Product (Admin Walkthrough)

**Visual:** Screenshots from creation wizard

**Content:**

System admins create products through the wizard:

1. **Select firmware repository** — which Bitbucket repo holds the firmware
2. **Select board family** — auto-discovered from ck_boards repo
3. **Configure** — name, slug, description, revision, targets with AppIDs
4. **Confirm** — review and create

After creation:
- Enable desired validation stages
- Upload or connect an asset set
- Register a fixture (if manufacturing)
- Upload test packages via corectl
- Grant access to team members

**Speaker notes:**
This is a system admin task. You do it once per product (or once per major hardware revision). After setup, the product is ready for builds, validation, and manufacturing. The next tutorials cover those workflows.

---

## Live Demo Script (3-4 min)

Walk through the Alpha product page in the browser:

1. **Overview tab** — "Here's the product summary. Board revision B0, two targets."
2. **Click into board revision** — "These are the targets. App on nRF52840, Comms on nRF9151. The AppIDs connect to CoreCloud."
3. **Stage configs** — "Smoke and Driver are enabled, watching main. When we push a build, validation starts automatically."
4. **Asset sets tab** — "Here are the firmware bundles. v0.5.14 debug — that's what's running in manufacturing right now."
5. **Test packages** — "Latest released package. This is the Python code that actually exercises the hardware."
6. **Fixtures** — "One fixture registered with 5 slots. 4 panel + 1 standalone."

Close with: "That's a product. Next up: Tutorial 3 covers manufacturing — how operators use this to produce tested units."

---

## Key Points to Reinforce

- A product is not just firmware. It's firmware + hardware + tests + fixtures + configuration.
- Everything is connected. A build produces an asset set. Validation tests that set. Manufacturing flashes that set.
- Configuration is done once by admins. Daily use is simple — results flow automatically.
- Access control exists to prevent accidents, not to slow people down.
