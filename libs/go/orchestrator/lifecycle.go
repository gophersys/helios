package orchestrator

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// emit hands one orchestration-plane ObservabilityEvent to the Telemetry seam. Telemetry
// failure never enters business logic (a dropped event can never fail a transition), so
// Emit returns nothing and emit swallows nothing it could check.
//
//nolint:gocritic // ObservabilityEvent is a small copyable value envelope; emit hands the seam its own copy by design.
func (p *Pool) emit(ctx context.Context, event ObservabilityEvent) {
	p.dependencies.Telemetry.Emit(ctx, event)
}

// Start runs the reconcile loop on its own goroutine at Config.ReconcileInterval, using
// the Deps-supplied reconcile ports, until ctx is canceled or Close. It is the ONE
// impure entry (it starts a goroutine and reads the Clock); New stays pure. Optional: a
// single-node app calls Start; a test calls Reconcile by hand. A second Start is a no-op.
func (p *Pool) Start(ctx context.Context) error {
	p.loopMu.Lock()
	if p.closed {
		p.loopMu.Unlock()
		return wrapKind(&ConfigError{Reason: "Start called on a closed Pool"})
	}
	if p.started {
		p.loopMu.Unlock()
		return nil
	}
	interval := p.configuration.ReconcileInterval
	if interval <= 0 {
		interval = defaultReconcileInterval
	}
	p.started = true
	p.stop = make(chan struct{})
	p.done = make(chan struct{})
	stop := p.stop
	done := p.done
	p.loopMu.Unlock()

	go p.loop(ctx, interval, stop, done)
	return nil
}

// loop ticks Reconcile at interval until stop is signaled or ctx is canceled, closing
// done on exit. When Config.RetentionWindow is set, each tick also reaps terminal agents
// whose UpdatedAt is older than the window (now - RetentionWindow is the cutoff), so the
// declared retention policy is actually honored by the running loop rather than waiting on
// an out-of-band caller. A pass error is non-fatal to the loop (the next tick retries); a
// per-agent fault is recorded on that agent inside Reconcile.
func (p *Pool) loop(ctx context.Context, interval time.Duration, stop, done chan struct{}) {
	defer close(done)
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-stop:
			return
		case <-ticker.C:
			_, _ = p.Reconcile(ctx, ReconcilePorts{}) //nolint:errcheck // a pass error is non-fatal; the next tick retries (loop stays live).
			if window := p.configuration.RetentionWindow; window > 0 {
				_, _ = p.Reap(ctx, p.now().Add(-window)) //nolint:errcheck // retention is best-effort on the loop cadence; a reap fault retries next tick.
			}
		}
	}
}

// Close stops the loop, records a Stopping intent for every non-terminal agent it owns
// (best-effort graceful drain bounded by ctx), and releases resources. Idempotent. It
// does NOT itself tear down pods — it records the intent the final reconcile pass acts
// on, then drives one final pass so the drain actually happens before Close returns.
func (p *Pool) Close(ctx context.Context) error {
	p.loopMu.Lock()
	if p.closed {
		p.loopMu.Unlock()
		return nil
	}
	p.closed = true
	started := p.started
	stop := p.stop
	done := p.done
	p.loopMu.Unlock()

	// Stop the loop goroutine if Start ran it.
	if started && stop != nil {
		close(stop)
		select {
		case <-done:
		case <-ctx.Done():
		}
	}

	// Record a Stopping intent for every non-terminal agent, then drive final passes so the
	// drain+release happens (the pod reap is reconcile's job, never Close's directly). The
	// stop is two-phase (live → Stopping → Stopped), so Close drives passes until the fleet
	// quiesces (no transition) or a bound is hit — each agent needs at most one Stopping and
	// one drain step, so a small bound past the active count converges. A residual non-terminal
	// agent (a teardown fault) is left for a later operator pass; idempotent Teardown converges.
	if err := p.recordCloseIntents(ctx); err != nil {
		return err
	}
	p.drainToQuiescent(ctx)

	// End every live Watch subscriber.
	p.closeWatchers()
	return nil
}

// drainToQuiescent drives final reconcile passes until no agent transitions (the fleet is
// drained: every agent reached Stopped/Failed or is wedged on a transient fault) or a bound
// is hit. The two-phase stop needs two steps per agent (→ Stopping, → Stopped); the bound is
// generous past that so a healthy fleet always reaches terminal within Close. A residual
// non-terminal agent is left for a later operator pass (idempotent Teardown converges).
func (p *Pool) drainToQuiescent(ctx context.Context) {
	const maxDrainPasses = 16
	for range maxDrainPasses {
		report, err := p.Reconcile(ctx, ReconcilePorts{})
		if err != nil || report.Transitioned == 0 {
			return // a pass error is non-fatal (a later operator pass retries); 0 transitions == quiesced
		}
	}
}

// recordCloseIntents marks every non-terminal agent the Pool owns as DesiredStopped, so
// the final reconcile passes drain and release it.
func (p *Pool) recordCloseIntents(ctx context.Context) error {
	page, err := p.dependencies.Desired.List(ctx, Filter{OnlyActive: true, Limit: 0})
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestrator: close list agents", err)
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	for i := range page.Agents {
		agent := page.Agents[i]
		if agent.Status.Terminal() || agent.Desired == DesiredStopped {
			continue
		}
		agent.Desired = DesiredStopped
		agent.UpdatedAt = p.now()
		agent.Detail = "pool closing"
		if err := p.dependencies.Desired.Put(ctx, agent); err != nil {
			return errors.Wrap(errors.KindUnavailable, "orchestrator: close record intent", err)
		}
	}
	return nil
}

// closeWatchers ends every live Watch subscriber's stream.
func (p *Pool) closeWatchers() {
	p.watchersMu.Lock()
	defer p.watchersMu.Unlock()
	for sub := range p.watchers {
		select {
		case <-sub.done:
		default:
			close(sub.done)
		}
		delete(p.watchers, sub)
	}
}
