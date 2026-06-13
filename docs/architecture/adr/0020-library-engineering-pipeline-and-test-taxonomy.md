# ADR-0020: Library engineering pipeline + 8-dimension test taxonomy

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Mateo

## Context

ADR-0018 built the deterministic enforcement *toolchain* (the shared `libs/.golangci.yml`,
`tools/hnslint`, the `.githooks`, the `project-go` plugin) and ADR-0017 added the post-wave
adversarial *review*. What was still missing is the **process** that sequences a library from a
frozen contract to "done" and the **test taxonomy** that defines what "tested" means for a Go
library that leverages a real orchestration host. Without a mechanical pipeline, "done" is a
judgment call an agent can declare prematurely, and "tested" collapses to "unit tests pass" —
the blind-gate failure mode (08 §3).

The devcontainer (`ghcr.io/gophersys/base`) is both the dev substrate and the CI runtime, and it
carries a live docker host plus k3s/k3d/kind. That makes REAL orchestration/integration/load
tests runnable in the same image a CI pod uses — so the taxonomy can demand real substrates, not
mocks (ADR-0016 §2: "mocks are not acceptable substitutes"), and an absent tool can be a hard
failure rather than a silent skip.

This ADR is the build spec for that pipeline + taxonomy. It **extends** ADR-0016 (contract
freeze), ADR-0017 (quality bar / review lanes), and ADR-0018 (the enforcement toolchain); it does
not replace any of them.

## Decision

### A four-phase library SDLC, each with a mechanical gate

A library is built in four **phases** — **architecture → implementation → testing → qa** — in
order. Each phase has a mechanical gate, a new per-lib `ctl.sh` verb
`bash ./ctl.sh phase-gate <phase>`, that MUST pass before the next phase begins; `phase-gate all`
runs 1→4 short-circuiting on the first failure. ("phase" is the SDLC step, kept strictly distinct
from "stage" = the environment axis — the verb takes a *phase* token.)

1. **Architecture** — frozen contract (`Status: Frozen` header, ADR-0016) + the exported-surface
   skeleton compiling (the `New(configuration, dependencies)` spine + ≤5-method ports, no bodies)
   + the conformance-suite signature declared + the cohesion declaration (one concept, one home).
   The gate records an **apidiff baseline** at `<lib>/.apibaseline` — the freeze made mechanical.
   The architecture cannot change after this gate except via a contract revision (ADR-0016 §1).
2. **Implementation** — TDD under the gate: the fake binding + conformance cases written FIRST
   (red), then the bodies (green). The gate is build + full golangci + hnslint + **apidiff shows
   no break vs `.apibaseline`** (a break aborts — the cardinal sin, 10 §9) + `go vet` + the fake
   conformance suite GREEN.
3. **Testing** — the eight dimensions below, each wired to a verb and run by the gate, against the
   REAL docker+k3d+kind substrates in the devcontainer; an absent tool is a gate FAILURE, not a
   skip.
4. **QA** — the cross-cutting evidence bundle + the ADR-0017 no-shortcuts grep + mutation score on
   leaf libs. A library is "done" only past `phase-gate qa`.

### The 8-dimension test taxonomy

Each dimension is a concrete Go mechanism wired to a `ctl.sh` verb, an Nx target, a `.githooks`
gate (the lighter ones), and a CI lane, with a pass threshold:

