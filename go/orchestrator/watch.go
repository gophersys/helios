package orchestrator

import (
	"context"

	"github.com/gophersys/libs/go/errors"
)

// watchBuffer bounds a Watch subscriber's in-flight backlog. A subscriber that overflows
// it is dropped from the live tail (its stream ends with a fault) rather than stalling
// the reconcile loop — the same pull-based backpressure agentsession uses, applied to the
// orchestration-plane transition stream.
const watchBuffer = 256

// watchSubscription is one live Watch attachment: a bounded channel of AgentEvents plus
// the Filter that scopes which agents' transitions it receives.
type watchSubscription struct {
	filter  Filter
	channel chan AgentEvent
	done    chan struct{} // closed when the subscriber's ctx ends or the Pool closes
}

// Watch streams AgentEvent transitions for agents matching filter, snapshot-then-tail:
// the current state of each matching agent is delivered first (so a fresh subscriber
// needs no separate List), then live transitions. Closing ctx ends THIS subscription
// only.
//
//nolint:gocritic,ireturn // contract §2: Filter is the frozen copyable query; Watch returns the AgentStream port the consumer holds.
func (p *Pool) Watch(ctx context.Context, filter Filter) (AgentStream, error) {
	if filter.Limit <= 0 {
		filter.Limit = defaultPageSize
	}
	sub := &watchSubscription{
		filter:  filter,
		channel: make(chan AgentEvent, watchBuffer),
		done:    make(chan struct{}),
	}

	// Register BEFORE the snapshot so no transition between the snapshot read and the live
	// tail is lost (any event published during the snapshot is buffered on the channel and
	// the stream deduplicates by delivering snapshot-then-buffered in order).
	p.watchersMu.Lock()
	p.watchers[sub] = struct{}{}
	p.watchersMu.Unlock()

	snapshot, err := p.dependencies.Desired.List(ctx, filter)
	if err != nil {
		p.removeWatcher(sub)
		return nil, errors.Wrap(errors.KindUnavailable, "orchestrator: watch snapshot", err)
	}

	stream := &agentStream{pool: p, sub: sub}
	// Prime the snapshot as the first emissions (current state per matching agent).
	for i := range snapshot.Agents {
		agent := snapshot.Agents[i]
		stream.snapshot = append(stream.snapshot, AgentEvent{
			AgentID: agent.ID, From: agent.Status, To: agent.Status,
			At: agent.UpdatedAt, Reason: "snapshot",
		})
	}

	// Tie the subscription lifetime to ctx so a canceled subscriber is reaped.
	go func() {
		<-ctx.Done()
		p.removeWatcher(sub)
	}()
	return stream, nil
}

// notifyWatchers delivers an AgentEvent to every live Watch subscriber whose Filter
// matches. It never blocks the caller (the reconcile loop / a verb): an overflowed
// subscriber is dropped. The caller may hold p.mu; watcher state has its own lock.
//
//nolint:gocritic // AgentEvent is a small copyable value record; each subscriber gets its own copy by design.
func (p *Pool) notifyWatchers(event AgentEvent) {
	p.watchersMu.Lock()
	defer p.watchersMu.Unlock()
	for sub := range p.watchers {
		if !matchesEventFilter(&sub.filter, event) {
			continue
		}
		select {
		case sub.channel <- event:
		default:
			// Overflow: drop the subscriber (its stream faults). The loop never stalls.
			close(sub.done)
			delete(p.watchers, sub)
		}
	}
}

// removeWatcher unregisters a subscription and signals its stream to end. Idempotent.
func (p *Pool) removeWatcher(sub *watchSubscription) {
	p.watchersMu.Lock()
	defer p.watchersMu.Unlock()
	if _, ok := p.watchers[sub]; ok {
		delete(p.watchers, sub)
		select {
		case <-sub.done:
		default:
			close(sub.done)
		}
	}
}

// matchesEventFilter reports whether an AgentEvent passes a Watch Filter's status
// constraints. Tenant/Template/Label scoping is applied at the snapshot (the durable
// record carries them); a live transition is delivered to a matching subscriber when its
// status filter (if any) admits the target status. OnlyActive excludes terminal targets.
func matchesEventFilter(filter *Filter, event AgentEvent) bool {
	if filter.OnlyActive && event.To.Terminal() {
		return false
	}
	if len(filter.Statuses) > 0 {
		found := false
		for _, s := range filter.Statuses {
			if s == event.To {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	return true
}

// agentStream is the one-shot AgentStream for one Watch subscriber: it drains the
// snapshot first, then the live channel, until ctx ends or the Pool closes.
type agentStream struct {
	pool     *Pool
	sub      *watchSubscription
	snapshot []AgentEvent
	cursor   int
	err      error
}

// Next returns the next transition (snapshot first, then live), or ok=false at end.
func (s *agentStream) Next(ctx context.Context) (AgentEvent, bool) {
	if s.cursor < len(s.snapshot) {
		event := s.snapshot[s.cursor]
		s.cursor++
		return event, true
	}
	select {
	case <-ctx.Done():
		return AgentEvent{}, false
	case <-s.sub.done:
		return AgentEvent{}, false
	case event, ok := <-s.sub.channel:
		if !ok {
			return AgentEvent{}, false
		}
		return event, true
	}
}

// Err reports a fault that ended the stream early (nil at a clean end).
func (s *agentStream) Err() error { return s.err }
