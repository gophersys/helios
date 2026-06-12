# Eden Architecture — Document Set

> Status: Draft for review · Created: 2026-06-12 · Owner: Mateo
> This set is the canonical architecture of **Eden** (formerly Helios — ADR-0002), the agentic
> engineering platform. It sits downstream of the research corpus and upstream of all code.

## 1. Layering — where this set fits

```
~/Documents/research/agentic-engineering/      WHY      — the substrate: Bender failure modes,
        │                                                 ecosystem graph, universal SDLC spine
        ▼
~/Documents/Claude/Projects/Helios/            HOW-WE-  — build-system design: spec-driven system,
        │   (to be migrated under Eden naming)  BUILD     agentcfg, agents.yaml, 12 invariants
        ▼
docs/architecture/  (THIS SET)                 WHAT     — the Eden platform: charter, decomposition,
        │                                                 process model, connectors, bootstrap
        ▼
code (eden monorepo · gophersys/libs · photosphere · infrastructure)
```

Lower layers never depend on higher ones. Where this set and the upstream corpus conflict, this
set wins and must record the supersession as an ADR (the corpus is renamed/migrated lazily).

**Transitional:** upstream corpus documents still say "Helios". Per ADR-0002 every document in
this set says **Eden**; upstream docs are corrected as they are touched, never silently.

### Source registry (every shorthand used in this set)

