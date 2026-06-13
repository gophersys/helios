package testing

import (
	"context"
	"fmt"
	"time"

	"github.com/gophersys/libs/go/testing/internal/deterministic"
)

// epochAnchor is the injected, host-free start instant for vended fakes. Stored as
// a plain value so New stays pure (no clock read).
type epochAnchor struct{ at time.Time }

// timeoutPolicy bounds a single case; a zero duration means inherit the run
// context only (no per-case deadline).
type timeoutPolicy struct{ d time.Duration }

// suiteHarness is the per-case Harness implementation. It vends a fresh
// deterministic Clock/RandomSource, gates capabilities from the Runner's
// RequireCapabilities set, owns LIFO Cleanup, and exposes the run Context (with the
// per-case timeout applied). A new suiteHarness is built per case for isolation.
type suiteHarness struct {
	clock    *deterministic.Clock
	random   *deterministic.Random
	caps     map[string]struct{}
	runCtx   context.Context
	cancel   context.CancelFunc
	cleanups []func()
}

// newHarness builds a fresh per-case Harness. Capability gating is OPT-OUT by
// presence: a case requires a capability via h.Has(name); a name in the Runner's
// RequireCapabilities set is present, anything else is absent. This matches the
// suite-side contract where RequireCapabilities enumerates the run's declared
// capabilities and a case gated on an undeclared one skips.
func (r *Runner) newHarness() *suiteHarness {
	ctx := context.Background()
	var cancel context.CancelFunc
	if r.caseTimeout.d > 0 {
		ctx, cancel = context.WithTimeout(ctx, r.caseTimeout.d)
	}
	return &suiteHarness{
		clock:  deterministic.NewClock(r.epoch.at),
		random: deterministic.NewRandom(r.seed),
		caps:   r.requireCaps,
		runCtx: ctx,
		cancel: cancel,
	}
}

// Clock and RandomSource return the port interfaces the Harness contract declares
// (contract §2): the deterministic *deterministic.Clock/*deterministic.Random
// adapters are internal by design, so the Harness vends them as their ports. The
// ireturn "return concrete" rule is wrong-for-contract for exactly these two
// methods — they implement the frozen Harness interface and cannot return the
// unexported concrete type.

//nolint:ireturn // contract §2: Harness.Clock() returns the Clock port; the *deterministic.Clock adapter is internal by design.
func (h *suiteHarness) Clock() Clock { return h.clock }

//nolint:ireturn // contract §2: Harness.RandomSource() returns the RandomSource port; the *deterministic.Random adapter is internal by design.
func (h *suiteHarness) RandomSource() RandomSource { return h.random }

func (h *suiteHarness) Context() context.Context { return h.runCtx }

// Has reports whether capability is present for this run. Presence = membership in
// the Runner's RequireCapabilities set (02 §1 CapabilityManifest gate).
func (h *suiteHarness) Has(capability string) bool {
	_, ok := h.caps[capability]
	return ok
}

// Cleanup registers a teardown to run LIFO after the case.
func (h *suiteHarness) Cleanup(fn func()) {
	h.cleanups = append(h.cleanups, fn)
}

// runCleanup runs registered cleanups in LIFO order and cancels the case context.
// Each cleanup is invoked under its OWN recover so a panicking cleanup cannot
// escape RunSuite (contract: RunSuite NEVER lets a panic escape — M2). The first
// cleanup panic is returned, formatted, so runCase can fold it into the CaseResult;
// remaining cleanups still run (a teardown is not abandoned because an earlier one
// panicked). An empty string means no cleanup panicked.
func (h *suiteHarness) runCleanup() string {
	var firstPanic string
	for i := len(h.cleanups) - 1; i >= 0; i-- {
		if p := runOneCleanup(h.cleanups[i]); p != "" && firstPanic == "" {
			firstPanic = p
		}
	}
	if h.cancel != nil {
		h.cancel()
	}
	return firstPanic
}

// runOneCleanup invokes a single cleanup under recover, returning the formatted
// panic value if it panicked (empty string otherwise). Isolating one cleanup per
// recover is what lets the LIFO chain continue past a panicking entry.
func runOneCleanup(fn func()) (recovered string) {
	defer func() {
		if p := recover(); p != nil {
			recovered = fmt.Sprintf("cleanup panicked: %v", p)
		}
	}()
	fn()
	return ""
}
