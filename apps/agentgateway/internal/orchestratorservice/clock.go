package orchestratorservice

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// systemClock is the production time source the composition root injects into every clock
// seam (orchestrator.Clock, agentsession.Clock, workspaceprovider's dependencies.Clock,
// observability.Clock). It is the ONE place a real wall clock is read — the libraries stay
// pure (New reads no clock). It satisfies every narrow Now()-only Clock port AND the wider
// dependencies.Clock (Now + After) the workspaceprovider holds, so a single value wires them
// all without per-seam adapters.
//
// It delegates to dependencies.RealClock() rather than re-spelling time.Now/time.After (one
// concept, one home): the real OS clock+timer impl lives once in the dependencies library.
type systemClock struct {
	inner dependencies.Clock
}

// newSystemClock returns the production wall-clock seam backed by dependencies.RealClock().
func newSystemClock() systemClock {
	return systemClock{inner: dependencies.RealClock()}
}

// Now returns the current wall-clock instant (the narrow Now()-only Clock contract every Eden
// library's Clock port declares).
func (c systemClock) Now() time.Time { return c.inner.Now() }

// After returns a channel that fires after d on this clock's timeline, honoring ctx (the wider
// dependencies.Clock contract the workspaceprovider holds). It delegates to the real timer.
func (c systemClock) After(ctx context.Context, d time.Duration) <-chan time.Time {
	return c.inner.After(ctx, d)
}
