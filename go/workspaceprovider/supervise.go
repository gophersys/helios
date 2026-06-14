package workspaceprovider

import (
	"context"
	"sync"
)

// eventBuffer bounds the per-Supervise normalized Event channel: a slow consumer slows its own
// read (the agentsession backpressure ruling applied to events), and the buffer absorbs a burst
// of substrate transitions without blocking the watch goroutine momentarily.
const eventBuffer = 64

// Static assertion: the concrete *Provisioner satisfies the Supervisor port IN ADDITION to
// Provider — a consumer that only provisions holds Provider; the orchestrator holds Supervisor.
var _ Supervisor = (*Provisioner)(nil)

// Supervise starts the global label-filtered watch over the routable adapters' ownership domain
// and returns a stream of NORMALIZED Events. It reconciles-from-reality first (each adapter's
// Watch emits a synthetic WatchEvent per existing object before live changes), then streams. The
// library — not the adapter — maps each raw WatchEvent.Action onto an EventKind and stamps At from
// the injected Clock, so the normalization table lives in ONE place. The returned channel closes
// when ctx is canceled (the sole shutdown). UnsupportedError if NO routable adapter declares
// CapSupervise (a substrate that cannot watch is honestly unsupported, not silently empty).
func (s *Provisioner) Supervise(ctx context.Context, selector Selector) (<-chan Event, error) {
	watchers := s.watchers()
	if len(watchers) == 0 {
		return nil, wrapKind(&UnsupportedError{Cap: CapSupervise})
	}

	// Start every routable adapter's watch, then fan their raw streams into one merged channel the
	// normalize goroutine drains. Reconcile-from-reality is the adapter's obligation: each Watch
	// emits a synthetic WatchEvent per existing object before live changes (list-by-label
	// re-adoption), so a restart rebuilds the supervised set from the LIVE substrate.
	raws := make([]<-chan WatchEvent, 0, len(watchers))
	for _, w := range watchers {
		raw, err := w.Watch(ctx, selector)
		if err != nil {
			return nil, classify(err)
		}
		raws = append(raws, raw)
	}

	out := make(chan Event, eventBuffer)
	go s.fanIn(ctx, mergeWatch(ctx, raws), out)
	return out, nil
}

// fanIn drains the merged raw watch stream, normalizes each WatchEvent into a platform-neutral
// Event (stamping At from the Clock), and forwards it onto out, closing out exactly once when the
// source drains or ctx is canceled. It honors ctx on every send so a canceled supervisor never
// blocks on a full buffer with no reader (no goroutine leak — the goleak dimension proves it).
func (s *Provisioner) fanIn(ctx context.Context, merged <-chan WatchEvent, out chan<- Event) {
	defer close(out)
	for {
		select {
		case raw, ok := <-merged:
			if !ok {
				return
			}
			select {
			case out <- s.normalizeEvent(raw):
			case <-ctx.Done():
				return
			}
		case <-ctx.Done():
			return
		}
	}
}

// mergeWatch fans the per-adapter raw watch streams into ONE channel, closing it when every source
// closes (each source closes when ctx is canceled or the adapter's watch ends). One goroutine per
// source forwards into the merged channel; a WaitGroup-backed closer closes it once all forwarders
// return — the canonical leak-free fan-in (the goleak dimension asserts zero residual goroutines).
func mergeWatch(ctx context.Context, sources []<-chan WatchEvent) <-chan WatchEvent {
	merged := make(chan WatchEvent, eventBuffer)
	if len(sources) == 0 {
		close(merged)
		return merged
	}
	var wg sync.WaitGroup
	wg.Add(len(sources))
	for _, src := range sources {
		go func(src <-chan WatchEvent) {
			defer wg.Done()
			for {
				select {
				case ev, ok := <-src:
					if !ok {
						return
					}
					select {
					case merged <- ev:
					case <-ctx.Done():
						return
					}
				case <-ctx.Done():
					return
				}
			}
		}(src)
	}
	go func() {
		wg.Wait()
		close(merged)
	}()
	return merged
}

