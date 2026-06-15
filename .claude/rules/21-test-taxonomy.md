# Rule — Test taxonomy: the Go mechanism per dimension (ADR-0020)

> Write each test dimension the house way, not from scratch. These are the canonical templates
> the `ctl.sh` verbs (`property`, `leak`, `lifecycle`, `load`, `vuln`, `sast`, `secretscan`,
> `bench`/`bench-guard`, `maintainability`, `mutate`, `cover-floor`) expect. They EXTEND the
> existing conformance two-binding (`<lib>test.ProviderSuite` over fake + real substrate, 08 §2).

## (a) Application-logic correctness — property tests with `pgregory.net/rapid`

A test-only dep (in the lib's go.mod test-require block; depguard's `test-taxonomy` rule allows
it). The `property` verb sets `RAPID_CHECKS=1000` in the environment. Use rapid for invariants:
fingerprint stability, idempotency, error-Kind round-trips.

```go
func TestProperty_KindRoundTrip(t *testing.T) {
    t.Parallel()
    rapid.Check(t, func(rt *rapid.T) {
        k := drawKind(rt)
        got := subject.KindOf(subject.New(k, rapid.String().Draw(rt, "msg")))
        if got != k { rt.Fatalf("round-trip drifted: got %v want %v", got, k) }
    })
}
```

## (b) Resource utilization — `go.uber.org/goleak` in every package's TestMain

Compile `goleak.VerifyTestMain(m)` into a `TestMain` per package, listing ONLY the known-benign
docker-SDK / k3d / runtime roots explicitly. Add `defer goleak.VerifyNone(t)` on lifecycle/load
tests. Allocation budgets ride `testing.AllocsPerRun` / `-benchmem` ceilings on the New spine.

```go
func TestMain(m *testing.M) {
    goleak.VerifyTestMain(m,
        goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
        // real-substrate packages also ignore the docker SDK / k3d background roots — list each.
    )
}
```

## (c) Full object lifecycle — `testing.AssertLifecycle(ctx, h, report, factory)`

Implement the `testing.LifecycleProbe` port (`Use` / `Close` / `CountOwned`, ≤5 methods) for your
handle, then drive it once per binding. `AssertLifecycle` asserts construct → use → first Close →
**second Close is a no-op** (double-close idempotent) → `CountOwned()==0` (no orphans). Pair with
`defer goleak.VerifyNone(t)` for the orphan-goroutine half. Tag the heavy probe `//go:build
lifecycle` so it stays out of the fast unit run.

## (d) Host-leveraging integration — the `//go:build integration` lane, REAL substrate

Run the SAME `<lib>test.ProviderSuite` over a real daemon via
`workspaceprovidertest.EphemeralContainer` / `ephemeralCluster` (k3d default, kind second). Reap
every resource on `t.Cleanup` under a unique label namespace; isolated kubeconfig; leak-free.
Never mock the substrate (ADR-0016 §2). `CountOwned==0` post-suite (no orphan container/cluster).

## (e) Load / scale — the `//go:build load` lane, race-clean fan-out

Spin N concurrent Provision/Run/agentsession fan-outs (the `load` verb sets `EDEN_LOAD_N`, default
500 in-process / 50 real-pod) under `-race`. Bound with `t.Context()` + `errgroup`; reap on
cleanup; assert throughput/latency within a recorded envelope and the goroutine high-water returns
to baseline (`goleak`). 0 races; all N reaped; no deadlock within the context deadline.

## (f) Security — govulncheck + gosec + gitleaks + the SeededCanary

`vuln`/`sast`/`secretscan` verbs run govulncheck, gosec (also in golangci), and gitleaks. The
**canary** half is a redaction-property test: a seeded needle handed to the error/spec model must
appear in NO surfaced artifact (Spec/Handle/Status/log/error). One leak fails the lane.

