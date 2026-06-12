# 01 — Principles

> Status: Draft · 2026-06-12 · Canonical home for P1–P13. Each principle: statement, implication,
> provenance. These are enforceable commitments, not aspirations — where a principle can be
> mechanically enforced, the enforcing mechanism is named.

| ID | Principle | Implication | Enforced by | Provenance |
|---|---|---|---|---|
| P1 | **Contracts over integrations.** Every external system (cloud, git host, billing, agent harness, observability backend, design system) sits behind an Eden-defined port; adapters satisfy it. | Vendor work is additive; the platform never imports a vendor SDK outside an adapter package. | Import-boundary lint; adapter conformance suites (05 §6). | T1; 10 §1.5 (hexagonal everywhere) |
| P2 | **The SDLC is a typed pipeline.** Phases consume and produce schema-validated artifacts; agents are transforms; the platform type-checks and orchestrates. | "Hard schemas the agents must adhere to" is the architecture, not a feature. Invalid output is rejected and retried under budget, never patched downstream. | Schema validation at every phase boundary (04 §4); CI re-validation. | T2; corpus doc 04 |
| P3 | **Evidence over assertion.** Promotion decisions read evidence envelopes (claim, verdict, confidence, reproducibility, cost, provenance, staleness) produced by harnesses in environments the authoring agent never wrote to. | No reward-hacking surface; agent self-report is advisory only. | Clean-room test harness (07 §4, 08); gate policy (04 §5). | spec-driven §2–§5 |
| P4 | **The discipline layer is the durable asset.** No architectural decision may depend on a benchmark decimal or a specific model; per-model data is configuration. | Model and harness swaps are configuration changes (`agentconfiguration` routing); Eden survives model generations. | `agentconfiguration` IR + routing; build-system invariant I2. | corpus README |
| P5 | **Opinionation is the feature.** One blessed pattern catalogue, one naming standard (HNS-1), one process per cell. Agents generate against the SDK, not the open ecosystem. | Shrinks output space; uniform, reviewable, instrumented-by-default generated systems. | Locked dependency sets per archetype; linters; knowledge libraries (08 §4). | T4; 10 §4–§5 |
| P6 | **Environment ≠ Platform.** Stage (development/test/staging/production) is an enum selecting injected wiring; substrate (docker-compose/kubernetes/bare-host/vm) is a port selecting mechanism. Never conflated — the hard rule, detection, and default map live in 10 §2. | One artifact runs everywhere. | Composition-root-only stage switch; lint. | 10 §2 |
| P7 | **Knowledge ≠ enforcement.** Guides and skills shape agent authoring; deterministic linters, breaking-change gates, and conformance suites enforce. Both, layered; neither alone. | A rule without an oracle is an opinion; every shipped rule carries its checker and proves measured uplift before it earns context tokens. | Knowledge-library pipeline + eval harness (✅ validated in `poc/knowledge`). | 10 §9; docs/research/03 |
| P8 | **No load-bearing token engines.** Critical workflows — rollback, drift remediation, gate evaluation, billing cutoffs — are deterministic code paths that cannot stall on an agent budget. | Agents propose; machinery disposes. The hooks/enforcement spine never routes through an LLM. | Architecture review; the hooks spine carries no model calls. | Bender (corpus doc 01 §11) |
| P9 | **Observable by construction.** Three planes on one OTel stack: (a) Eden's own telemetry, (b) agent telemetry (runs, transcripts, tokens, validation failures), (c) generated-system telemetry — emitted by default because the core libraries instrument themselves. | The non-technical dashboard is a rendering of plane (c), not separate work. Agent transcripts are first-class, queryable objects. | `observability` pattern library; OTel resource stamping (`deployment.environment.name`). | T8; 10 §4 |
| P10 | **Drift is detected, never silently absorbed.** Every connector family declares its ownership domain and runs a reconcile loop comparing observed vs desired; out-of-band changes become DriftEvents with remediation options. | The platform stays truthful about the world; users are surprised by thoroughness, not by breakage. | Connector contract obligation (05 §5); cell invariant I6 (corpus doc 04) generalized. | T7 |
| P11 | **Eden builds Eden.** Every capability must eventually be exercised by the platform on itself; the bootstrap ladder is the standing proof and the migration machinery is how each version delivers the next. | Self-hosting failures are platform bugs of the highest severity. | Ladder exit criteria (06). | T5 |
| P12 | **Full naming, no abbreviations.** `configuration` not `config`, `kubernetes` not `k8s`, `dependencies` not `deps`; `util`/`common`/`core` banned outright. | A slug is a join key; rendered names per ecosystem are pure functions (HNS-1). | Lint hook (forbidden→required table, 10 §5). | 10 §5 |
| P13 | **Humans at gates, not in loops.** Human attention is the scarcest resource in the system (Bender). Eden spends it on up-front specification and discrete gate rulings, never on synchronous supervision. | Gate policy per phase is auto/approve/edit — a policy table, not a habit. The "open decisions → human ruling" pattern is the only blocking human interaction. | Gate policy schema (04 §5); E6. | Bender (corpus doc 01 §15); user mandate |

## Tensions (acknowledged, ruled)

- **P5 opinionation vs user freedom.** Resolution: opinionation governs *how systems are built*
  (libraries, process); user freedom lives in *what is built* and in declared extension points
  (design systems, archetype selection, connector choice). 🧩
- **P8 vs agentic everything.** Resolution: agents author changes to deterministic machinery; the
  machinery itself never awaits a model. 🧩
- **P11 dogfooding vs shipping speed.** Resolution: the ladder (06) makes dogfooding the build
  plan rather than a tax on it — each rung's output is the next rung's tooling. 🔶