| Shorthand | Resolves to |
|---|---|
| corpus doc NN / corpus README | `~/Documents/research/agentic-engineering/NN-*.md` / its `README.md` |
| Bender | Adam Bender (Principal Engineer, Google), "Software Engineering at the Tipping Point" (2026); catalogued in corpus docs 01–03 |
| build-system README | `~/Documents/Claude/Projects/Helios/README.md` — home of the 12 **build-system invariants I1–I12** |
| spec-driven §N | `~/Documents/Claude/Projects/Helios/spec-driven-implementation-system.md` |
| agentcfg / portable-agent-config | `~/Documents/Claude/Projects/Helios/agentcfg-architecture.md` / `portable-agent-config-2026-06.md` (upstream artifact names; the Eden library is `agentconfiguration`) |
| cell invariants I1–I10 | corpus doc 04 (the Cell schema invariants) |
| 10 §N (library system) | [10-library-system.md](10-library-system.md) — absorbed the former root `/LIBRARY-SYSTEM.md` + `/LIBRARIES.md` (originals in `docs/attic/`, ADR-0010) |
| photosphere ADR-NNNN | `gophersys/photosphere` `docs/adr/` (a different chain from this set's `adr/`) |

Two upstream invariant families share the I-prefix; this set always qualifies citations as
**"cell invariant IN"** (corpus doc 04) or **"build-system invariant IN"** (build-system README).

## 2. Reading order

| # | Document | One-line scope | Status |
|---|---|---|---|
| 00 | [Charter](00-charter.md) | What Eden is, theses, scope, non-goals | Draft |
| 01 | [Principles](01-principles.md) | The 13 organizing principles | Draft |
| 02 | [Domain model](02-domain-model.md) | Entities, glossary, schema ownership | Draft |
| 03 | [System decomposition](03-system-decomposition.md) | Subsystems, boundaries, dependency rules | Draft |
| 04 | [Process model](04-process-model.md) | The Eden SDLC: spine instantiation, phase schemas, gates | Draft |
| 05 | [Connector model](05-connector-model.md) | Contract spec for everything external; drift detection | Draft |
| 06 | [Dogfooding & bootstrap](06-dogfooding-bootstrap.md) | The L0–L4 ladder; migration/update model | Draft |
| 07 | [Security model](07-security-model.md) | Credentials, sandboxing, supply chain, audit | Draft |
| 08 | [Testing strategy](08-testing-strategy.md) | Three test layers; evidence quality instruments | Draft |
| 09 | [Build execution plan](09-build-execution-plan.md) | How we build Eden with Claude; workstreams | Draft |
| 10 | [Library system](10-library-system.md) | Patterns, HNS-1 naming, environment≠platform axes, lifecycle, manifest | Draft |
| 11 | [Project document system](11-project-document-system.md) | Document tiers, id/link grammar, envelope, traceability, enforcement | Draft |
| 12 | [Presentation layer](12-presentation-layer.md) | Visual-first thesis, view altitudes A0–A4, diagram-as-projection, navigation/IA | Draft |
| — | [Open decisions](open-decisions.md) | Register of unruled items | Living |
| — | [adr/](adr/) | Decision records (ADR-0001…) | Living |
| — | [contracts/](contracts/README.md) | WS1 contract negotiation drafts (not frozen) | Drafts |

The former root planning docs (`/LIBRARIES.md`, `/LIBRARY-SYSTEM.md`) are absorbed into doc 10
(ADR-0010); originals preserved in `docs/attic/`. `docs/research/00–03` remain as point-in-time
research notes (see `docs/research/README.md`). Doc 10 sits last in the reading order but is
migrated *foundational* material — when working on libraries, read 10 §1–§5 alongside 01–02.

## 3. Epistemic legend (mandatory on claims — build-system invariant I12)

| Tag | Meaning |
|---|---|
| ✅ | **Verified** — confirmed against an external source or a working artifact |
| 🔶 | **Hypothesis** — survived pressure-testing; falsifiable; not yet proven by a working instance |
| ⚠️ | **Corrected** — verification showed an earlier claim wrong; the corrected form is given. Never used as a generic caution marker. |
| 🧩 | **Design choice** — a decision with named alternatives; ruled in place, recorded as an ADR, or queued in the open-decisions register |

## 4. Cohesion contract — one concept, one home

Every concept has exactly one canonical definition. Other documents cite; they never redefine.

| Concept | Canonical home |
|---|---|
| Eden charter, theses, scope | 00 |
| Principles P1–P13 | 01 |
| Entity definitions (Project, Cell, Spec, Evidence, Gate, Connector, Drift, Swarm, FileLease, …) | 02 |
| Subsystem boundaries S1–S10 + dependency rules | 03 |
| The 10-phase spine (upstream: corpus doc 04) — Eden instantiation | 04 |
| Phase artifact schemas + gate policy | 04 |
| Connector anatomy, families, capability manifests, conformance | 05 |
| Drift detection & remediation | 05 |
| Bootstrap ladder L0–L4, migration model | 06 |
| Threat model, credential & sandbox rules | 07 |
| Test layers, mutation/spec-determinacy instruments | 08 |
| Workstreams, interface negotiation protocol, milestones | 09 |
| Evidence interface, Spec envelope, harness senses | upstream spec-driven (cited via 02) |
| Cell parameter vector D1–D5, **cell invariants I1–I10**, topology selector | upstream corpus doc 04 |
| **Build-system invariants I1–I12** | upstream build-system README |
| Pattern catalogue, HNS-1 naming, dev→release→adopt lifecycle, library manifest | 10 |
| Environment ≠ Platform axes (hard rule, detection, default map) | 10 §2 |
| Bender failure modes 1–15 (compact in-repo list) | 03 §1 |
| Document tiers, id/link grammar, envelope, traceability rules T1–T7 | 11 |
| Presentation thesis, view-altitude model A0–A4, diagram-as-projection contract, navigation/IA | 12 |
| Engine altitudes (product/component recursion depth) | 04 §3 |

## 5. Eden-level invariants

These extend (never replace) the 12 build-system invariants. E-rows that operationalize a thesis
or principle point at it rather than restating it — one formulation, one home.

| ID | Invariant |
|---|---|
| E1 | Everything external sits behind a connector contract (= P1; checked by the 05 anatomy checklist and import-boundary lint). |
| E2 | No artifact without a schema: every phase input/output validates against a versioned schema before acceptance (= P2; checked at phase boundaries and in CI, 04 §4). |
| E3 | No promotion without evidence (= P3/T3; checked by gate policy, 04 §5). |
| E4 | Drift is detected, never silently absorbed (= P10/T7; checked per connector family, 05 §5). |
| E5 | Eden builds Eden (= P11/T5; checked by ladder exit criteria, 06). |
| E6 | Humans sit at gates, not in loops (= P13; checked by gate-policy schema — no phase may require synchronous supervision, 04 §5). |
| E7 | No `helios` identifier in new code or documents; renames recorded, not improvised (ADR-0002). |

## 6. Review protocol

Comments or edits in place; every ruling that changes a 🧩 becomes an ADR or an open-decisions
row movement. Per-document status lives in the §2 table and is updated as documents are accepted.