```go
const seededCanary = "SEEDED-CANARY-...-do-not-leak"
func TestCanary_NeverLeaks(t *testing.T) {
    t.Parallel()
    s := subject.New(...).WithField("secret", struct{ v string }{seededCanary}) // non-scalar → redacted
    if strings.Contains(s.Error(), seededCanary) { t.Fatalf("canary leaked: %q", s.Error()) }
}
```

## (g) Performance — benchstat baseline workflow

Benchmark the hot paths (`New` spine, fingerprint hash, Provision, event fan-out) with
`b.ReportAllocs()` + `b.Loop()`. Use a package-level `any` sink so the compiler cannot elide the
work (`var sink any` — keep it OFF the errname sentinel path). Record the baseline with
`ctl.sh bench-record` (a reviewed commit to `.benchbaseline/`); `bench-guard` fails if a hot path
regresses > +10% time or allocs at benchstat p<0.05. A deliberate regression re-baselines in the
same PR.

## (h) Maintainability — strict lint + hnslint + cohesion + mutation

`maintainability` runs the full strict golangci set (interfacebloat≤5, ireturn, cyclop/gocognit,
revive exported-doc, depguard) + hnslint (structural HNS-1) + the doc-coverage report + the
cohesion scan (no contract type defined in >1 public package). `mutate` runs gremlins on leaf libs
(efficacy ≥ 75%): a survived (LIVED) mutant on covered code is a real test gap — strengthen the
test to kill it (an equivalent mutant on a perf-only hint is the floor's headroom).

### Two cross-lib duplication detectors (one concept, one home — 10 §9)

The single-lib cohesion scan only sees duplicate TYPE declarations within one lib. The
`maintainability` verb additionally runs two **tree-scoped** detectors (in `libs/go/_ctl/lib.sh`:
`_xlib_duplicate_wrapper_scan`, `_xlib_wire_literal_scan`) that catch the duplication a per-lib
scan is blind to. Both FAIL the gate; the fix is to CITE the one home, never to re-spell it.

- **Duplicate-wrapper.** The typed-inspect boolean lives ONCE as `errors.IsType[E](err)`
  (`_, ok := errors.AsType[E](err); return ok`, in `libs/go/errors`). No other lib may define a
  local boolean wrapper that re-derives it — a `func …[E error](err error) bool` (named
  `is`/`isType`/`asType`) whose body is the value-DISCARDING `_, ok := errors.AsType[…]` form. The
  detector flags any `_, ok := errors.AsType[…]` outside `libs/go/errors` — in production, in a
  shipped `<lib>test` helper, OR in `*_test.go` (**the reinforcement is not skipped for test code**:
  a test re-spelling the boolean must cite it too). **Cite `errors.IsType`**; do not copy the
  three-line helper. (A legitimate inline use BINDS the typed value — `if authErr, ok :=
  errors.AsType[T](err); ok` — and is NOT flagged: the blank value position `_,` is the wrapper tell.)
- **Wire-literal.** A wire contract shared by a producer and a consumer lib — the JetStream stream
  name (`EDEN_AGENT_EVENTS`) and the agent subject formats (`agent.<id>.events|control|health` and
  the `agent.*.<…>` wildcards) — lives ONCE in the protocol owner `agentruntime` (`EventsStreamName`,
  `EventsSubject`/`ControlSubject`/`HealthSubject`) and is CITED by both natsbus (producer) and
  natssse (consumer). The detector FAILS if any such protocol literal appears in a string in more
  than one top-level lib's PRODUCTION code (`*_test.go` excluded — a black-box test MAY pin an
  expected wire value as a literal assertion, which is how a drift is caught). **Import
  `agentruntime` and cite the const/subject helper**; never re-spell the literal.

### Three half-wired-contract detectors (Stage-6 ENFORCE — the meta-loop teeth)

