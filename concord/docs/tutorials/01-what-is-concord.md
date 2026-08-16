---
min_role: OPERATOR
---

# Tutorial 1: What is Concord

**Duration:** ~10 minutes
**Audience:** Everyone
**Format:** Presentation + browser demo

---

## Slide Outline

### Slide 1 — Title

**Visual:** Concord logo + tagline

**Content:**

> Concord: Embedded Continuous Integration Platform

**Speaker notes:**
This is a short introduction to Concord — what it is, why it exists, and how it fits into our workflow. By the end you'll understand the high-level architecture and where your role fits in.

---

### Slide 2 — The Problem

**Visual:** Two columns — "Before" vs "After"

**Content:**

Before Concord:

- Builds compiled locally or through Temacity (slow, single-target, no integration)
- Validation was "developer runs tests at their desk" — no traceability
- Manufacturing had limited observability — pass/fail with no detailed data
- No connection between a code change and its real-world hardware behavior
- Every build-to-validation cycle required manual intervention

The core problem:

> We have no automated way to know if a firmware change works on real hardware until someone manually tests it.

**Speaker notes:**
We've shipped product with this approach, and it works — but it doesn't scale. Every new product, every new revision, every new firmware variant multiplies the manual effort. Concord eliminates that multiplication.

---

### Slide 3 — What Concord Does (One Sentence)

**Visual:** Single sentence, large text

**Content:**

> Concord takes firmware from code commit to validated-on-hardware with minimal human input, giving us high confidence in every release.

**Speaker notes:**
That's it. Everything else is implementation detail in service of this one goal. If a feature doesn't serve this, it doesn't belong.

---

### Slide 4 — The Pipeline

**Visual:** Linear flow diagram with four boxes

```
Code Commit → Build → Validate → Manufacture / Deploy to Field
```

**Content:**

| Stage | What happens | Who cares |
|-------|-------------|-----------|
| **Build** | Firmware compiled for all targets | Developers |
| **Validate** | Tests run on real hardware automatically | Developers, Maintainers |
| **Manufacture** | Production testing at scale with full traceability | Operators, Maintainers |
| **Deploy** | OTA push to devices already in the field | Developers, Maintainers |

Each stage feeds the next. A build produces an asset set. Validation runs that asset set through hardware stages. Once validated, that firmware can be flashed onto new units in manufacturing OR deployed over-the-air to existing devices in the field.

**Speaker notes:**
This is the mental model. Code goes in one end, validated firmware comes out the other — ready for manufacturing new units OR deploying to devices already in the field. The system handles scheduling, hardware allocation, result tracking, and reporting. You interact with it through the browser app or the CLI.

---

### Slide 5 — Validation Stages (The "Why")

**Visual:** Five sequential boxes with descriptions

**Content:**

| Stage | Question it answers | Runs when |
|-------|-------------------|-----------|
| **Smoke** | Does it boot? Do basics work? | Every commit |
| **Driver** | Do hardware peripherals function correctly? | Every commit (if enabled) |
| **Integration** | Do subsystems work together end-to-end? | Nightly or on-demand |
| **Regression** | Did we break anything that used to work? | Pre-release |
| **FUOTA** | Does over-the-air update work from previous version to this one? | Pre-release |

Each stage catches a different class of bug. Smoke is fast and cheap. FUOTA is slow and expensive. You run the cheap ones often and the expensive ones before release.

**Why FUOTA matters:** Once firmware passes the FUOTA stage, we know it can be safely deployed over-the-air to devices already in customers' hands. This is the final gate before a field update.

**Speaker notes:**
This is why there are five stages and not one. A smoke test that passes doesn't mean OTA works. A regression test that passes doesn't mean the driver initializes correctly on cold boot. Each layer adds confidence. Together, they give us near-certainty before firmware ships — whether that's to a new unit in manufacturing or to an existing device via OTA.

---

### Slide 6 — How Builds Get In

**Visual:** Three arrows pointing into the "Build" box

**Content:**

Firmware enters Concord three ways:

1. **Internal build service** — Concord watches a Git branch, compiles on push, produces an asset set automatically
2. **External CI upload** — Your existing CI (Temacity, GitHub Actions, etc.) compiles firmware and uploads the artifacts to Concord via API
3. **Manual upload** — A developer or admin uploads a pre-built hex/cfw directly

All three produce the same thing: an **asset set** that can be validated and manufactured with.

**Speaker notes:**
We're not asking anyone to throw away their build system tomorrow. If Temacity works for your product, keep using it — just upload the output to Concord and it flows through validation like anything else. Over time, the internal build service is faster and more integrated, but it's not mandatory.

---

