// Tests for package testing — authored FIRST against the frozen contract
// (docs/architecture/contracts/testing.md §2 surface, §4 conformance properties),
// then implemented until green (TDD discipline, ADR-0016).
//
// This file lives in `package testing` (internal/white-box) so it can exercise
// the constructor spine and RunSuite directly with stub subjects, without the
// testingtest fakes (those have their own black-box suite). It uses the stdlib
// `testing` package under the alias `gotest` because the package under test is
// itself named `testing`.
package testing

import (
	"context"
	gotest "testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// ── recordingReport is a Report implementation used to drive cases that need a
// sink, without importing testingtest (which would create an import cycle from
// the white-box test). It records every message and the terminal verb.
type recordingReport struct {
	errorfs []string
	fatalfs []string
	skipfs  []string
}

func (r *recordingReport) Errorf(format string, args ...any) {
	r.errorfs = append(r.errorfs, format)
}
func (r *recordingReport) Fatalf(format string, args ...any) {
	r.fatalfs = append(r.fatalfs, format)
}
func (r *recordingReport) Skipf(format string, args ...any) {
	r.skipfs = append(r.skipfs, format)
}

// seq turns a slice of cases into the iter.Seq the Suite expects.
func seq[S any](cases ...Case[S]) func(yield func(Case[S]) bool) {
	return func(yield func(Case[S]) bool) {
		for _, c := range cases {
			if !yield(c) {
				return
			}
		}
	}
}

func mustRunner(t *gotest.T, cfg Config, deps Deps) *Runner {
	t.Helper()
	r, err := New(cfg, deps)
	if err != nil {
		t.Fatalf("New(%+v, %+v): %v", cfg, deps, err)
	}
	if r == nil {
		t.Fatal("New returned a nil *Runner with nil error")
	}
	return r
}

// ── Surface: the dependencies aliases must be the SAME types, not redefinitions.
// A value of the alias type must satisfy the dependencies-owned interface and
// vice versa (contract §2: "a fake satisfying these satisfies dependencies'").
func TestClockAlias_IsDependenciesClock(t *gotest.T) {
	var c Clock
	var _ dependencies.Clock = c // alias ⇒ assignable both ways at compile time
	var d dependencies.Clock
	var _ Clock = d
}

func TestRandomSourceAlias_IsDependenciesRandomSource(t *gotest.T) {
	var r RandomSource
	var _ dependencies.RandomSource = r
	var d dependencies.RandomSource
	var _ RandomSource = d
}

// ── New is pure and zero values are valid + deterministic (rationale 4) ──────
func TestNew_ZeroValuesValid(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	fakes := r.Fakes()
	if fakes.Clock == nil {
		t.Fatal("Fakes().Clock is nil")
	}
	if fakes.Random == nil {
		t.Fatal("Fakes().Random is nil")
	}
}

// Zero Epoch → the Unix epoch, never time.Now (contract §2 Deps doc).
func TestNew_ZeroEpochIsUnixEpoch(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	now := r.Fakes().Clock.Now()
	if !now.Equal(time.Unix(0, 0).UTC()) {
		t.Fatalf("zero Epoch should anchor at the Unix epoch; got %v", now)
	}
}

// An injected Epoch is honored exactly (the cross-process reproducibility anchor).
func TestNew_InjectedEpochHonored(t *gotest.T) {
	epoch := time.Date(2026, 6, 12, 0, 0, 0, 0, time.UTC)
	r := mustRunner(t, Config{}, Deps{Epoch: epoch})
	if got := r.Fakes().Clock.Now(); !got.Equal(epoch) {
		t.Fatalf("injected Epoch not honored: want %v got %v", epoch, got)
	}
}

// Fakes returns a FRESH bundle each call — independent instances (contract §2:
// "a fresh, deterministic bundle"). Advancing one must not move another.
func TestFakes_FreshEachCall(t *gotest.T) {
	r := mustRunner(t, Config{Seed: 1}, Deps{})
	a := r.Fakes()
	b := r.Fakes()
	// Reading entropy from a must not affect b's stream (independent state).
	pa := make([]byte, 16)
	pb := make([]byte, 16)
	if _, err := a.Random.Read(pa); err != nil {
		t.Fatalf("a.Random.Read: %v", err)
	}
	if _, err := b.Random.Read(pb); err != nil {
		t.Fatalf("b.Random.Read: %v", err)
	}
	// Same seed, same first read ⇒ identical bytes (reproducible & independent).
	for i := range pa {
		if pa[i] != pb[i] {
			t.Fatalf("fresh bundles from same seed diverged at byte %d: %x vs %x", i, pa[i], pb[i])
		}
	}
}

// Same Seed + same first Read sequence ⇒ identical bytes across distinct Runners
// (the frozen determinism invariant, open question 6).
func TestFakes_DeterministicAcrossRunners(t *gotest.T) {
	mk := func() []byte {
		r := mustRunner(t, Config{Seed: 42}, Deps{})
		p := make([]byte, 64)
		if _, err := r.Fakes().Random.Read(p); err != nil {
			t.Fatalf("Read: %v", err)
		}
		return p
	}
	a, b := mk(), mk()
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("same seed produced different bytes at %d across runners", i)
		}
	}
}