// normalizeEvent maps a raw adapter WatchEvent onto the platform-neutral Event: the library owns
// the Action→EventKind table (so docker "start"/"die"/"destroy"/"oom" and k8s "Running"/"Failed"/
// "Deleted" collapse to ONE closed EventKind set), folds the adapter's read State/Conditions in,
// carries the native reason in Detail, and stamps At from the injected Clock (so the fake is
// deterministic and New stays pure).
//
//nolint:gocritic // hugeParam: raw is one adapter WatchEvent normalized once per event; passing it by value is the normalization spine's natural shape.
func (s *Provisioner) normalizeEvent(raw WatchEvent) Event {
	condition := ConditionReady
	for _, c := range raw.Conditions {
		condition = c // the last typed condition wins (OOMKilled/Evicted dominate Ready)
	}
	return Event{
		Handle:    raw.Handle,
		Kind:      eventKindFor(raw.Action, raw.State, raw.Conditions),
		State:     raw.State,
		Condition: condition,
		Detail:    raw.Detail,
		At:        s.clock.Now(),
	}
}

// eventKindFor collapses a native action/phase string (+ the adapter's read State/Conditions) onto
// the closed EventKind set. It is the ONE normalization table (the IOTEA EventFromPlatform shape,
// adapted): docker start / k8s Running → Started; docker stop → Stopping; docker die-exit-0 / k8s
// Succeeded → Stopped; docker die-nonzero|oom / k8s Failed → Failed; docker destroy / k8s Deleted →
// Removed. A Gone State (the object vanished) is Removed; an OOM condition forces Failed.
func eventKindFor(action string, state State, conditions []Condition) EventKind {
	for _, c := range conditions {
		if c == ConditionOOMKilled {
			return EventFailed
		}
	}
	switch action {
	case "start", "Running", "running":
		if state == StateReady || state == StateRunning {
			return EventStarted
		}
	case "stop", "Stopping", "stopping":
		return EventStopping
	case "destroy", "Deleted", "deleted", "remove":
		return EventRemoved
	case "Succeeded", "succeeded":
		return EventStopped
	case "Failed", "failed", "oom":
		return EventFailed
	}
	// Fall back on the normalized State the adapter read (the action string is advisory; the
	// State is authoritative — a Gone object is Removed, an Evicted/Degraded is Failed, a Ready/
	// Running is Started).
	switch state {
	case StateGone:
		return EventRemoved
	case StateEvicted, StateDegraded:
		return EventFailed
	case StateReady, StateRunning:
		return EventStarted
	default:
		return EventStopping
	}
}

// Supervised reports the live supervised Status for one workspace by handle, read from the
// substrate via the adapter Probe (reconcile-from-reality — never an in-memory cache that can lie
// across a restart). It is Open(handle).Status without materializing a Workspace, the cheap
// supervised read the orchestrator Probes. NotFoundError if the workspace is gone.
func (s *Provisioner) Supervised(ctx context.Context, handle Handle) (Status, error) {
	if handle.IsZero() {
		return Status{}, wrapKind(&InvalidHandleError{Raw: handle.String()})
	}
	_, adapter, err := s.route(handle.Substrate())
	if err != nil {
		return Status{}, err
	}
	data, derr := adapter.Dial(ctx, handle)
	if derr != nil {
		return Status{}, classify(derr)
	}
	probe, perr := data.Connection.Probe(ctx)
	if perr != nil {
		return Status{}, classify(perr)
	}
	return Status{
		State:      probe.State,
		Conditions: probe.Conditions,
		Usage:      probe.Usage,
		Detail:     probe.Detail,
		Since:      s.clock.Now(),
	}, nil
}

// Reconcile rebuilds the supervised set from the LIVE substrate: it lists the ownership domain by
// selector (the reconcile-from-reality scan Supervise performs at startup), so a stateless restart
// re-adopts exactly what Eden authored with each Descriptor's current normalized State. It reuses
// the same fan-out List performs, so the supervised view and the reconcile view never drift.
func (s *Provisioner) Reconcile(ctx context.Context, selector Selector) ([]Descriptor, error) {
	return s.List(ctx, selector)
}

// watchers returns the routable adapters that implement the optional Watcher seam (declare
// CapSupervise and can watch). An adapter that does not is omitted — Supervise over a substrate
// with no watching adapter is UnsupportedError, never a silently empty stream.
//
//nolint:ireturn // collects the optional Watcher port from each adapter; returning the port slice is the seam.
func (s *Provisioner) watchers() []Watcher {
	out := make([]Watcher, 0, len(s.adapters))
	for _, adapter := range s.adapters {
		if w, ok := adapter.(Watcher); ok {
			out = append(out, w)
		}
	}
	return out
}
