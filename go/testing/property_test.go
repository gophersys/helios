package testing_test

import (
	"context"
	gotest "testing"
	"time"

	"pgregory.net/rapid"

	testingpkg "github.com/gophersys/libs/go/testing"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS set in the process
// environment (default 1000 iterations/property, ADR-0020 dimension (a) threshold); rapid
// reads it directly. These properties pin the Runner spine's purity/determinism invariants
// and RunSuite's outcome-accounting invariant across the whole input space, not just the
// hand-picked points the unit suite covers. (The package under test is named `testing`, so
// the stdlib import is aliased `gotest`.)

// propSeq turns a slice of cases into the iter.Seq the Suite expects.
func propSeq[S any](cases ...testingpkg.Case[S]) func(yield func(testingpkg.Case[S]) bool) {
	return func(yield func(testingpkg.Case[S]) bool) {
		for _, c := range cases {
			if !yield(c) {
				return
			}
		}
	}
}

// TestProperty_FakesDeterministicFromSeed asserts the frozen determinism invariant (OQ6)
// over the WHOLE seed space: for ANY seed, two Runners built from the same Config.Seed vend
// byte-identical entropy for the same Read length. A PRNG that did not fully derive from the
// seed, or a Fakes() that shared mutable state across Runners, would falsify this.
func TestProperty_FakesDeterministicFromSeed(t *gotest.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		seed := rapid.Uint64().Draw(rt, "seed")
		n := rapid.IntRange(1, 256).Draw(rt, "len")
		read := func() []byte {
			r, err := testingpkg.New(testingpkg.Config{Seed: seed}, testingpkg.Deps{})
			if err != nil {
				rt.Fatalf("New: %v", err)
			}
			p := make([]byte, n)
			if _, err := r.Fakes().Random.Read(p); err != nil {
				rt.Fatalf("Read: %v", err)
			}
			return p
		}
		a, b := read(), read()
		for i := range a {
			if a[i] != b[i] {
				rt.Fatalf("seed %d len %d: byte %d diverged across Runners (%#x vs %#x)", seed, n, i, a[i], b[i])
			}
		}
	})
}

// TestProperty_EpochAnchorsClock asserts the injected-Epoch invariant over the whole time
// axis: for ANY injected Epoch, the vended FakeClock's Now() equals that Epoch exactly (the
// cross-process reproducibility anchor — New never reads the host clock). Only the zero
// Epoch maps elsewhere (to the Unix epoch), excluded here.
func TestProperty_EpochAnchorsClock(t *gotest.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// Draw a non-zero unix-nanosecond instant so the zero-Epoch->UnixEpoch special case
		// (its own unit test) is not what this property exercises.
		nanos := rapid.Int64Range(1, 4_102_444_800_000_000_000).Draw(rt, "nanos")
		epoch := time.Unix(0, nanos).UTC()
		r, err := testingpkg.New(testingpkg.Config{}, testingpkg.Deps{Epoch: epoch})
		if err != nil {
			rt.Fatalf("New: %v", err)
		}
		if got := r.Fakes().Clock.Now(); !got.Equal(epoch) {
			rt.Fatalf("injected Epoch not honored: want %v got %v", epoch, got)
		}
	})
}