// Different seeds ⇒ different streams (the seed must actually feed the PRNG).
func TestFakes_SeedAffectsStream(t *gotest.T) {
	read := func(seed uint64) []byte {
		r := mustRunner(t, Config{Seed: seed}, Deps{})
		p := make([]byte, 64)
		if _, err := r.Fakes().Random.Read(p); err != nil {
			t.Fatalf("Read: %v", err)
		}
		return p
	}
	a := read(1)
	b := read(2)
	same := true
	for i := range a {
		if a[i] != b[i] {
			same = false
			break
		}
	}
	if same {
		t.Fatal("different seeds produced identical streams; seed is not wired into the PRNG")
	}
}

// ── RunSuite: per-case isolation — factory invoked once per case (contract §4)
func TestRunSuite_PerCaseIsolation_FactoryOncePerCase(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	var built int
	factory := func(ctx context.Context, h Harness) (int, error) {
		built++
		return built, nil
	}
	cases := []Case[int]{
		{Name: "a", Run: func(subject int, h Harness, report Report) {}},
		{Name: "b", Run: func(subject int, h Harness, report Report) {}},
		{Name: "c", Run: func(subject int, h Harness, report Report) {}},
	}
	suite := Suite[int]{Name: "iso", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if built != 3 {
		t.Fatalf("factory should be invoked once per case (3); got %d", built)
	}
	if res.Passed != 3 || res.Failed != 0 || res.Skipped != 0 {
		t.Fatalf("expected 3 passed; got %+v", res)
	}
}

// Deterministic ordering — cases run in the order Suite.Cases yields (contract §4).
func TestRunSuite_DeterministicOrdering(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	var order []string
	factory := func(ctx context.Context, h Harness) (string, error) { return "", nil }
	names := []string{"first", "second", "third", "fourth"}
	var cases []Case[string]
	for _, n := range names {
		n := n
		cases = append(cases, Case[string]{
			Name: n,
			Run:  func(subject string, h Harness, report Report) { order = append(order, n) },
		})
	}
	suite := Suite[string]{Name: "ord", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	for i, n := range names {
		if order[i] != n {
			t.Fatalf("case order diverged at %d: want %q got %q", i, n, order[i])
		}
		if res.Cases[i].Name != n {
			t.Fatalf("Result.Cases order diverged at %d: want %q got %q", i, n, res.Cases[i].Name)
		}
	}
}

// Panic containment — a panicking case becomes Fail with Panic non-empty; run
// continues and no panic escapes (contract §4, M2).
func TestRunSuite_PanicContainment(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	cases := []Case[int]{
		{Name: "boom", Run: func(subject int, h Harness, report Report) { panic("kaboom") }},
		{Name: "after", Run: func(subject int, h Harness, report Report) {}},
	}
	suite := Suite[int]{Name: "panic", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory) // must not panic out of RunSuite
	if res.Failed != 1 {
		t.Fatalf("panicking case should be 1 Fail; got Failed=%d (%+v)", res.Failed, res)
	}
	if res.Passed != 1 {
		t.Fatalf("the case after the panic must still run and pass; got Passed=%d", res.Passed)
	}
	var boom CaseResult
	for _, c := range res.Cases {
		if c.Name == "boom" {
			boom = c
		}
	}
	if boom.Outcome != Fail {
		t.Fatalf("panicking case Outcome must be Fail; got %v", boom.Outcome)
	}
	if boom.Panic == "" {
		t.Fatal("panicking case must have a non-empty Panic field")
	}
}

// A factory error is a failed case, not a panic (open question 2 reconciliation).
func TestRunSuite_FactoryErrorIsFailedCase(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	var ran bool
	factory := func(ctx context.Context, h Harness) (int, error) {
		return 0, context.DeadlineExceeded
	}
	cases := []Case[int]{
		{Name: "wiring", Run: func(subject int, h Harness, report Report) { ran = true }},
	}
	suite := Suite[int]{Name: "factoryerr", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if res.Failed != 1 {
		t.Fatalf("factory error should yield 1 Fail; got %+v", res)
	}
	if ran {
		t.Fatal("Run must not be called when the factory fails")
	}
	if len(res.Cases) == 0 || len(res.Cases[0].Messages) == 0 {
		t.Fatal("a factory-failed case must carry a message explaining the wiring failure")
	}
}

// Capability gating — h.Has(cap)==false then report.Skipf is recorded Skip,
// counted in Result.Skipped, never Fail (contract §4, 02 §1).
func TestRunSuite_CapabilityGating_SkipNotFail(t *gotest.T) {
	r := mustRunner(t, Config{RequireCapabilities: []string{"present"}}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	cases := []Case[int]{
		{Name: "needs-absent", Run: func(subject int, h Harness, report Report) {
			if !h.Has("absent") {
				report.Skipf("capability %q absent", "absent")
				return
			}
			report.Errorf("should not reach: absent capability reported present")
		}},
		{Name: "needs-present", Run: func(subject int, h Harness, report Report) {
			if !h.Has("present") {
				report.Errorf("required capability 'present' reported absent")
			}
		}},
	}
	suite := Suite[int]{Name: "cap", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if res.Skipped != 1 {
		t.Fatalf("absent-capability case must be 1 Skip; got %+v", res)
	}
	if res.Failed != 0 {
		t.Fatalf("a capability skip must never be a Fail; got Failed=%d", res.Failed)
	}
	if res.Passed != 1 {
		t.Fatalf("present-capability case must pass; got Passed=%d", res.Passed)
	}
}

// Errorf records a failure but the case still counts as Fail (continue semantics);
// Skipf wins over a prior Errorf only per the documented precedence: a case that
// both errors and skips — we assert the simple contract: Errorf ⇒ Fail.
func TestRunSuite_ErrorfMakesCaseFail(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	cases := []Case[int]{
		{Name: "bad", Run: func(subject int, h Harness, report Report) {
			report.Errorf("assertion failed: %d != %d", 1, 2)
		}},
	}
	suite := Suite[int]{Name: "errf", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if res.Failed != 1 {
		t.Fatalf("Errorf must make the case Fail; got %+v", res)
	}
	if len(res.Cases[0].Messages) == 0 {
		t.Fatal("Errorf message must be captured in CaseResult.Messages")
	}
}

// Fatalf aborts THIS case only and the run continues (contract §2 Report doc).
func TestRunSuite_FatalfAbortsOnlyThisCase(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	var reachedAfterFatal bool
	cases := []Case[int]{
		{Name: "fatal", Run: func(subject int, h Harness, report Report) {
			report.Fatalf("abort this case")
			reachedAfterFatal = true // must NOT execute
		}},
		{Name: "next", Run: func(subject int, h Harness, report Report) {}},
	}
	suite := Suite[int]{Name: "fatalf", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if reachedAfterFatal {
		t.Fatal("code after Fatalf executed; Fatalf must abort the case body")
	}
	if res.Failed != 1 {
		t.Fatalf("Fatalf case must be Fail; got %+v", res)
	}
	if res.Passed != 1 {
		t.Fatalf("the case after Fatalf must still run; got Passed=%d", res.Passed)
	}
}

// FailFast stops the run at the first failing case (contract §2 Config doc).
func TestRunSuite_FailFast(t *gotest.T) {
	r := mustRunner(t, Config{FailFast: true}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	var thirdRan bool
	cases := []Case[int]{
		{Name: "ok", Run: func(subject int, h Harness, report Report) {}},
		{Name: "fail", Run: func(subject int, h Harness, report Report) { report.Errorf("boom") }},
		{Name: "never", Run: func(subject int, h Harness, report Report) { thirdRan = true }},
	}
	suite := Suite[int]{Name: "ff", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if thirdRan {
		t.Fatal("FailFast must stop after the first failing case")
	}
	if res.Failed != 1 || res.Passed != 1 {
		t.Fatalf("FailFast result mismatch: %+v", res)
	}
}

// Cleanup runs LIFO after the case (contract §2 Harness.Cleanup doc).
func TestRunSuite_CleanupLIFO(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	var order []int
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	cases := []Case[int]{
		{Name: "registers", Run: func(subject int, h Harness, report Report) {
			h.Cleanup(func() { order = append(order, 1) })
			h.Cleanup(func() { order = append(order, 2) })
			h.Cleanup(func() { order = append(order, 3) })
		}},
	}
	suite := Suite[int]{Name: "cleanup", Cases: seq(cases...)}
	RunSuite(r, suite, factory)
	if len(order) != 3 || order[0] != 3 || order[1] != 2 || order[2] != 1 {
		t.Fatalf("Cleanup must run LIFO after the case; got %v", order)
	}
}

// Determinism injection — every subject's Harness vends a Clock anchored at Epoch,
// never the host clock (contract §4).
func TestRunSuite_HarnessClockIsDeterministic(t *gotest.T) {
	epoch := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	r := mustRunner(t, Config{}, Deps{Epoch: epoch})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	cases := []Case[int]{
		{Name: "clock", Run: func(subject int, h Harness, report Report) {
			if got := h.Clock().Now(); !got.Equal(epoch) {
				report.Errorf("Harness clock not anchored at epoch: want %v got %v", epoch, got)
			}
		}},
	}
	suite := Suite[int]{Name: "detclock", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if res.Failed != 0 {
		t.Fatalf("Harness clock should be deterministic at epoch; %+v", res.Cases)
	}
}

// Harness.Context is non-nil and carries the run context (contract §2 Harness.Context).
func TestRunSuite_HarnessContextNonNil(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) {
		if h.Context() == nil {
			return 0, context.Canceled
		}
		return 0, nil
	}
	cases := []Case[int]{
		{Name: "ctx", Run: func(subject int, h Harness, report Report) {
			if h.Context() == nil {
				report.Errorf("Harness.Context() returned nil")
			}
		}},
	}
	suite := Suite[int]{Name: "ctx", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if res.Failed != 0 {
		t.Fatalf("Harness.Context must be non-nil; %+v", res)
	}
}

// CaseTimeout bounds a single case; a case that respects ctx cancellation through
// Harness.Context observes the deadline (contract §2 Config.CaseTimeout).
func TestRunSuite_CaseTimeoutDeadlinePropagates(t *gotest.T) {
	r := mustRunner(t, Config{CaseTimeout: 10 * time.Millisecond}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	var hadDeadline bool
	cases := []Case[int]{
		{Name: "deadline", Run: func(subject int, h Harness, report Report) {
			if _, ok := h.Context().Deadline(); ok {
				hadDeadline = true
			}
		}},
	}
	suite := Suite[int]{Name: "timeout", Cases: seq(cases...)}
	RunSuite(r, suite, factory)
	if !hadDeadline {
		t.Fatal("CaseTimeout should give the case a context with a deadline")
	}
}

// Structured outcome — RunSuite returns counts + per-case outcomes (contract §4).
func TestRunSuite_StructuredResult(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	cases := []Case[int]{
		{Name: "p1", Run: func(subject int, h Harness, report Report) {}},
		{Name: "f1", Run: func(subject int, h Harness, report Report) { report.Errorf("x") }},
		{Name: "s1", Run: func(subject int, h Harness, report Report) { report.Skipf("y") }},
	}
	suite := Suite[int]{Name: "myport", Cases: seq(cases...)}
	res := RunSuite(r, suite, factory)
	if res.Suite != "myport" {
		t.Fatalf("Result.Suite mismatch: %q", res.Suite)
	}
	if res.Passed != 1 || res.Failed != 1 || res.Skipped != 1 {
		t.Fatalf("counts mismatch: %+v", res)
	}
	if len(res.Cases) != 3 {
		t.Fatalf("expected 3 CaseResults; got %d", len(res.Cases))
	}
}

// Zero-value Suite is an empty, runnable suite (contract §2 Suite doc).
func TestRunSuite_ZeroSuiteIsEmptyAndRunnable(t *gotest.T) {
	r := mustRunner(t, Config{}, Deps{})
	factory := func(ctx context.Context, h Harness) (int, error) { return 0, nil }
	var suite Suite[int] // zero value: nil Cases
	res := RunSuite(r, suite, factory)
	if res.Passed != 0 || res.Failed != 0 || res.Skipped != 0 {
		t.Fatalf("zero suite must run zero cases; got %+v", res)
	}
	if len(res.Cases) != 0 {
		t.Fatalf("zero suite must have no CaseResults; got %d", len(res.Cases))
	}
}

// Outcome constants are the documented tri-state with Pass=0 (iota) (contract §2).
func TestOutcomeConstants(t *gotest.T) {
	if Pass != 0 || Fail != 1 || Skip != 2 {
		t.Fatalf("Outcome constants must be Pass=0,Fail=1,Skip=2; got %d,%d,%d", Pass, Fail, Skip)
	}
}

// Reruns with the same Seed/Epoch are bit-identical in case outcomes (contract §4).
func TestRunSuite_RerunsAreIdentical(t *gotest.T) {
	run := func() Result {
		r := mustRunner(t, Config{Seed: 9}, Deps{Epoch: time.Unix(100, 0).UTC()})
		factory := func(ctx context.Context, h Harness) ([]byte, error) {
			p := make([]byte, 8)
			_, err := h.RandomSource().Read(p)
			return p, err
		}
		cases := []Case[[]byte]{
			{Name: "entropy", Run: func(subject []byte, h Harness, report Report) {
				if len(subject) != 8 {
					report.Errorf("short read")
				}
			}},
		}
		suite := Suite[[]byte]{Name: "rerun", Cases: seq(cases...)}
		return RunSuite(r, suite, factory)
	}
	a, b := run(), run()
	if a.Passed != b.Passed || a.Failed != b.Failed || a.Skipped != b.Skipped {
		t.Fatalf("reruns diverged: %+v vs %+v", a, b)
	}
}
