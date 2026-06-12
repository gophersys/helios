# 04 — Process Model (the Eden SDLC)

> Status: Draft · 2026-06-12 · Canonical home for: the spine instantiation, phase artifact
> schemas, gate policy, swarm operational semantics, budgets, failure paths.
> Terminology: **phase** = a step of this pipeline; **stage** is reserved for the environment
> axis (P6) and never used for the pipeline.
> Answers "which SDLC do we use": **the universal 10-phase spine (corpus doc 04) instantiated per
> cell, operated with Google-derived engineering practice** — trunk-based development, design-doc
> culture, mandatory review-as-gate, blameless postmortems, SLOs — adapted so that agents do the
> work and humans rule at gates (P13).

## 1. The spine, instantiated

Every cell runs the same ten phases; cells differ only in their parameter vector (D1–D5), their
topology selector (linear-spine vs reconciliation-loop), and the adapters their ports bind
(corpus doc 04 — stress-tested across ~20 categories; standing hypothesis H1′ — that
spine + parameter vector + topology fully capture category variation — per build-system
invariant I8 🔶).

| Phase | Produces | Port | Eden v1 binding (go-backend cell) |
|---|---|---|---|
| 1 Specify | Spec | — | wizard + requirement extraction; human-edited |
| 2 Author | SourceChange | `author` | Claude Code connector (ADR-0008); swarm fan-out |
| 3 Build | Artifact + provenance | `builder` | Go toolchain (1.26 floor, ADR-0003), nx targets |
| 4 Analyze | static Evidence | `static_analyzer` | golangci-lint v2, buf lint/breaking, knowledge checkers |
| 5 Provision | Environment | `environment_provider` | docker-compose / kind via F1 |
| 6 Exercise | dynamic Evidence | `harness` | clean-room test harness (anti-reward-hack, P3) |
| 7 Package | ReleaseCandidate | `packager` | container image, `GOWORK=off`, SBOM |
| 8 Gate | Decision + signature | `gate_policy` + `signer` | evidence-policy evaluation + human policy table (§5) |
| 9 Deliver | DeploymentRecord / Availability | `deployer` | compose up / kustomize apply via F1 |
| 10 Observe | runtime Evidence → feeds 1 | `observer` | OTel planes (S6); drift detection feeds back as DriftEvents |

## 2. Google practice mapping

| Google practice | Eden mechanism |
|---|---|
| Trunk-based development | One `main` per monorepo; agent work on short-lived branches/worktrees merged only through gates; no long-lived release branches in v1 cells (reversible delivery, D4) |
| Design docs | Phase-1 artifacts ARE design docs with schemas; Open-Decisions tables route human rulings (P13) |
| Code review culture (Critique) | Reviewer agents produce rubric-anchored review Evidence; the deterministic gate evaluates the envelope, with a human ruling per the policy table; at org scale a dedicated reviewer port (D5) |
| Readability / style enforcement | Knowledge libraries + compiled checkers (P7); HNS-1 lint; locked archetype dependency sets |
| Postmortems (blameless) | Phase-10 incidents produce Observation artifacts feeding phase 1; transcripts give complete provenance |
| SRE / SLOs | Plane (c) telemetry with SLOs per generated service; error budgets surface in the non-technical view |
| LSCs (large-scale changes) | Platform migrations are pipelines fanned over projects/libraries (06 §3) — the analogue of Google's Rosie: one change distributed across many targets, each individually validated |

## 3. Project-level lifecycle

```
create ──▶ ProjectSpec ──▶ archetype instantiation (create | graft) ──▶ feature loop:
   Intake → Requirements → Domain model → Service contracts → Implementation plan
   → [swarm: per-contract Spec pipelines through the spine] → Review gate → Deliver → Observe ↺
```

Each named step consumes and produces phase artifacts (§4). The feature loop is the spine run at
product altitude; each swarm member runs it at component altitude. Scope guard: recursion beyond
these two altitudes is explicitly deferred (build-system invariant I11).

## 4. Phase artifacts and schemas (E2)

