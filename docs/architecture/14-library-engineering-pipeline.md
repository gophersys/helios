# 14 — Library Engineering Pipeline & Test Taxonomy

> Status: Draft · 2026-06-13 · Canonical home for: the four-phase library SDLC (architecture →
> implementation → testing → qa), the per-phase inputs/artifacts/gates, and the eight-dimension
> test taxonomy with its verb + CI lane + threshold per dimension. Decision basis: ADR-0020.
> Mechanisms are owned elsewhere and cited, never redefined: the enforcement toolchain
> (golangci/hnslint/hooks/plugin) → ADR-0018; the contract freeze → ADR-0016; the quality bar and
> review lanes → ADR-0017; HNS-1 naming + library lifecycle → 10 §5/§8; conformance two-binding →
> 08 §2; gate policy → 04 §5.
> Epistemic legend (✅🔶⚠️🧩) per the architecture README §3.

## 1. The four phases (the SDLC sequence) ✅

A library moves through four **phases** — distinct from a **stage** (the environment axis,
development/test/staging/production, 10 §2). Each phase has required INPUTS, produced ARTIFACTS,
and a MECHANICAL GATE that must pass before the next phase. The gate is one per-lib verb,
`bash ./ctl.sh phase-gate <phase>`, delegating to the shared `libs/go/_ctl/lib.sh`, re-run
identically in CI. `phase-gate all` runs 1→4, short-circuiting on the first failure, and is what
`nx run <lib>:phase-gate` and `.ci/ctl.sh lib-gate <lib>` invoke.

### Phase 1 — Architecture (frozen contract + cohesion)

|                                    |                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Inputs**                         | the reconciler-frozen contract `docs/architecture/contracts/<lib>.md` (ADR-0016 freeze); the 10 §9 interface/error/naming rules (`libs/.claude/rules/*.md`); Eden invariants E1–E7.                                                                                                                                                                                                                                                               |
| **Artifacts**                      | (a) the frozen contract file with a `Status: Frozen` header; (b) the exported-surface skeleton — types + the `New(configuration, dependencies) (Component, error)` spine + the ≤5-method ports, compiling, no bodies; (c) the conformance-suite signature `<lib>test.ProviderSuite()` declared (cases may be TODO); (d) the cohesion declaration (one concept, one home).                                                                         |
| **Gate `phase-gate architecture`** | contract file exists with a `Status: Frozen` header (a "not frozen" draft is rejected); skeleton compiles (`go build ./...`); `interfacebloat`(≤5) + `ireturn` + `forbidigo` + `hnslint` pass; an **apidiff baseline is recorded** at `<lib>/.apibaseline`. BLOCKING. The architecture cannot change after this gate except via a contract revision (ADR-0016 §1) + re-recording `.apibaseline` — the baseline is what makes "frozen" mechanical. |

### Phase 2 — Implementation (TDD under the gate)

|                                      |                                                                                                                                                                                                                                     |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Inputs**                           | the frozen skeleton + `.apibaseline`; the conformance-suite signature.                                                                                                                                                              |
| **Artifacts**                        | the fake binding (in-memory adapter) implemented FIRST + the conformance cases written before bodies (red); then the library bodies (green); the PostToolUse inner loop keeps every edit conformant.                                |
| **Gate `phase-gate implementation`** | `go build ./...` clean; full golangci set clean; hnslint clean; **apidiff shows NO break vs `.apibaseline`** (a break aborts — the cardinal sin, 10 §9); `go vet`; the fake conformance suite is GREEN (`go test -race`). BLOCKING. |

### Phase 3 — Testing (the eight dimensions)

|                               |                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Inputs**                    | green fake + bodies.                                                                                                                                                                                                                                                                                                                                                 |
| **Artifacts**                 | the eight test dimensions (§2) wired, each behind its taxonomy mechanism.                                                                                                                                                                                                                                                                                            |
| **Gate `phase-gate testing`** | runs `test`, `property`, `leak`, `lifecycle`, `load`, `integration` (REAL docker+k3d+kind in the devcontainer), `bench-guard`, `vuln`, `sast`, `secretscan`, `cover-floor`; per-package coverage floor met; race-clean under load; ZERO leaks. BLOCKING. In the devcontainer all tools are present, so an absent tool is a GATE FAILURE, not a skip (fail-not-skip). |

### Phase 4 — Quality assurance (cross-cutting + adversarial review)

