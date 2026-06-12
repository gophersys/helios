# 06 — Dogfooding & Bootstrap

> Status: Draft · 2026-06-12 · Canonical home for: the L0–L4 ladder, migration/update model,
> self-hosting invariants. Decision basis: ADR-0007 (kernel-first).
> The mandate (T5/P11/E5): Eden must reach the point where it develops itself — version N builds,
> deploys, and migrates to version N+1. Self-hosting is the complexity proof and the forcing
> function for migration, updates, and observability being real.

## 1. Why kernel-first

The system cannot build itself from zero — a strong model cannot author the harness that runs it
(spec-driven §8's premise, accepted here 🔶). A minimal kernel is hand-built (human + Claude,
conversationally — exactly how this document set is being produced), then every subsequent rung
is built *by* the rung below it. The alternative ("build the platform conventionally, dogfood later") produces a platform whose
central claim was never exercised during its own construction — rejected (ADR-0007).

## 2. The ladder

| Rung | What is built | Built by | Exit criteria (the proof) |
|---|---|---|---|
| **L0 — Kernel** | `agentconfiguration` · `evidence` (+GoTestEvidence) · `testharness` (clean temp env + go test) · `codingharness` (Claude Code connector, ADR-0008) · `specification`/`template` · linear `engine`; plus the universal Go pattern libraries (configuration, dependencies, errors, observability, secrets, testing) | humans + Claude Code directly (worktrees, TDD, interface negotiation — 09) | kernel closes the loop on one task: spec in → gated, evidence-passing Go package out, with tokens metered and variance/mutation instrumented from run 1 |
| **L1 — Kernel builds libraries** | the remaining Go pattern/control-plane libraries, ~50 tasks through the `go-backend` cell (build-system invariant I11). The task inventory is drawn from real WS1/WS3 packages (09 §2), not synthetic exercises | the L0 kernel | ≥50 tasks gated on a non-gameable oracle; spec-determinacy + mutation-score dashboards live; libraries enter `main` only via dev→release→adopt |
| **L2 — Kernel builds the platform** | control plane slices (S1–S3, S5, S6, S9), workspace service, connector framework, Svelte frontend walking skeleton | the kernel, fanned as swarms; humans at `approve` gates | Eden runs via `eden up` (on a local k3d/kind cluster — local-as-a-cluster, ADR-0012); the eden monorepo is registered as **project #1**; drift detection live on Eden's own mirrors and infrastructure |
| **L3 — Eden maintains Eden** | nothing new — the proof rung: feature work on Eden flows through Eden's own process engine; version N builds N+1, deploys it, migrates project #1 onto it | Eden (N) | one full self-migration N→N+1 with rollback rehearsed; postmortem artifacts produced by the platform about itself |
| **L4 — Generalization** | second cell (`svelte-ui`) through the full pipeline; archetype registry + graft; the wizard; first external-style project end-to-end | Eden | a project that is not Eden goes wizard→deployed→observed with no out-of-band human work |

```mermaid
%% D2: Bootstrap ladder L0–L4 — v0 hand-authored projection of this document (12 §3); to be generated from model data.
stateDiagram-v2
  direction TB
  [*] --> L0
  L0: L0 Kernel (humans + Claude build it)
  L1: L1 Kernel builds libraries
  L2: L2 Kernel builds the platform
  L3: L3 Eden maintains Eden
  L4: L4 Generalization

  L0 --> L1: loop closed on one task (spec in, gated Go pkg out; tokens + mutation metered)
  L1 --> L2: >=50 tasks gated on non-gameable oracle; dashboards live; dev->release->adopt
  L2 --> L3: eden up runs; eden repo = project #1; drift detection live
  L3 --> L4: one self-migration N to N+1, rollback rehearsed
  L4 --> [*]: non-Eden project goes wizard to deployed to observed, no out-of-band work

  note right of L0
    Built by: humans + Claude Code directly
    B2 hand-built exemption
  end note
  note right of L1
    Built by: the L0 kernel
  end note
  note right of L2
    Built by: kernel, fanned as swarms;
    humans at approve gates
  end note
```

Scope guard: no engine DAG, no recursion/altitudes, no additional cells before L1's 50 tasks
close (build-system invariant I11). The ladder is sequenced proof, not a roadmap of parallel
ambitions — parallel *workstreams within a rung* are how idle time is avoided (09). The S6
observability stack (whose composition is OD-11) must be minimally live by L1's exit — the
kernel's own instrument dashboards are its first customer.

## 3. Migration & update model (opinionated)

- **Platform versioning.** Eden releases are versioned as one unit (apps + archetype registry +
  stage schemas + library floor set). Projects **pin** an Eden version; nothing upgrades silently.
- **Migration pipelines.** An upgrade is a pipeline fanned over a project: schema migrations for
  phase artifacts, library version bumps through the adopt machinery, archetype regeneration
  diffs, infrastructure rollout per substrate. Each step emits Evidence; the upgrade is gated like
  any other change. This is the LSC mechanism (04 §2) — and platform development uses the same
  machinery on project #1 first (canary = ourselves).
- **Compatibility windows.** N+1 must migrate projects from N (contract-tested); skipping versions
  composes migrations. Breaking a published contract without a migration is the cardinal sin
  (10 §9) — `buf breaking` literally stops the platform from amputating itself.
- **Rollback posture.** Deliver-phase reversibility (D4) is preserved by migration steps being
  individually reversible or checkpointed; release never outruns detection (Bender mode 9) —
  observability SLOs gate rollout progression. Rollback is deterministic machinery (P8).

## 4. Self-hosting invariants

| ID | Invariant |
|---|---|
| B1 | Eden's own monorepo is permanently project #1; platform capabilities ship only after being exercised on it (E5). |
| B2 | Every rung's output is the next rung's tooling — no rung builds with tools the previous rung didn't produce (except L0's hand-built exemption). |
| B3 | Self-migration N→N+1 is a release-blocking test from L3 onward. |
| B4 | The kernel's instruments (token ledger, spec-determinacy, mutation score) are never disabled on platform work — Eden's own development data trains the cost models (T6). |
