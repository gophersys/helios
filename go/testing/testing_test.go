// Tests for package testing — authored FIRST against the frozen contract
// (docs/architecture/contracts/testing.md §2 surface, §4 conformance properties),
// then implemented until green (TDD discipline, ADR-0016).
//
// This file is a black-box test (package testing_test, testpackage discipline): it
// exercises the constructor spine and RunSuite through the exported surface only,
// with stub subjects, without the testingtest fakes (those have their own suite).
// It imports the package under test under the alias `testingpkg` and stdlib
// `testing` under `gotest`, because the package under test is itself named
// `testing`.
package testing_test

import (
	"context"
	gotest "testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	testingpkg "github.com/gophersys/libs/go/testing"
)

// seq turns a slice of cases into the iter.Seq the Suite expects.
func seq[S any](cases ...testingpkg.Case[S]) func(yield func(testingpkg.Case[S]) bool) {
	return func(yield func(testingpkg.Case[S]) bool) {
		for _, c := range cases {
			if !yield(c) {
				return
			}
		}
	}
}

// mustRunner builds a Runner from the given Config/Deps or fails the test. The
// parameters are named cfgIn/depsIn (not the spine's configuration/dependencies) to
// avoid shadowing the imported dependencies package in this black-box test file.
func mustRunner(t *gotest.T, cfgIn testingpkg.Config, depsIn testingpkg.Deps) *testingpkg.Runner {
	t.Helper()
	r, err := testingpkg.New(cfgIn, depsIn)
	if err != nil {
		t.Fatalf("New(%+v, %+v): %v", cfgIn, depsIn, err)
	}
	if r == nil {
		t.Fatal("New returned a nil *Runner with nil error")
	}
	return r
}

// TestClockAlias_IsDependenciesClock proves the dependencies aliases are the SAME
// types, not redefinitions: a value of the alias type must satisfy the
// dependencies-owned interface and vice versa (contract §2: "a fake satisfying
// these satisfies dependencies'").
func TestClockAlias_IsDependenciesClock(t *gotest.T) {
	t.Parallel()
	// Passing a testingpkg.Clock where a dependencies.Clock is expected (and vice
	// versa) compiles only if the two named types are identical — the alias-identity
	// proof, expressed through typed parameters so neither a redundant typed
	// declaration (QF1011) nor a split decl/assign (S1021) is needed.
	wantDependencies := func(dependencies.Clock) {}
	wantTesting := func(testingpkg.Clock) {}
	var c testingpkg.Clock
	var d dependencies.Clock
	wantDependencies(c) // testingpkg.Clock → dependencies.Clock
	wantTesting(d)      // dependencies.Clock → testingpkg.Clock
}

// TestRandomSourceAlias_IsDependenciesRandomSource is the RandomSource counterpart
// of the alias-identity proof above.
func TestRandomSourceAlias_IsDependenciesRandomSource(t *gotest.T) {
	t.Parallel()
	// Same alias-identity proof as TestClockAlias, via typed parameters.
	wantDependencies := func(dependencies.RandomSource) {}
	wantTesting := func(testingpkg.RandomSource) {}
	var r testingpkg.RandomSource
	var d dependencies.RandomSource
	wantDependencies(r) // testingpkg.RandomSource → dependencies.RandomSource
	wantTesting(d)      // dependencies.RandomSource → testingpkg.RandomSource
}

// TestNew_ZeroValuesValid proves New is pure and zero values are valid and
// deterministic (rationale 4).
func TestNew_ZeroValuesValid(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	fakes := r.Fakes()
	if fakes.Clock == nil {
		t.Fatal("Fakes().Clock is nil")
	}
	if fakes.Random == nil {
		t.Fatal("Fakes().Random is nil")
	}
}

// TestNew_ZeroEpochIsUnixEpoch proves a zero Epoch anchors at the Unix epoch, never
// time.Now (contract §2 Deps doc).
func TestNew_ZeroEpochIsUnixEpoch(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	now := r.Fakes().Clock.Now()
	if !now.Equal(time.Unix(0, 0).UTC()) {
		t.Fatalf("zero Epoch should anchor at the Unix epoch; got %v", now)
	}
}

// TestNew_InjectedEpochHonored proves an injected Epoch is honored exactly (the
// cross-process reproducibility anchor).
func TestNew_InjectedEpochHonored(t *gotest.T) {
	t.Parallel()
	epoch := time.Date(2026, 6, 12, 0, 0, 0, 0, time.UTC)
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{Epoch: epoch})
	if got := r.Fakes().Clock.Now(); !got.Equal(epoch) {
		t.Fatalf("injected Epoch not honored: want %v got %v", epoch, got)
	}
}