The classes below are the ones EVERY prior layer was blind to: an EXPORTED struct field or an enum
constant is invisible to `unused`/staticcheck (the symbol is exported), counts as "covered" the
moment it is merely ASSIGNED (cover-floor measures lines executed, not values READ), and survives
mutation silently on a `leaf=false` lib (gremlins is off). The `maintainability` verb runs three
detectors (in `libs/go/_ctl/lib.sh`: `_state_consumed_scan`, `_enum_liveness_scan`,
`_fault_path_unit_warn`). The first two FAIL the gate; the third is a WARNING (see below). All three
honor an explicit **`//eden:reserved`** doc tag on the declaration as an opt-out for a member
deliberately reserved in a closed, append-only taxonomy (10 §9) — the escape is documented, not silent.

- **CONFIG-DEAD-STATE** (`_state_consumed_scan`, FAIL). Every exported field of a contract VALUE
  struct (`type Config struct` / `type Actual struct`) MUST be READ by non-test production code in
  the lib. "Read" = a SELECTOR access `.<Field>` (e.g. `p.configuration.ProvisionTimeout`,
  `actual.SessionState`, `configuration.Region`) that is NOT a write (`.<Field> =`) and not a
  comment — exactly the consume signal the audit named (orchestrator `Config.ProvisionTimeout` /
  `RetentionWindow` were resolved knobs the spine never read; `Actual.SessionState` was populated by
  every Probe but branched on by no decision). A field with zero selector reads is a knob that does
  nothing → FAIL. **Fix:** wire the field into a decision/return, DELETE it, or tag the declaration
  `//eden:reserved`. (A `Field: configuration.Field` line is both a struct-KEY write AND a selector
  READ of the value — it counts as a read; do not exclude it.)
- **CAPABILITY-WIRED** (`_enum_liveness_scan`, FAIL). An enum TYPE whose doc declares it a **closed,
  EMITTED** taxonomy (the doc contains "Closed taxonomy" AND an emission word
  `emitted`/`on the wire`/`heartbeat`/`publish` — e.g. agentruntime `HealthPhase`) advertises exactly
  the set of states an observer may see. Every non-zero const member MUST appear in a LIVE position
  in non-test production code: a CALL ARGUMENT (`publishHealth(ctx, PhaseStarting)` — the PRODUCE
  side), an ASSIGNMENT RHS to a published variable (`phase = PhaseDraining`), OR a SWITCH ARM
  `case <Member>:` (the CONSUME side — a received-and-dispatched verb like `ControlVerb.VerbPrompt`
  is wired by its handler, not by an emit). A member in NONE of those positions is a half-wired state
  that advertises a transition that never happens (`PhaseStarting` was never published, the
  `PhaseDraining` beat was unreachable) → FAIL. **Fix:** emit/dispatch the member on the path it
  advertises, drop it from the emitted set, or tag the declaration `//eden:reserved`. The decl
  `Name <type> = iota`, the token-table key `Name: "tok"`, and the table-INDEX read
  `tokens[Name]` are NOT live positions (they only name the member).
- **FAULT-PATH-COVERAGE** (`_fault_path_unit_warn`, **WARNING — not a hard FAIL**). A package that
  constructs typed errors (`errors.Wrap`/`errors.New`) but whose ONLY `*_test.go` files carry
  `//go:build integration` (no fast unit test in the package) has its fault arms reachable only under
  the integration build tag — and cover-floor for a substrate lib is computed WITH that tag, so the
  happy-path integration lines clear the floor while the error branches stay unexercised at the unit
  level (the natssse class: `forward` decode-fault, `openConsumer` fault, `onFetchGap` transport
  fault). This is a **reported WARNING with a precise per-package message, never a gate FAIL** — the
  build-tag/test-file heuristic is too false-positive-prone to block (a package may legitimately be
  integration-only). It nudges a human to add a fast unit fault arm (table tests over the pure
  branches via the `export_test.go` white-box seam — mock-free, no substrate). The gate stays green.