| # | Dimension | Mechanism | Verb | Threshold |
|---|---|---|---|---|
| a | Application-logic correctness | unit + the conformance two-binding (fake ≡ real, executed) + `pgregory.net/rapid` properties | `test`, `property` | 100% conformance cases Pass-or-Skip; rapid 1000 iters/property, 0 falsifications |
| b | Resource utilization | `go.uber.org/goleak` VerifyTestMain + `AllocsPerRun`/`-benchmem` budgets | `leak` | ZERO leaked goroutines/fds; allocs within budget |
| c | Full object lifecycle | `testing.AssertLifecycle` + `LifecycleProbe` (construct→use→double-close→teardown) | `lifecycle` | double-close idempotent; CountOwned()==0; 0 orphans |
| d | Host-leveraging integration | the `//go:build integration` lane over REAL docker + k3d (+ kind) | `integration` | real-substrate conformance Green; CountOwned==0; goleak clean |
| e | Load / scale | the `//go:build load` lane, N concurrent fan-outs under `-race` | `load` | 0 races; all N reaped; goroutine high-water bounded; no deadlock |
| f | Security / vulnerabilities | `govulncheck` + `gosec` + `gitleaks` + the SeededCanary no-leak property | `vuln`, `sast`, `secretscan` | 0 applicable vulns; 0 high/medium SAST; 0 leaks; canary 0× |
| g | Performance | `go test -bench -benchmem -count=10` + `benchstat` HEAD vs `.benchbaseline` | `bench`, `bench-guard` | no hot path regresses > +10% time/allocs at p<0.05 |
| h | Maintainability | strict golangci + hnslint + doc-coverage + cohesion scan + `gremlins` | `maintainability`, `mutate`, `cover-floor` | golangci 0 issues; 100% exported-doc; 0 duplicate defs; mutation ≥ 0.75 on leaf libs; per-package coverage ≥ floor |

### Enforcement wiring (defense in depth, extending ADR-0018)

- The verb bodies live ONCE in `libs/go/_ctl/lib.sh` (HNS-1: `_ctl/lib.sh`, never `common.sh`);
  each per-lib `ctl.sh` is a thin dispatcher that sets metadata (leaf-or-not, coverage floor, hot
  paths, integration substrates) and sources it. Each verb `require_cmd`s its tool — a missing
  tool exits 127 (FAIL-NOT-SKIP).
- Coverage is a per-**package** FLOOR (not a target; ADR-0018): default **80%** leaf, **70%**
  substrate (real behavior proven by integration, not line count). A `<lib>test` helper package is
  reported, not gated.
- `.githooks/pre-push` gains `govulncheck`/leak/cover-floor/apidiff per touched module (the inner
  loop stays fast; integration/load/bench stay in CI + the verb). Client hooks WARN-not-fail
  locally when a tool is absent; the CI lane in the devcontainer is authoritative and fails hard.
- `.ci/ctl.sh` gains `affected-gate` / `lib-gate`; `on-pr.yml` splits into a `fast` job and a
  `substrate` job (real docker+k3d), both inside `ghcr.io/gophersys/base`.
- The base image installs k3d + kind + the pinned Go gate tools so absence is impossible.

### AI instrumentation

Two new rule files (`libs/.claude/rules/20-library-pipeline.md`, `21-test-taxonomy.md`) are
injected at SessionStart; `session-start.sh` becomes phase-aware (probes which gate passes and
tells the agent "you are at phase N, next gate is X"); `post-edit-lint.sh` adds TDD-order and
four-binding reminders; `pre-git-gate.sh` extends the git block with the full taxonomy; and a NEW
**Stop hook** (`stop-phase-check.sh`) blocks the agent from ending its turn while `phase-gate qa`
is red for a touched lib — the mechanical answer to "the agent always carries a library to
completion."

## Consequences

- "Done" becomes mechanical: a library is done iff `phase-gate qa` is green, and the Stop hook
  makes the agent unable to claim otherwise. "Tested" becomes the eight-dimension taxonomy, not a
  coverage number.
- The cardinal sin (an exported-surface break) is now caught at the implementation gate and on
  push via the `.apibaseline` diff — the freeze is enforced, not honored.
- CI cost: real-pod load-scale (k3d) defaults to **nightly**, advisory-in-PR, to bound cost; the
  in-process load N runs every PR. (Open item: promote real-pod load to every-PR if budget allows
  — registered in open-decisions.)
- 08 (testing) and 10 §9 are amended on next touch to cite this ADR as the realized taxonomy and
  the four-binding conformance rule (08 carries an "amended on next touch" note).
- Alternatives rejected: (1) a single monolithic `test` verb — rejected because it hides which
  dimension failed and cannot be a phase sequence; (2) coverage as the primary signal — rejected
  per ADR-0018 (coverage is necessary, not sufficient; mutation is the test-power signal);
  (3) mocking the substrate to keep CI cheap — rejected per ADR-0016 §2.
