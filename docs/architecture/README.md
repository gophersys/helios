# Eden Architecture — Document Set

> Status: Draft for review · Created: 2026-06-12 · Owner: Mateo
> This set is the canonical architecture of **Eden** (formerly Helios — ADR-0002), the agentic
> engineering platform. It sits downstream of the research corpus and upstream of all code.

## 1. Layering — where this set fits

```
docs/upstream/agentic-engineering/             WHY      — the substrate: Bender failure modes,
        │                                                 ecosystem graph, universal SDLC spine
        ▼
docs/upstream/build-system/                    HOW-WE-  — build-system design: spec-driven system,
        │                                       BUILD     agentcfg, agents.yaml, 12 invariants
        ▼
docs/architecture/  (THIS SET)                 WHAT     — the Eden platform: charter, decomposition,
        │                                                 process model, connectors, bootstrap
        ▼
code (eden monorepo · gophersys/libs · photosphere · infrastructure)
```

Lower layers never depend on higher ones. Where this set and the upstream corpus conflict, this
set wins and must record the supersession as an ADR (the corpus is renamed/migrated lazily).

**Transitional:** the upstream corpus now lives in-repo under `docs/upstream/` (ADR-0014), still
Helios-named by design. Per ADR-0002 every document in *this* set says **Eden**; upstream docs are
corrected on touch, never silently — corrections land in the canonical set, which supersedes
upstream on conflict.

### Source registry (every shorthand used in this set)

| Shorthand | Resolves to |
|---|---|
| corpus doc NN / corpus README | `docs/upstream/agentic-engineering/NN-*.md` / its `README.md` |
| Bender | Adam Bender (Principal Engineer, Google), "Software Engineering at the Tipping Point" (2026); catalogued in corpus docs 01–03 |
| build-system README | `docs/upstream/build-system/helios-corpus-readme.md` — home of the 12 **build-system invariants I1–I12** |
| spec-driven §N | `docs/upstream/build-system/spec-driven-implementation-system.md` |
| agentcfg / portable-agent-config | `docs/upstream/build-system/agentcfg-architecture.md` / `portable-agent-config-2026-06.md` (upstream artifact names; the Eden library is `agentconfiguration`) |
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
| 13 | — *(removed)* | The git process moved to `.claude/rules/git-process.md`, its single home. Doc 13 and ADR-0019 are superseded and deleted by [ADR-0032](adr/0032-git-process-single-home.md). | Superseded |
| 14 | [Library engineering pipeline](14-library-engineering-pipeline.md) | The four-phase library SDLC + the 8-dimension test taxonomy + per-phase gates | Draft |
| 16 | [Application template system](16-application-template-system.md) | Templates in `libs/templates/` (ADR-0026 folds them into libs); sqlc/pgx, OpenAPI-first, the 5-files-per-route rule, libs-assembly, .claude enforcement (ADR-0023) | Draft |
| 17 | [Design language](17-design-language.md) | The Eden UI ruling: tokens, atomic hierarchy, information architecture, motion, the one-shell ruling, wizard/settings/theming patterns (grounds the ADR-0024 UI track) | Draft |
| 18 | [Release and home deploy](18-release-and-home-deploy.md) | The stable-release runbook: the one-verb cut, `release.yml` job-by-job, digest-pin GitOps promotion → Argo, the backing-stack prerequisites, verification, the six pipeline lessons, demo-vs-release (ADR-0028) | Accepted |
| 19 | [Connectors and user secret material](19-connectors-and-user-secrets.md) | The `platformgateway` `connectors` domain: per-user/org third-party credentials, envelope-encrypted in Postgres (`envelope` leaf lib, platform-Vault KEK), the write-once/fingerprint-only API, the `eden://connector/<id>` agent-resolution seam (ADR-0029) | Accepted |
| — | [Open decisions](open-decisions.md) | Register of unruled items | Living |
| — | [adr/](adr/) | Decision records (ADR-0001…) | Living |
| — | [contracts/](contracts/README.md) | WS1 contract negotiation drafts (not frozen) | Drafts |

The former root planning docs (`/LIBRARIES.md`, `/LIBRARY-SYSTEM.md`) are absorbed into doc 10
(ADR-0010); originals preserved in `docs/attic/`. `docs/research/00–05` remain as point-in-time
research notes (see `docs/research/README.md`). Doc 10 sits last in the reading order but is
migrated *foundational* material — when working on libraries, read 10 §1–§5 alongside 01–02.