### Slide 7 — Architecture (30,000 ft)

**Visual:** System diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Browser App                            │
│         (products, builds, validation, manufacturing)    │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────┐
│                      HTTP API                             │
│              (auth, scheduling, orchestration)            │
├──────────┬───────────┬────────────┬─────────────────────┤
│ Postgres │   MinIO   │ Build Svc  │    Git Poller       │
│ (data)   │ (files)   │ (compile)  │ (watch branches)    │
└──────────┴───────────┴────────────┴─────────────────────┘
                           │ gRPC
┌──────────────────────────▼──────────────────────────────┐
│                    Edge Nodes (ARM64)                     │
│                  MTIB Servers (per slot)                  │
│          [power] [uart] [gpio] [j-link] [adc]           │
└──────────────────────────┬──────────────────────────────┘
                           │ hardware
                    ┌──────▼──────┐
                    │    DUTs     │
                    │ (your PCBs) │
                    └─────────────┘
```

**Speaker notes:**
The browser app is where you interact with Concord. The API handles auth, scheduling, and orchestration. Storage is PostgreSQL for structured data and MinIO for files (firmware binaries, test packages, logs). Edge nodes sit physically next to the fixtures and control hardware via gRPC. Runners are temporary containers that download test code and execute it against the hardware.

---

### Slide 8 — What's Already In Place

**Visual:** Checklist with checkmarks

**Content:**

- Rolling deployments with zero downtime
- Automated database backups (daily)
- Helm rollback in <10 seconds if something breaks
- JWT authentication with role-based permission sets
- All firmware stored with checksums in redundant object storage
- Full audit log of every mutation (who did what, when)
- Network policies isolating every service
- Automated CI running nightly against the platform itself

**Speaker notes:**
I know the system has bugs and we're still iterating. But the foundation is solid. If something goes wrong, we can roll back in seconds. Data is backed up. Auth is real. This isn't a prototype — it's production infrastructure with production safeguards. We'll keep improving it, but the safety net is already there.

---

### Slide 9 — Roles

**Visual:** Four-tier pyramid or table

**Content:**

| Role | Access | Example people |
|------|--------|----------------|
| **Operator** | Run panels, view results | Gwen, Peter |
| **Developer** | Write/upload tests, view validation, trigger builds | Michael, Robert, Anton, Christian, Chris, Enos |
| **Maintainer** | Configure products, stages, test packages, fixtures | Blake |
| **System Admin** | Everything + users, sessions, deployments | Mateo, Jared |

Escalation path: Operator → Maintainer → System Admin

**Speaker notes:**
You don't need to know everything about Concord. Operators need to know manufacturing. Developers need to know validation and test authoring. Maintainers need to know product configuration. System admins need to know infrastructure. The tutorial series is structured this way — watch what applies to your role.

---

### Slide 10 — What's Next

**Visual:** Series roadmap

**Content:**

| Tutorial | What you'll learn |
|----------|-------------------|
| **This one** | What Concord is and why it exists |
| **Tutorial 2: Products** | How products are structured, configured, and managed |
| **Tutorial 3: Manufacturing** | Running a manufacturing session end-to-end |
| **Tutorial 4: Validation** | How automated validation works, stage configs, results |
| **Tutorial 5: Builds** | Internal build service, external CI integration, asset sets |

**Speaker notes:**
Each tutorial is ~10 minutes. Watch them in order — concepts build on each other. There's also a glossary in the docs if you hit a term you don't recognize. Questions and feedback are welcome — this is built for us, and if something doesn't make sense, that's a bug in the docs, not in you.

---

## Browser Demo Script (2-3 min at end)

After slides, switch to the browser and show:

1. **Dashboard** — "This is home. You see products, recent builds, active sessions."
2. **Product page** — "Click into Alpha. Here's the board, the revisions, the targets. This is the single source of truth for this hardware platform."
3. **Manufacturing tab** — "Active sessions show up here. Green means passing. We'll dive deep in Tutorial 3."
4. **Validation tab** — "Runs queue here automatically. Each row is a test run against real hardware. Tutorial 4 covers this."

Close with: "That's Concord at 30,000 feet. Next up: Products — how they're structured and why."

---

## Key Messaging (Internal)

Throughout this tutorial, the subtext is:

- **This is ours.** We built it because nothing on the market does what we need for embedded hardware CI.
- **It's real.** Production infrastructure with real safeguards, not a side project.
- **It reduces risk.** Every firmware release validated on real hardware before it ships.
- **Your role matters.** The system is designed for different levels of access because different people need different things.
- **We're iterating.** Bugs exist. Features are coming. But the architecture is sound and the trajectory is clear.