|                          |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Inputs**               | a library passing phases 1–3.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Artifacts**            | the cross-cutting evidence bundle (coverage/leak/vuln/sast/bench-baseline/`.apibaseline`); the ADR-0017 adversarial-review outcome (cohesion / true-coverage / adversarial-correctness — no stub-as-implementation, no swallowed error, no mock-only coverage of a real-substrate feature).                                                                                                                                                                                                                  |
| **Gate `phase-gate qa`** | maintainability green (strict golangci + hnslint + interface-size + cyclomatic + doc-comment coverage + cohesion "one concept, one home" scan); mutation score ≥ floor on leaf libs (`gremlins`); the ADR-0017 no-shortcuts grep (no `TODO`/`panic("unimplemented")`/`return nil, nil` in non-test bodies on load paths); the evidence bundle present. BLOCKING — a library is "done" only past `phase-gate qa`. This is the gate the agent's **Stop hook** verifies so the agent cannot declare done early. |

## 2. The eight test dimensions ✅

Each dimension: WHAT IT ASSERTS · GO/TOOLING MECHANISM · GATE (verb + CI lane) · THRESHOLD. The
concrete Go templates are in `libs/.claude/rules/21-test-taxonomy.md`. New verbs extend the
existing build/test/integration/lint/vet/fmt/cover set; every tool is present in the devcontainer
so absence == FAIL.

| #     | Dimension                     | Asserts                                                                                                      | Mechanism                                                                                                                                                                                                                                                                  | Verb · CI lane                                                                                   | Threshold                                                                                                                                           |
| ----- | ----------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **a** | Application-logic correctness | every contract behavior holds; fake ≡ real substitutability is EXECUTED (the conformance two-binding, 08 §2) | testpackage black-box `_test.go`; the `edentesting.Suite[S]`/`RunSuite` engine over fake + real; property tests via `pgregory.net/rapid` (test-only dep, GOWORK-isolated)                                                                                                  | `test`, `property` · unit (every push)                                                           | 100% conformance cases Pass-or-Skip (Skip only on a declared-absent capability, never silent); rapid 1000 iters/property, 0 falsifications          |
| **b** | Resource utilization          | no goroutine/fd/connection leak across construct→use→teardown; hot constructors within an alloc budget       | `go.uber.org/goleak` `VerifyTestMain(m)` per package (benign docker-SDK/k3d roots listed) + `defer goleak.VerifyNone(t)`; `AllocsPerRun`/`-benchmem` ceilings on the `New` spine                                                                                           | `leak` · leak (every push)                                                                       | ZERO leaked goroutines/fds; allocs within the per-path budget                                                                                       |
| **c** | Full object lifecycle         | idempotent Close/Teardown; no orphan resources; the New→use→reap contract per handle                         | `testing.AssertLifecycle(ctx, h, report, factory)` + the `LifecycleProbe` port (`Use`/`Close`/`CountOwned`, ≤5 methods) generalised from the workspaceprovider reap pattern; goleak for the orphan-goroutine half                                                          | `lifecycle` · leak (co-located)                                                                  | double-close idempotent; `CountOwned()==0` post-teardown on every binding; 0 orphans on the real substrate                                          |
| **d** | Host-leveraging integration   | the contract holds against REAL substrates, not mocks (ADR-0016 §2)                                          | the `//go:build integration` lane — the ProviderSuite over a real daemon via `workspaceprovidertest.EphemeralContainer`/`ephemeralCluster` (k3d default, kind second); every resource reaped on `t.Cleanup` under a unique label namespace; isolated kubeconfig; leak-free | `integration` · integration (every push, in `ghcr.io/gophersys/base` with the docker host + k3d) | real-substrate conformance Green on docker+k3d+kind; `CountOwned==0`; goleak clean post-suite                                                       |
| **e** | Load / scale                  | not pathological under fan-out; race-clean under concurrency; per-session fan-out scales (REQ-0022)          | the `//go:build load` lane spinning N concurrent fan-outs (default 500 in-process / 50 real-pod) under `-race`; bounded with `t.Context()` + `errgroup`; reaped on cleanup; goroutine high-water back to baseline (goleak)                                                 | `load` · load (every push in-process; nightly real-pod)                                          | 0 races; all N reaped; goroutine high-water within the ceiling; no deadlock within the deadline                                                     |
| **f** | Security / vulnerabilities    | no known-vulnerable dependency; no SAST finding; no leaked secret; credentials never leak                    | `govulncheck ./...`; `gosec` (also in golangci); `gitleaks` over the tree + the SeededCanary redaction-property test (the needle appears in NO Spec/Handle/Status/log/error); `go mod verify` + depguard import bounds                                                     | `vuln`, `sast`, `secretscan` · security (every push)                                             | govulncheck 0 applicable vulns; gosec 0 high/medium; gitleaks 0 findings; canary 0× in any artifact                                                 |
| **g** | Performance                   | hot paths do not regress beyond a threshold vs a recorded baseline                                           | `go test -bench -benchmem -count=10` on the hot paths; baseline at `<lib>/.benchbaseline/`; `benchstat` HEAD vs baseline                                                                                                                                                   | `bench`, `bench-guard` · performance (every push for guard)                                      | no hot-path benchmark regresses > +10% time or allocs at p<0.05; a deliberate regression re-baselines in the same PR                                |
| **h** | Maintainability               | the code stays inspectable and cohesive (one concept, one home)                                              | the strict golangci set (interfacebloat≤5, ireturn, cyclop 15/avg 10, gocognit 20, revive exported-doc, depguard) + hnslint + a doc-coverage check + a cohesion scan (a public type defined in >1 package) + `gremlins` mutation                                           | `maintainability`, `mutate`, `cover-floor` · maintainability (every push)                        | golangci 0 issues; hnslint clean; exported-doc 100% (revive); cohesion 0 duplicate defs; gremlins ≥ 0.75 on leaf libs; per-package coverage ≥ floor |

