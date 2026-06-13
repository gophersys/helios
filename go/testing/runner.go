package testing

import (
	"fmt"

	"github.com/gophersys/libs/go/testing/internal/deterministic"
)

// Runner vends deterministic fakes and executes Suites. It is concrete (accept
// interfaces, return concrete). New is the pattern spine: PURE — no I/O, no clock
// read, no env read; it only fixes the deterministic starting state in Config/Deps.
// Errors are wrapped with %w and inspected via errors.AsType.
type Runner struct {
	epoch       epochAnchor // injected start instant for vended fakes
	seed        uint64      // deterministic RandomSource seed
	requireCaps map[string]struct{}
	caseTimeout timeoutPolicy // per-case deadline policy
	failFast    bool
}

// New is the pattern spine. It is PURE: it performs no I/O, reads no clock, and
// reads no env. It only fixes the deterministic starting state derived from the
// immutable Config and the injected Deps. A nil error and a non-nil *Runner are
// always returned for any valid input (zero values included).
func New(configuration Config, dependencies Deps) (*Runner, error) {
	caps := make(map[string]struct{}, len(configuration.RequireCapabilities))
	for _, c := range configuration.RequireCapabilities {
		caps[c] = struct{}{}
	}
	return &Runner{
		epoch:       epochAnchor{at: dependencies.Epoch},
		seed:        configuration.Seed,
		requireCaps: caps,
		caseTimeout: timeoutPolicy{d: configuration.CaseTimeout},
		failFast:    configuration.FailFast,
	}, nil
}

// Fakes returns a fresh, deterministic bundle for direct wiring into a subject's
// own Deps outside a suite run (e.g. a library's own unit test). Returned concrete.
func (r *Runner) Fakes() Fakes {
	return Fakes{
		Clock:  deterministic.NewClock(r.epoch.at),
		Random: deterministic.NewRandom(r.seed),
	}
}

// Fakes is the concrete (returned, not interface) bundle the Runner builds.
type Fakes struct {
	Clock  Clock        // a *testingtest.FakeClock under the hood
	Random RandomSource // a *testingtest.FakeRandomSource under the hood
}

// RunSuite executes every Case of suite against subjects built by factory, once per
// case for isolation. It NEVER lets a panic escape: a panicking case is recorded as
// a failed case (Panic non-empty) and the run continues (M2: one bad adapter case
// must not abort a 50-task run). It returns a machine-readable Result the
// engine/evidence layer folds into a GoTestEvidence envelope without parsing stdout.
func RunSuite[S any](r *Runner, suite Suite[S], factory Factory[S]) Result {
	result := Result{Suite: suite.Name}
	if suite.Cases == nil {
		return result
	}
	for c := range suite.Cases {
		cr := runCase(r, c, factory)
		result.Cases = append(result.Cases, cr)
		switch cr.Outcome {
		case Pass:
			result.Passed++
		case Fail:
			result.Failed++
		case Skip:
			result.Skipped++
		}
		if r.failFast && cr.Outcome == Fail {
			break
		}
	}
	return result
}

// runCase builds one fresh subject and runs one Case under panic containment and a
// per-case Harness, returning the structured CaseResult.
func runCase[S any](r *Runner, c Case[S], factory Factory[S]) (cr CaseResult) {
	cr.Name = c.Name
	rec := newRecorder()
	h := r.newHarness()
	defer h.runCleanup()

	// Panic containment: any panic — in the factory, the Run body, or a Fatalf's
	// goexit-equivalent — is captured here, not allowed to escape RunSuite.
	defer func() {
		if p := recover(); p != nil {
			cr.Outcome = Fail
			cr.Panic = fmt.Sprintf("%v", p)
			cr.Messages = rec.messages
		}
	}()

	subject, err := factory(h.runCtx, h)
	if err != nil {
		cr.Outcome = Fail
		cr.Messages = append(rec.messages, fmt.Sprintf("factory: %v", err))
		return cr
	}

	// Fatalf aborts THIS case via runFatal panic, caught locally so the run
	// continues with the next case.
	func() {
		defer func() {
			if p := recover(); p != nil {
				if _, ok := p.(fatalSignal); !ok {
					panic(p) // a real panic: re-raise to the containment recover above
				}
				// fatalSignal: the case body aborted; outcome is decided below.
			}
		}()
		c.Run(subject, h, rec)
	}()

	cr.Messages = rec.messages
	cr.Outcome = rec.outcome()
	return cr
}