| Artifact | Produced by | Schema discipline |
|---|---|---|
| ProjectSpec | wizard + intake agent | project kind, archetype set, design-system ref, connector bindings, budgets |
| RequirementsArtifact | requirements agent + human edit | EARS-style requirement statements, priorities, acceptance criteria |
| DomainModel | architecture agent | entities, relationships, invariants |
| ServiceContract | architecture agent | proto packages (buf); the frozen seam — interface-negotiation gate before implementation (09 §4) |
| ImplementationPlan | planning agent | work packages with file-lease sets, dependencies, per-package budget estimates |
| SourceChange | implementing agents | branch + diff + provenance (Spec ref, Run ref, transcript ref) |
| Evidence | harnesses (never authors) | the Evidence interface envelope (02 §2) |
| ReleaseCandidate | packager | artifact digests, SBOM, provenance attestation |
| DeploymentRecord / Observation | deployer / observer | versions, environments, SLO snapshots, incidents, drift events |

Schemas are versioned in the eden monorepo next to the engine; validation runs at the phase
boundary **and** in CI (defense in depth). An agent output failing validation triggers bounded
retry-with-diagnostics; budget exhaustion escalates per §6 — invalid artifacts never flow
downstream (P2).

## 5. Gate policy

A Gate evaluates: `Verdict == pass ∧ Confidence > θ ∧ ¬stale ∧ reproducibility acceptable`, plus
**test-power** (mutation score) where the cell affords it — without test-power, "all green" cannot
distinguish correct code from tests that cannot tell (spec-driven §5, ✅).

Human involvement is a per-phase **policy table**, not a habit:

| Policy | Meaning | v1 defaults |
|---|---|---|
| `auto` | promote on evidence alone | Build, Analyze, Exercise, Package |
| `approve` | human ruling required (async, queued) | ServiceContract freeze, production Deliver |
| `edit` | human may amend the artifact before promotion | Requirements, ImplementationPlan |

Defaults tighten or loosen per project and per environment (production stricter). Every `approve`
queue item carries the evidence summary and cost ledger — rulings are minutes, not sessions (P13).

## 6. Budgets, cost, and token predictability (T6)

- **Meter from run 1:** every Run records tokens in/out, cache hits, wall time, retries, and the
  model/harness pair (instrumented in the kernel from v0.1 — the same discipline `poc/agents`'
  token tracker prototyped ✅).
- **Estimate from history:** archetype × stage cost models accumulate; the wizard shows expected
  cost ranges before a run ("a service of this archetype costs ~N tokens to generate") 🔶.
- **Hard ceilings:** TokenBudget per run/phase/project. Exhaustion → cost-aware escalation
  (stronger model per `agentconfiguration` routing) or abort with a resumable checkpoint; never a
  silent stall (P8: budget machinery is deterministic).
- **Routing split:** `think` → strongest model; `default`/`background` → cheap models — the
  strong-model-authors-specs / cheap-model-fills-templates economics 🔶 (spec-driven; unproven,
  instrumented to be tested).

## 7. Swarm semantics

Fan out only over **independent** artifacts (one agent per ServiceContract / component / rule).
Independence is established at planning time via disjoint FileLease sets (02 §2); each member works in
its own git worktree against its own Spec; merges go through gates. Cross-member seams must be
frozen Contracts *before* fan-out (interface negotiation, 09 §4) — members never negotiate with
each other at runtime (that would be an edit war, Bender mode 8).

## 8. Failure paths (first-class)

| Failure | Handling |
|---|---|
| Non-termination | hard iteration + cost budget; escalate to `think`; abort resumable |
| Spec is wrong | Specs are versioned and invalidatable by Evidence; amending tests is a governed act (gate), not an agent convenience |
| Reward hacking | clean-room outer loop (07 §4): the verifier never executes in an environment the author wrote to |
| Validation thrash | bounded retry-with-diagnostics; thrash beyond N → human queue with transcript |
| Cost blowup | cheap×N can exceed one strong pass — escalation policy is cost-aware, comparing ledgers, not fixed |
| Drift mid-run | DriftEvents pause affected pipelines at the next gate; remediation precedes promotion |