// TestProperty_RunSuiteAccountingIsExact asserts RunSuite's accounting invariant over ANY
// mix of pass/fail/skip outcomes: Passed+Failed+Skipped == number of cases run, len(Cases)
// matches, and each count equals the number of cases that produced that outcome. This is the
// structural invariant engine/evidence folds on — a miscount (e.g. a skip silently downgraded
// to a fail, or a case dropped) falsifies it.
func TestProperty_RunSuiteAccountingIsExact(t *gotest.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// 0 = pass, 1 = fail, 2 = skip.
		kinds := rapid.SliceOfN(rapid.IntRange(0, 2), 0, 32).Draw(rt, "outcomes")
		r, err := testingpkg.New(testingpkg.Config{}, testingpkg.Deps{})
		if err != nil {
			rt.Fatalf("New: %v", err)
		}
		var wantPass, wantFail, wantSkip int
		cases := make([]testingpkg.Case[int], 0, len(kinds))
		for i, k := range kinds {
			kind := k
			cases = append(cases, testingpkg.Case[int]{
				Name: "c" + string(rune('a'+i%26)),
				Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) {
					switch kind {
					case 1:
						report.Errorf("planned fail")
					case 2:
						report.Skipf("planned skip")
					}
				},
			})
			switch kind {
			case 0:
				wantPass++
			case 1:
				wantFail++
			case 2:
				wantSkip++
			}
		}
		factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
		suite := testingpkg.Suite[int]{Name: "acct", Cases: propSeq(cases...)}
		res := testingpkg.RunSuite(r, suite, factory)
		if res.Passed != wantPass || res.Failed != wantFail || res.Skipped != wantSkip {
			rt.Fatalf("accounting drift: got P%d F%d S%d want P%d F%d S%d (n=%d)",
				res.Passed, res.Failed, res.Skipped, wantPass, wantFail, wantSkip, len(kinds))
		}
		if res.Passed+res.Failed+res.Skipped != len(kinds) {
			rt.Fatalf("counts do not sum to %d cases: %+v", len(kinds), res)
		}
		if len(res.Cases) != len(kinds) {
			rt.Fatalf("len(Cases)=%d, want %d", len(res.Cases), len(kinds))
		}
	})
}

// failFastCases builds N cases (kinds[i]==1 ⇒ fail, else pass) and returns them with the
// index of the FIRST failing case (-1 if none). Factored out of the property body so the
// case-construction loop does not inflate the test's cognitive complexity (gocognit).
func failFastCases(kinds []int) (cases []testingpkg.Case[int], firstFail int) {
	firstFail = -1
	cases = make([]testingpkg.Case[int], 0, len(kinds))
	for i, k := range kinds {
		if k == 1 && firstFail == -1 {
			firstFail = i
		}
		kind := k
		cases = append(cases, testingpkg.Case[int]{
			Name: "c",
			Run: func(_ int, _ testingpkg.Harness, report testingpkg.Report) {
				if kind == 1 {
					report.Errorf("fail")
				}
			},
		})
	}
	return cases, firstFail
}

// TestProperty_FailFastStopsAtFirstFailure asserts that with FailFast, RunSuite records
// exactly the cases up to and including the first failing one, for ANY outcome sequence: no
// case after the first failure runs, and Failed is 0 (all passes) or 1 (stopped at first
// fail). This is the FailFast contract generalised past the single hand-written sequence.
func TestProperty_FailFastStopsAtFirstFailure(t *gotest.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// Draw outcomes where 1 = fail, else pass (skip omitted: FailFast keys on Fail only).
		kinds := rapid.SliceOfN(rapid.IntRange(0, 1), 1, 24).Draw(rt, "outcomes")
		r, err := testingpkg.New(testingpkg.Config{FailFast: true}, testingpkg.Deps{})
		if err != nil {
			rt.Fatalf("New: %v", err)
		}
		cases, firstFail := failFastCases(kinds)
		factory := func(_ context.Context, _ testingpkg.Harness) (int, error) { return 0, nil }
		res := testingpkg.RunSuite(r, testingpkg.Suite[int]{Name: "ff", Cases: propSeq(cases...)}, factory)
		if firstFail == -1 {
			// No failure at all: every case runs, none fail.
			if res.Failed != 0 || len(res.Cases) != len(kinds) {
				rt.Fatalf("no-failure run should run all %d cases with 0 fails; got %+v", len(kinds), res)
			}
			return
		}
		if res.Failed != 1 {
			rt.Fatalf("FailFast must stop at the FIRST failure (exactly 1 fail); got Failed=%d", res.Failed)
		}
		// Exactly firstFail+1 cases ran (the passes before it, plus the failing one).
		if len(res.Cases) != firstFail+1 {
			rt.Fatalf("FailFast ran %d cases; want %d (stop after first fail at index %d)",
				len(res.Cases), firstFail+1, firstFail)
		}
	})
}
