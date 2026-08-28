# Rule — The test loop (no shortcuts, real substrates)

> Injected at SessionStart (ADR-0023). A resource is "done" only when `bash ./ctl.sh phase-gate qa`
> is green. This rule is the app-side instance of the ADR-0020 pipeline + ADR-0017 no-shortcuts bar.

## The phase-gate sequence

Run the gate after each phase; paste its PASS/FAIL summary so the state is auditable:

```bash
bash ./ctl.sh phase-gate architecture     # contract present + skeleton compiles
bash ./ctl.sh phase-gate implementation   # build + vet + lint + fake conformance GREEN
bash ./ctl.sh phase-gate testing          # unit + REAL-substrate integration + cover
bash ./ctl.sh phase-gate qa               # vuln + sast + secretscan + maintainability + no-shortcuts
bash ./ctl.sh phase-gate all              # 1→4, short-circuiting
```

## What to test per stage

- **validate.go** — pure: table-test malformed inputs → the right `errors.Kind`. The cheapest, most
  valuable tests; cover every rejection branch.
- **execute.go** — the business step: test against a FAKE Querier for logic, then against the REAL
  postgres in the integration lane. A feature that touches persistence is proven on the real
  database, never only a mock (ADR-0016 §2).
- **route.go** — wire a request through the assembled handler behind the spine Middleware: assert
  authn (401 without a token), authz (403 without the `Required` grant), and the happy path (200 +
  the Envelope). The emitted client (`clients/go`) drives this in the integration lane.
- **effect.go** — assert the after-respond Action emits its audit Event and that its error never
  reaches the client.

## No shortcuts (the qa gate FAILS on any)

- No `panic("unimplemented")`, no `return nil, nil` standing in for real logic on a load path.
- No swallowed error — every returned error is checked/wrapped (the errors contract).
- No `TODO`/`FIXME` on a non-test body.
- No mock-only coverage of a real-substrate feature (persistence/deploy → REAL postgres / k3d).

The `// SKELETON:` markers the template ships are the ONLY allowed "fill me in" tells, and they sit
on intent comments, never on a forbidden pattern — replace the stubbed body, keep the marker out of
the finished code.
