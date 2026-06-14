package workspaceprovidertest

import (
	"context"

	"github.com/gophersys/libs/go/workspaceprovider"
)

// Static assertion: the in-memory *Adapter implements the OPTIONAL workspaceprovider.Watcher seam
// (it declares CapSupervise), so the conformance supervision case runs against the fake exactly as
// it runs against the real docker/k3d adapters — the fake ≡ adapter closure (08 §2).
var _ workspaceprovider.Watcher = (*Adapter)(nil)

// Watch is the fake's supervision watch: it reconciles-from-reality (one synthetic "started"
// WatchEvent per existing in-memory workspace matching selector), then streams any further events
// the test injects via EmitEvent, closing when ctx is canceled. It models the real adapters'
// shape — list-by-label re-adoption first, live transitions after — so the library's normalize/
// fan-in path is exercised deterministically without a substrate.
func (a *Adapter) Watch(ctx context.Context, selector workspaceprovider.Selector) (<-chan workspaceprovider.WatchEvent, error) {
	out := make(chan workspaceprovider.WatchEvent, 64)

	a.mu.Lock()
	seed := make([]workspaceprovider.WatchEvent, 0, len(a.state))
	for _, ws := range a.state {
		if !matchesLabels(ws.spec.Labels, selector.Labels) {
			continue
		}
		seed = append(seed, workspaceprovider.WatchEvent{
			Handle: ws.handle,
			Action: "start",
			State:  workspaceprovider.StateRunning,
			Detail: "reconcile-from-reality (fake)",
		})
	}
	ch := make(chan workspaceprovider.WatchEvent, 16)
	a.watchSinks = append(a.watchSinks, ch)
	a.mu.Unlock()

	go func() {
		defer close(out)
		for i := range seed {
			select {
			case out <- seed[i]:
			case <-ctx.Done():
				return
			}
		}
		for {
			select {
			case ev := <-ch:
				select {
				case out <- ev:
				case <-ctx.Done():
					return
				}
			case <-ctx.Done():
				return
			}
		}
	}()
	return out, nil
}

// EmitEvent pushes a raw WatchEvent onto every live fake watch stream (a test injects a synthetic
// transition — e.g. an OOM-kill — so the supervision case asserts the library normalizes it into
// the platform-neutral Event). Non-blocking per sink (a full sink drops, matching a real bounded
// watch under backpressure).
//
//nolint:gocritic // hugeParam: EmitEvent is a test-only injector taking the event by value (the natural call shape); a copy per injected event is not a path.
func (a *Adapter) EmitEvent(ev workspaceprovider.WatchEvent) {
	a.mu.Lock()
	defer a.mu.Unlock()
	for _, sink := range a.watchSinks {
		select {
		case sink <- ev:
		default:
		}
	}
}
