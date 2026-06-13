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
// done on exit. A pass error is non-fatal to the loop (the next tick retries); a per-agent
// fault is recorded on that agent inside Reconcile.
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

	// Record a Stopping intent for every non-terminal agent, then drive one final pass so
	// the drain+release happens (the pod reap is reconcile's job, never Close's directly).
	if err := p.recordCloseIntents(ctx); err != nil {
		return err
	}
	_, _ = p.Reconcile(ctx, ReconcilePorts{}) //nolint:errcheck // a final-pass error is non-fatal; idempotent Teardown converges on a later (operator) pass.

	// End every live Watch subscriber.
	p.closeWatchers()
	return nil
}

// recordCloseIntents marks every non-terminal agent the Pool owns as DesiredStopped, so
// the final reconcile pass drains and releases it.
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
