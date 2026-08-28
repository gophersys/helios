# Rule — Library engineering pipeline (ADR-0020)

> Enforced mechanically by `bash ./ctl.sh phase-gate <phase>` per lib (the shared verbs in
> `libs/go/_ctl/lib.sh`), re-run identically in CI, and by the project-go Stop hook that blocks
> turn-end while `phase-gate qa` is red. This is the SDLC layer on top of ADR-0018's enforcement.

You implement a library in **four phases**, in order: **architecture → implementation → testing
→ qa**. Each phase has a **mechanical gate** that MUST pass before you proceed to the next:

```
bash ./ctl.sh phase-gate architecture     # frozen contract + cohesion + skeleton + apibaseline
bash ./ctl.sh phase-gate implementation   # build + lint + apidiff-no-break + vet + fake conformance GREEN
bash ./ctl.sh phase-gate testing          # the 8-dimension taxonomy (see rule 21)
bash ./ctl.sh phase-gate qa               # cross-cutting gates + mutation + no-shortcuts + evidence
bash ./ctl.sh phase-gate all              # 1→4 in order, short-circuiting on first failure
```

Vocabulary: **"phase"** is an SDLC step (architecture/implementation/testing/qa). It is NOT the
environment **"stage"** (development/test/staging/production). The verb takes a *phase* token.

## The hard sequence

- **TDD order is mandatory.** You may NOT write implementation bodies before the conformance
  cases exist and are red. Write the fake binding + the conformance cases FIRST (red), then the
  library bodies (green). The PostToolUse hook warns you when a non-test body is edited while the
  conformance suite is still red — heed it.
- **You may NOT declare a library "done" before `phase-gate qa` is GREEN.** The Stop hook runs a
  fast `phase-gate qa` subset for any library you touched and blocks your turn from ending while
  it is red. A library is "done" only past phase-gate qa.
- **Run the gate after each phase and paste its per-dimension PASS/FAIL summary** so the state is
  auditable. The gate prints `PASS / FAIL / REQUIRED-BUT-ABSENT` per dimension — a blind gate is
  visible, never silent.
- **The architecture is frozen after phase-gate architecture.** It changes only via a contract
  revision (ADR-0016 §1) + re-recording the `.apibaseline`. An exported-surface break vs the
  frozen `.apibaseline` is the **cardinal sin** (10 §9) and aborts the implementation/testing
  gate.

## No shortcuts (ADR-0017)

The qa gate greps your non-test bodies for the canonical shortcut tells and FAILS on any:

- **No stub-as-implementation** — no `panic("unimplemented")`, no `return nil, nil` standing in
  for real logic on a load path.
- **No swallowed error** — every returned error is checked/wrapped/handled (the errors contract;
  golangci errcheck/wrapcheck enforce it).
- **No mock-only coverage of a real-substrate feature** — a feature that touches docker/k3s is
  proven against the REAL substrate, not a mock (next section).
- **No `TODO`/`FIXME` on a load path** — a non-test body must be complete.

## Real substrates, never mocked

The integration and load lanes run against **REAL docker + k3s/k3d (+ kind)** inside this
devcontainer, where all three are live. **Never mock them** — "mocks are not acceptable
substitutes" (ADR-0016 §2). In the devcontainer every gate tool is present, so an absent tool is
a **gate failure (exit 127), not a skip** (FAIL-NOT-SKIP). Locally a substrate may be absent and
the integration lane Skips the binding whose substrate is missing — but it never silently omits a
binding, and CI (the devcontainer) makes it REQUIRED.

## The 8-dimension self-check

Before you call a library done, self-verify every dimension is wired and green (the concrete Go
mechanism for each is in rule 21 — test-taxonomy):

1. **Application-logic correctness** — unit + the conformance two-binding (fake ≡ real, executed).
2. **Resource utilization** — goleak (zero leaked goroutines/fds) + allocation budgets.
3. **Full object lifecycle** — construct→use→double-close→teardown; idempotent Close; 0 orphans.
4. **Host-leveraging integration** — the contract holds on real docker + k3d (+ kind).
5. **Load / scale** — race-clean under fan-out; all N objects reaped; goroutine high-water bounded.
6. **Security** — govulncheck + gosec + gitleaks + the SeededCanary no-leak property, all 0.
7. **Performance** — benchstat HEAD vs `.benchbaseline`; no hot path regresses > +10%.
8. **Maintainability** — strict golangci + hnslint + 100% exported-doc + cohesion (one concept,
   one home) + gremlins mutation ≥ 0.75 on leaf libs.