## 3. Enforcement & blocking policy ✅

Every dimension is (1) a per-lib `ctl.sh` verb, (2) an Nx target in `project.json`, (3) a
`.githooks` gate (the lighter ones), (4) a CI lane in the devcontainer. Defense-in-depth is
preserved: client hooks are advisory-degradable LOCALLY (loud WARN if a tool is missing, the
ADR-0018 stance) but the CI lane is AUTHORITATIVE and runs in the devcontainer where every tool is
guaranteed present — there an absent tool is a HARD FAIL (`require_cmd` → exit 127).

- **Coverage** is a per-PACKAGE FLOOR (not a target; ADR-0018), read from each lib's `ctl.sh`
  metadata: default **80%** leaf, **70%** substrate adapters (their real behavior is proven by
  integration, not line count). A `<lib>test` conformance-helper package is reported, not gated.
- **BLOCKING every push (fail closed):** unit+conformance, fake substitutability, leak, lifecycle,
  integration(docker+k3d), security(vuln/sast/secretscan/canary), maintainability, apidiff-no-break,
  cover-floor, bench-guard.
- **Advisory locally / blocking in CI:** integration when a local substrate is absent (Skips
  locally, REQUIRED in CI); gremlins mutation (advisory until baselined per lib, then blocking);
  real-pod load N (advisory in PR, blocking nightly).
- **Nothing silently skips in CI:** the devcontainer guarantees presence, `require_cmd` turns
  absence into exit 127, and the `phase-gate` verb prints a per-dimension PASS / FAIL /
  REQUIRED-BUT-ABSENT summary so a blind gate is visible.

## 4. AI instrumentation ✅

The `project-go` plugin + `libs/.claude/rules` drive Claude Code through all four phases;
the root `AGENTS.md` and `CLAUDE.md` route both harnesses to the shared engineering system
every session, so a phase cannot be skipped:

- Rule files `20-library-pipeline.md` (the four-phase hard sequence + no-shortcuts + real-substrate
  rules) and `21-test-taxonomy.md` (the per-dimension Go templates) are injected at SessionStart.
- `session-start.sh` is phase-aware: it probes which gates pass for the active lib and injects
  "you are at phase N; the next gate is X" (a pure read-only probe).
- `post-edit-lint.sh` adds TDD-order and four-binding reminders (advisory).
- `pre-git-gate.sh` extends the git block with leak/vuln/secretscan/cover-floor/apidiff for the
  touched libs, so a commit/push is denied unless the full taxonomy passes.
- A NEW **Stop hook** `stop-phase-check.sh` blocks the agent from ending its turn while a fast
  `phase-gate qa` subset is red for a touched lib — the mechanical guarantee that the agent carries
  a library to completion.