// TestFakes_FreshEachCall proves Fakes returns a FRESH bundle each call —
// independent instances (contract §2: "a fresh, deterministic bundle"). Advancing
// one must not move another.
func TestFakes_FreshEachCall(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{Seed: 1}, testingpkg.Deps{})
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

// TestFakes_DeterministicAcrossRunners proves same Seed + same first Read sequence
// ⇒ identical bytes across distinct Runners (the frozen determinism invariant, open
// question 6).
func TestFakes_DeterministicAcrossRunners(t *gotest.T) {
	t.Parallel()
	mk := func() []byte {
		r := mustRunner(t, testingpkg.Config{Seed: 42}, testingpkg.Deps{})
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

// TestFakes_SeedAffectsStream proves different seeds ⇒ different streams (the seed
// must actually feed the PRNG).
func TestFakes_SeedAffectsStream(t *gotest.T) {
	t.Parallel()
	read := func(seed uint64) []byte {
		r := mustRunner(t, testingpkg.Config{Seed: seed}, testingpkg.Deps{})
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

// TestRunSuite_PerCaseIsolation_FactoryOncePerCase proves per-case isolation — the
// factory is invoked once per case (contract §4).
func TestRunSuite_PerCaseIsolation_FactoryOncePerCase(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	var built int
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) {
		built++
		return built, nil
	}
	cases := []testingpkg.Case[int]{
		{Name: "a", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
		{Name: "b", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
		{Name: "c", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
	}
	suite := testingpkg.Suite[int]{Name: "iso", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
	if built != 3 {
		t.Fatalf("factory should be invoked once per case (3); got %d", built)
	}
	if res.Passed != 3 || res.Failed != 0 || res.Skipped != 0 {
		t.Fatalf("expected 3 passed; got %+v", res)
	}
}

// TestRunSuite_DeterministicOrdering proves cases run in the order Suite.Cases
// yields (contract §4).
func TestRunSuite_DeterministicOrdering(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	var order []string
	factory := func(_ context.Context, _ testingpkg.Harness) (string, error) { return "", nil }
	names := []string{"first", "second", "third", "fourth"}
	var cases []testingpkg.Case[string]
	for _, n := range names {
		cases = append(cases, testingpkg.Case[string]{
			Name: n,
			Run:  func(_ string, _ testingpkg.Harness, _ testingpkg.Report) { order = append(order, n) },
		})
	}
	suite := testingpkg.Suite[string]{Name: "ord", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
	for i, n := range names {
		if order[i] != n {
			t.Fatalf("case order diverged at %d: want %q got %q", i, n, order[i])
		}
		if res.Cases[i].Name != n {
			t.Fatalf("Result.Cases order diverged at %d: want %q got %q", i, n, res.Cases[i].Name)
		}
	}
}

// TestRunSuite_PanicContainment proves a panicking case becomes Fail with Panic
// non-empty; the run continues and no panic escapes (contract §4, M2).
func TestRunSuite_PanicContainment(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "boom", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) { panic("kaboom") }},
		{Name: "after", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
	}
	suite := testingpkg.Suite[int]{Name: "panic", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory) // must not panic out of RunSuite
	if res.Failed != 1 {
		t.Fatalf("panicking case should be 1 Fail; got Failed=%d (%+v)", res.Failed, res)
	}
	if res.Passed != 1 {
		t.Fatalf("the case after the panic must still run and pass; got Passed=%d", res.Passed)
	}
	var boom testingpkg.CaseResult
	for _, c := range res.Cases {
		if c.Name == "boom" {
			boom = c
		}
	}
	if boom.Outcome != testingpkg.Fail {
		t.Fatalf("panicking case Outcome must be Fail; got %v", boom.Outcome)
	}
	if boom.Panic == "" {
		t.Fatal("panicking case must have a non-empty Panic field")
	}
}

// TestRunSuite_FactoryErrorIsFailedCase proves a factory error is a failed case,
// not a panic (open question 2 reconciliation).
func TestRunSuite_FactoryErrorIsFailedCase(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	var ran bool
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) {
		return 0, context.DeadlineExceeded
	}
	cases := []testingpkg.Case[int]{
		{Name: "wiring", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) { ran = true }},
	}
	suite := testingpkg.Suite[int]{Name: "factoryerr", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
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

// TestRunSuite_CapabilityGating_SkipNotFail proves capability gating — h.Has(cap)
// == false then report.Skipf is recorded Skip, counted in Result.Skipped, never
// Fail (contract §4, 02 §1).
func TestRunSuite_CapabilityGating_SkipNotFail(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{RequireCapabilities: []string{"present"}}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "needs-absent", Run: func(_ int, h testingpkg.Harness, report testingpkg.Report) {
			if !h.Has("absent") {
				report.Skipf("capability %q absent", "absent")
				return
			}
			report.Errorf("should not reach: absent capability reported present")
		}},
		{Name: "needs-present", Run: func(_ int, h testingpkg.Harness, report testingpkg.Report) {
			if !h.Has("present") {
				report.Errorf("required capability 'present' reported absent")
			}
		}},
	}
	suite := testingpkg.Suite[int]{Name: "cap", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
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

// TestRunSuite_ErrorfMakesCaseFail proves Errorf makes the case count as Fail
// (continue semantics) and the message is captured.
func TestRunSuite_ErrorfMakesCaseFail(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "bad", Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) {
			report.Errorf("assertion failed: %d != %d", 1, 2)
		}},
	}
	suite := testingpkg.Suite[int]{Name: "errf", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
	if res.Failed != 1 {
		t.Fatalf("Errorf must make the case Fail; got %+v", res)
	}
	if len(res.Cases[0].Messages) == 0 {
		t.Fatal("Errorf message must be captured in CaseResult.Messages")
	}
}

// TestRunSuite_FatalfAbortsOnlyThisCase proves Fatalf aborts THIS case only and the
// run continues (contract §2 Report doc).
func TestRunSuite_FatalfAbortsOnlyThisCase(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	var reachedAfterFatal bool
	cases := []testingpkg.Case[int]{
		{Name: "fatal", Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) {
			report.Fatalf("abort this case")
			reachedAfterFatal = true // must NOT execute
		}},
		{Name: "next", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
	}
	suite := testingpkg.Suite[int]{Name: "fatalf", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
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

// TestRunSuite_FailFast proves FailFast stops the run at the first failing case
// (contract §2 Config doc).
func TestRunSuite_FailFast(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{FailFast: true}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	var thirdRan bool
	cases := []testingpkg.Case[int]{
		{Name: "ok", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
		{Name: "fail", Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) { report.Errorf("boom") }},
		{Name: "never", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) { thirdRan = true }},
	}
	suite := testingpkg.Suite[int]{Name: "ff", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
	if thirdRan {
		t.Fatal("FailFast must stop after the first failing case")
	}
	if res.Failed != 1 || res.Passed != 1 {
		t.Fatalf("FailFast result mismatch: %+v", res)
	}
}

// TestRunSuite_CleanupLIFO proves Cleanup runs LIFO after the case (contract §2
// Harness.Cleanup doc).
func TestRunSuite_CleanupLIFO(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	var order []int
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "registers", Run: func(_ int, h testingpkg.Harness, _ testingpkg.Report) {
			h.Cleanup(func() { order = append(order, 1) })
			h.Cleanup(func() { order = append(order, 2) })
			h.Cleanup(func() { order = append(order, 3) })
		}},
	}
	suite := testingpkg.Suite[int]{Name: "cleanup", Cases: seq(cases...)}
	testingpkg.RunSuite(r, suite, factory)
	if len(order) != 3 || order[0] != 3 || order[1] != 2 || order[2] != 1 {
		t.Fatalf("Cleanup must run LIFO after the case; got %v", order)
	}
}

// TestRunSuite_HarnessClockIsDeterministic proves determinism injection — every
// subject's Harness vends a Clock anchored at Epoch, never the host clock (§4).
func TestRunSuite_HarnessClockIsDeterministic(t *gotest.T) {
	t.Parallel()
	epoch := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC)
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{Epoch: epoch})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "clock", Run: func(_ int, h testingpkg.Harness, report testingpkg.Report) {
			if got := h.Clock().Now(); !got.Equal(epoch) {
				report.Errorf("Harness clock not anchored at epoch: want %v got %v", epoch, got)
			}
		}},
	}
	suite := testingpkg.Suite[int]{Name: "detclock", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
	if res.Failed != 0 {
		t.Fatalf("Harness clock should be deterministic at epoch; %+v", res.Cases)
	}
}

// TestRunSuite_HarnessContextNonNil proves Harness.Context is non-nil and carries
// the run context (contract §2 Harness.Context).
func TestRunSuite_HarnessContextNonNil(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	factory := func(_ context.Context, h testingpkg.Harness) (int, error) {
		if h.Context() == nil {
			return 0, context.Canceled
		}
		return 0, nil
	}
	cases := []testingpkg.Case[int]{
		{Name: "ctx", Run: func(_ int, h testingpkg.Harness, report testingpkg.Report) {
			if h.Context() == nil {
				report.Errorf("Harness.Context() returned nil")
			}
		}},
	}
	suite := testingpkg.Suite[int]{Name: "ctx", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
	if res.Failed != 0 {
		t.Fatalf("Harness.Context must be non-nil; %+v", res)
	}
}

// TestRunSuite_CaseTimeoutDeadlinePropagates proves CaseTimeout bounds a single
// case; a case observes the deadline through Harness.Context (contract §2
// Config.CaseTimeout).
func TestRunSuite_CaseTimeoutDeadlinePropagates(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{CaseTimeout: 10 * time.Millisecond}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	var hadDeadline bool
	cases := []testingpkg.Case[int]{
		{Name: "deadline", Run: func(_ int, h testingpkg.Harness, _ testingpkg.Report) {
			if _, ok := h.Context().Deadline(); ok {
				hadDeadline = true
			}
		}},
	}
	suite := testingpkg.Suite[int]{Name: "timeout", Cases: seq(cases...)}
	testingpkg.RunSuite(r, suite, factory)
	if !hadDeadline {
		t.Fatal("CaseTimeout should give the case a context with a deadline")
	}
}

// TestRunSuite_StructuredResult proves RunSuite returns counts + per-case outcomes
// (contract §4).
func TestRunSuite_StructuredResult(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	cases := []testingpkg.Case[int]{
		{Name: "p1", Run: func(_ int, _ testingpkg.Harness, _ testingpkg.Report) {}},
		{Name: "f1", Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) { report.Errorf("x") }},
		{Name: "s1", Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) { report.Skipf("y") }},
	}
	suite := testingpkg.Suite[int]{Name: "myport", Cases: seq(cases...)}
	res := testingpkg.RunSuite(r, suite, factory)
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

// TestRunSuite_ZeroSuiteIsEmptyAndRunnable proves a zero-value Suite is an empty,
// runnable suite (contract §2 Suite doc).
func TestRunSuite_ZeroSuiteIsEmptyAndRunnable(t *gotest.T) {
	t.Parallel()
	r := mustRunner(t, testingpkg.Config{}, testingpkg.Deps{})
	factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
	var suite testingpkg.Suite[int] // zero value: nil Cases
	res := testingpkg.RunSuite(r, suite, factory)
	if res.Passed != 0 || res.Failed != 0 || res.Skipped != 0 {
		t.Fatalf("zero suite must run zero cases; got %+v", res)
	}
	if len(res.Cases) != 0 {
		t.Fatalf("zero suite must have no CaseResults; got %d", len(res.Cases))
	}
}

// TestOutcomeConstants proves the Outcome constants are the documented tri-state
// with Pass=0 (iota) (contract §2).
func TestOutcomeConstants(t *gotest.T) {
	t.Parallel()
	if testingpkg.Pass != 0 || testingpkg.Fail != 1 || testingpkg.Skip != 2 {
		t.Fatalf("Outcome constants must be Pass=0,Fail=1,Skip=2; got %d,%d,%d",
			testingpkg.Pass, testingpkg.Fail, testingpkg.Skip)
	}
}

// TestRunSuite_RerunsAreIdentical proves reruns with the same Seed/Epoch are
// bit-identical in case outcomes (contract §4).
func TestRunSuite_RerunsAreIdentical(t *gotest.T) {
	t.Parallel()
	run := func() testingpkg.Result {
		r := mustRunner(t, testingpkg.Config{Seed: 9}, testingpkg.Deps{Epoch: time.Unix(100, 0).UTC()})
		factory := func(_ context.Context, h testingpkg.Harness) ([]byte, error) {
			p := make([]byte, 8)
			_, err := h.RandomSource().Read(p)
			return p, err
		}
		cases := []testingpkg.Case[[]byte]{
			{Name: "entropy", Run: func(subject []byte, _ testingpkg.Harness, report testingpkg.Report) {
				if len(subject) != 8 {
					report.Errorf("short read")
				}
			}},
		}
		suite := testingpkg.Suite[[]byte]{Name: "rerun", Cases: seq(cases...)}
		return testingpkg.RunSuite(r, suite, factory)
	}
	a, b := run(), run()
	if a.Passed != b.Passed || a.Failed != b.Failed || a.Skipped != b.Skipped {
		t.Fatalf("reruns diverged: %+v vs %+v", a, b)
	}
}
