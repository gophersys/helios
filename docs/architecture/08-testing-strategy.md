# 08 — Testing Strategy

> Status: Draft · 2026-06-13 · Canonical home for: the three test layers, conformance suites,
> evidence-quality instruments, agent evals, scale strategy.
> The stance: testing is how Eden converts agent output into trustworthy systems — so the test
> system is itself a product subsystem, with capacity planning and quality instruments, not a
> convention (Bender mode 5: test-compute grows quadratically; plan for it now).
> **Amended (ADR-0020):** the per-library realization of §1's platform-test row and §2's
> conformance two-binding is the four-phase pipeline + 8-dimension test taxonomy in
> [14-library-engineering-pipeline.md](14-library-engineering-pipeline.md). The conformance suite
> now runs over **four bindings** — fake + REAL docker + k3d + kind — and the mutation/coverage
> instruments of §3 are wired as the `mutate`/`cover-floor` gates. Cite 14/ADR-0020 for the
> library mechanism; this doc owns the cross-layer strategy.

## 1. Three layers

| Layer | Tests what | Owned by |
|---|---|---|
| **Platform tests** | Eden itself: unit/integration per slice; **adapter conformance suites** per connector family; engine golden-path tests; self-migration tests (B3) | S-teams / kernel |
| **Generated-system tests** | every user project: tests are a *phase artifact* — contract tests authored from ServiceContracts before implementation; implementation decompresses against them (typed holes); held-out verify suites where the cell affords them | the process engine, per Spec |
| **Agent-quality evals** | the agents/knowledge themselves: golden-path evals per phase (given this requirements artifact, does the architecture agent emit a valid, sensible ServiceContract?); knowledge-rule uplift measurement; run on every prompt/template/rule change | knowledge pipeline (✅ harness exists: `poc/knowledge`) |

## 2. Conformance suites (the adapter scaling mechanism)

Each connector family's contract ships an executable conformance suite (05 §6); each pattern
library ships a **fake for every port plus a suite proving adapter ≡ fake substitutability**
(10 §4 `testing` pattern). Consequence: unit tests against fakes are trustworthy,
because substitutability is itself tested — the standard mocking failure mode (fakes drifting
from reality) is closed mechanically once the suite exists 🔶.

> Realized (ADR-0020): the substitutability suite runs over **four bindings** — the fake AND the
> REAL docker + k3d + kind substrates — executed, not asserted (doc 14 §2 dimension a/d). A
> binding may Skip on a declared-absent capability but is never silently omitted; in CI (the
> devcontainer) all substrates are present, so a real-substrate binding is REQUIRED. This is the
> dimension-(a)/(d) row of the 8-dimension taxonomy.

## 3. Evidence-quality instruments (is the gate blind?)

Gates are only as good as their evidence. Two instruments, read jointly (spec-driven §6 ✅),
instrumented from kernel run 1 (B4):

| variance (spec-determinacy) | mutation score | reading |
|---|---|---|
| low | high | spec genuinely tight ✅ |
| low | **low** | **gate is blind** — tests can't tell ❌ |
| high | high | loose spec or model noise |
| high | low | both broken |

- **Spec-determinacy** = variance across N runs of a frozen (spec, model, harness) triple —
  the de-circularized spec-quality metric. Confound: sampling noise; pin temperature/seed where
  the connector allows.
- **Mutation score** = test power; cheap in the go-backend cell (in-process, ms tests). A
  required-evidence gate without test-power where feasible is a "blind gate" (cell invariant
  I10, corpus doc 04).

## 4. Temptation-task evals & the knowledge pipeline

✅ `poc/knowledge` validated the method: atomic rules with checkability classes (C1 decidable /
C2 property / C3 judgment), temptation tasks where the violation is the lazy path, held-out rule
splits, N≥3 seeds, prior-delta filtering (a rule the bare model already follows is dead weight).
Promotion path: PoC harness → the standing agent-quality eval layer; rules ship only with
measured uplift and their oracle (P7). The post-cutoff seam (recent Go APIs the models cannot
know) is the highest-uplift knowledge per token (✅ all four post-cutoff rules in the PoC
confirmed at 100% baseline violation — `poc/knowledge/results/report.md`).

## 5. Scale strategy (designed now, activated later — D5)

- **Conjunction-of-Booleans:** at 10× velocity "all tests must pass" stops scaling; the gate
  model already supports statistical evidence kinds (sampled, flaky(p), measured(±)) so the move
  to statistical validation is a policy change, not a remodel. 🔶
- **Test-impact selection** (run what the change can affect) and test-capacity metering ride the
  CI engine's content-aware caching; deferred until L2+. To keep the retrofit possible, the Run
  record schema carries changed paths, artifact digests, evidence references, and test-execution
  identities from run 1 🔶.
- **Fidelity ladder:** unit → integration (compose/kind) → staging → production observation;
  evidence records its rung; gates demand the rung the change class requires.

## 6. What is deliberately not tested by agents

Deterministic machinery guards itself: schema validation, gate evaluation, drift remediation,
budget enforcement, and the vault are covered by conventional, human-reviewed tests at platform
layer — the enforcement spine must not depend on the thing it polices (P8).