The **TypeScript/Svelte UI track** is homed in **ADR-0024** (the TS/Svelte library-engineering
pipeline + the design system re-homed in-repo, amending ADR-0005; resolves OD-1) plus its empirical
foundation, the research note
[`docs/research/05-design-foundations.md`](../research/05-design-foundations.md) (the
`@eden/theme` proportion/color/contrast/motion/density math), and its interface ruling **doc 17**
(the Eden design language — tokens, atomic hierarchy, IA, the one-shell ruling). Read all three when
working on `libs/typescript/`. *(The canonical `NN-` series still skips 15 — a deliberate gap; the
next unused slot is 20.)*

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
| Library engineering pipeline (four phases) + the 8-dimension test taxonomy + phase gates | 14 (ADR-0020) |
| Application template system (libs/templates/, 5-files-per-route, sqlc/pgx, OpenAPI-first, two codegen axes, libs-assembly, .claude enforcement) | 16 (ADR-0023) |
| TypeScript/Svelte library-engineering pipeline (the `libs/typescript/` `@eden/*` set, the UI test-taxonomy recast + design-correctness dimension, the Bits-UI-primary behavior layer); the design system re-homed in-repo | ADR-0024 (amends ADR-0005); the `@eden/theme` math foundation = `docs/research/05-design-foundations.md` |
| Agent permission system (grants → human → advisor → default-deny; `Decision.Scope` once\|session; the `PermissionAdvisor` port + the data-derived risk-class wall; the native control-channel protocol obligation per adapter) | ADR-0025 (realizes the `agentsession` permission round-trip on the live path) |
| Read-only editor system (the gateway `GET /sessions/{id}/editor` seam in `editor_handler.go`; the `workspaceprovider` editor SIDECAR — additive `WorkspaceSpec.Editor *EditorSpec` + `CapEditorSidecar`, host-per-agent `<agent-id>.editor.<domain>` ingress on kubernetes, the `--volumes-from …:ro` sibling on docker; desktop ssh-remote read-only is OD-EDITOR-2, still open) | ADR-0027 (extends the `workspaceprovider` contract ADR-0016 + the `Entrypoint`/`CapWorkloadPod` precedent ADR-0022 §4; grounded in `docs/research/07-*`) |
| Interface design language (tokens, atomic hierarchy, information architecture, motion, the one-shell ruling, the wizard/settings/theming patterns) | 17 (grounds the ADR-0024 UI track; `@eden/theme` math = `docs/research/05-design-foundations.md`) |
| Stable release channel + home deploy (the tag-driven cut, `ghcr.io/gophersys/eden/*` prefix, the single `eden` namespace, the Vault-native token-file app-secret plane, static+nginx same-origin serving, digest-pinned GitOps promotion) — the RULING; the operational runbook (one-verb flow, `release.yml` job-by-job, promotion→Argo, backing-stack prerequisites, the six pipeline lessons, demo-vs-release) | ADR-0028 (ruling); 18 (runbook; builds on the ADR-0022 render catalog + dual-mode Vault; home backing stack = `infrastructure/apps/eden/README.md`) |
| Workstreams, interface negotiation protocol, milestones | 09 |
| Evidence interface, Spec envelope, harness senses | upstream spec-driven (cited via 02) |
| Cell parameter vector D1–D5, **cell invariants I1–I10**, topology selector | upstream corpus doc 04 |
| **Build-system invariants I1–I12** | upstream build-system README |
| Pattern catalogue, HNS-1 naming, dev→release→adopt lifecycle, library manifest | 10 |
| Environment ≠ Platform axes (hard rule, detection, default map) | 10 §2 |
| Bender failure modes 1–15 (compact in-repo list) | 03 §1 |
| Document tiers, id/link grammar, envelope, traceability rules T1–T7 | 11 |
| Git process — branch/commit grammar, worktrees, merge conditions, merge agents, attribution | `.claude/rules/git-process.md` (ADR-0032) |
| Agent instrumentation (the role × harness schema, the composition/precedence of rules and skills, per-repository overlays, the deterministic renderer, the digest a rendered profile is addressed by, and the commit-time drift gate) | `contracts/agentprofile.md` **DRAFT** — disambiguates the `agentconfiguration/TemplateStore` ambiguity in `contracts/orchestrator.md` §2; `agentconfiguration` keeps `RouteKey → Route` per 10 §12; the role axis binds to `agentsession.RouteKey.Role`; the naming warrant is `.claude/rules/git-process.md` §12 ("the repository's own `CLAUDE.md` and `.claude/` ARE the CI profile") |
| Fleet telemetry (the message-kind → OTel span/event/link mapping and its attribute vocabulary, task-as-trace, the durable bus consumer, the UI streaming read model) | `contracts/fleettelemetry.md` **DRAFT** — the S6 plane (b) of 03 §1. It does NOT own the wire nor the `Provider` port: it cites `contracts/observability.md` (on `main`) for the port, and `contracts/fleetenvelope.md` + `contracts/fleetbus.md` for the header and the consumer mechanics. ⚠️ **Those two are NOT on `main` yet** — they are DRAFTs on the sibling branch `docs/fleet-contracts` (`70a979f`), so this row's pointer chain is forward-looking until that branch merges. The stated order is `fleetenvelope` → `fleetbus` → `fleettelemetry`. |
| Per-class versioning | **no synthesis home — deliberately dropped (ADR-0032).** Doc 13 §7 was a pointer table, and all four homes it pointed at survive: document envelopes **11 §4**, library semver **10 §8**, platform releases **06 §3**, contract freezes **09 §4**/ADR-0016. Cite those, never a synthesis. |
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
