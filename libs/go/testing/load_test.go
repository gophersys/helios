//go:build load

package testing_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	gotest "testing"
	"time"

	"go.uber.org/goleak"

	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500
// in-process; ADR-0020 dimension (e) threshold).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentRunSuiteRaceClean fans out N goroutines that each build a fresh Runner
// and execute a Suite concurrently. RunSuite builds an independent per-case Harness (fresh
// Clock/RandomSource) for isolation, so N concurrent runs must produce identical, race-free
// results under -race; goleak then asserts the goroutine high-water returns to baseline
// (ADR-0020 dimension (e)). A shared-mutable-state bug in the Runner/Harness would surface as
// a data race or a divergent count here.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling would make it flaky, so the load probe runs serially.
func TestLoad_ConcurrentRunSuiteRaceClean(t *gotest.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	factory := func(_ context.Context, h testingpkg.Harness) ([]byte, error) {
		p := make([]byte, 16)
		_, err := h.RandomSource().Read(p)
		return p, err
	}
	cases := []testingpkg.Case[[]byte]{
		{Name: "entropy-nonempty", Run: func(subject []byte, _ testingpkg.Harness, report testingpkg.Report) {
			if len(subject) != 16 {
				report.Errorf("short entropy read: %d", len(subject))
			}
		}},
		{Name: "clock-anchored", Run: func(_ []byte, h testingpkg.Harness, report testingpkg.Report) {
			if h.Clock().Now().IsZero() {
				report.Errorf("harness clock not anchored")
			}
		}},
	}
	suite := testingpkg.Suite[[]byte]{Name: "loadsuite", Cases: testingtest.CaseSeq(cases...)}

	// Every worker builds an INDEPENDENT Runner from the SAME deterministic Config/Deps: the
	// invariant under test is that N concurrent RunSuite executions over independent Runners are
	// race-free (each builds its own per-case Harness) and all produce the identical, correct
	// result. A fixed seed/epoch (no per-worker derivation) keeps this free of int conversions
	// (gosec G115) while still exercising the full concurrent construct->run->account path.
	const workerSeed uint64 = 0x5eed
	epoch := time.Unix(1700000000, 0).UTC()
	var wg sync.WaitGroup
	wg.Add(n)
	failures := make(chan string, n)
	for range n {
		go func() {
			defer wg.Done()
			r, err := testingpkg.New(testingpkg.Config{Seed: workerSeed}, testingpkg.Deps{Epoch: epoch})
			if err != nil {
				failures <- "New failed"
				return
			}
			res := testingpkg.RunSuite(r, suite, factory)
			if res.Passed != 2 || res.Failed != 0 {
				failures <- "worker diverged: " + strconv.Itoa(res.Passed) + "p " + strconv.Itoa(res.Failed) + "f"
			}
		}()
	}
	wg.Wait()
	close(failures)
	for f := range failures {
		t.Fatalf("concurrent RunSuite produced an incorrect result under fan-out: %s", f)
	}
}

// TestLoad_ConcurrentFakeClockRaceClean fans out N goroutines hammering a SINGLE FakeClock
// with Now/After/Advance concurrently. The clock documents goroutine-safety; this proves it
// under -race at fan-out, and goleak asserts that every cancellable After waiter goroutine
// was reaped (no orphan) once the contexts are canceled (ADR-0020 dimension (e)).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling would make it flaky.
func TestLoad_ConcurrentFakeClockRaceClean(t *gotest.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	clock := testingtest.NewFakeClock(time.Unix(0, 0).UTC())
	ctx, cancel := context.WithCancel(context.Background())

	var wg sync.WaitGroup
	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			_ = clock.Now()
			// Half the workers register a cancellable waiter; the rest advance time. The
			// shared ctx is canceled after Wait so every waiter goroutine unwinds (the
			// orphan-goroutine assertion goleak makes).
			if i%2 == 0 {
				_ = clock.After(ctx, time.Duration(i+1)*time.Second)
			} else {
				clock.Advance(time.Millisecond)
			}
		}(i)
	}
	wg.Wait()
	cancel() // unwind every cancellable After waiter goroutine
	// Give the best-effort cancel goroutines a virtual nudge: a final Advance drains any
	// already-due waiter and the cancel path removes the rest. goleak.VerifyNone then
	// asserts none survived.
	clock.Advance(time.Duration(n+1) * time.Second)
}
