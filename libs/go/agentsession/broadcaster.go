package agentsession

import (
	"sync"
)

// liveBufferSize bounds a live subscriber's in-flight buffer. A subscriber that
// overflows it is demoted to a FromSeq replay reader off the durable transcript (it
// catches up by re-reading, never by skipping — the gap-free guarantee). The size is
// generous: a chat tab reads at human speed but rarely lags by hundreds of events.
const liveBufferSize = 256

// broadcaster is the fan-out hub for one session's live tail. The single pump
// goroutine calls publish for every Seq-stamped event; each live subscriber holds a
// bounded channel. publish never blocks on a slow subscriber: on overflow it marks
// the subscriber demoted and stops feeding it (the stream then catches up by replay).
//
// Concurrency: all state is guarded by mu. publish and (un)subscribe may race; the
// mutex serializes them. Channels are buffered so publish does not hold mu across a
// blocking send. done is closed exactly once at close so a stream's live loop detects
// end-of-session without busy-polling.
type broadcaster struct {
	mu          sync.Mutex
	subscribers map[*subscription]struct{}
	closed      bool
	head        uint64        // the highest Seq published (the live boundary for a fresh subscriber)
	done        chan struct{} // closed once at close
}

// subscription is one live attachment: a bounded channel plus a demotion flag the
// stream consults to fall back to transcript replay.
type subscription struct {
	channel chan Event
	demoted bool
	lastSeq uint64 // the last Seq delivered to this subscriber (its replay cursor on demotion)
}

// newBroadcaster constructs an empty fan-out hub.
func newBroadcaster() *broadcaster {
	return &broadcaster{
		subscribers: make(map[*subscription]struct{}),
		done:        make(chan struct{}),
	}
}

// publish delivers event to every live subscriber and advances head. A subscriber
// whose buffer is full is marked demoted (its stream re-reads the transcript from
// lastSeq); publish never blocks. It is a no-op once closed.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); fan-out hands each viewer an independent copy by design.
func (b *broadcaster) publish(event Event) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return
	}
	b.head = event.Seq
	for sub := range b.subscribers {
		if sub.demoted {
			continue
		}
		select {
		case sub.channel <- event:
			sub.lastSeq = event.Seq
		default:
			// Overflow: demote this subscriber. Its stream catches up by replaying the
			// durable transcript from lastSeq — never by dropping the event.
			sub.demoted = true
		}
	}
}

// subscribe registers a live subscriber and returns it plus the current head, so the
// stream knows the boundary between transcript replay and the live tail. Registering
// BEFORE the stream reads the transcript head guarantees no event is missed at the
// seam: any event published during replay is buffered here and deduplicated by Seq.
func (b *broadcaster) subscribe() (sub *subscription, head uint64) {
	b.mu.Lock()
	defer b.mu.Unlock()
	sub = &subscription{channel: make(chan Event, liveBufferSize)}
	b.subscribers[sub] = struct{}{}
	return sub, b.head
}

// unsubscribe removes a live subscriber. Idempotent.
func (b *broadcaster) unsubscribe(sub *subscription) {
	b.mu.Lock()
	defer b.mu.Unlock()
	delete(b.subscribers, sub)
}

// demoted reports whether the subscriber overflowed and must catch up via replay.
func (b *broadcaster) demoted(sub *subscription) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return sub.demoted
}

// reattach clears a demoted subscriber's backlog and re-enrolls it for the live tail
// after its stream has caught up via transcript replay. It returns the live head at
// re-attach; the stream re-reads the transcript until that head is reached with no
// gap, deduplicating by Seq.
func (b *broadcaster) reattach(sub *subscription) uint64 {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return b.head
	}
	for {
		select {
		case <-sub.channel:
		default:
			sub.demoted = false
			return b.head
		}
	}
}

// close shuts the hub: every live subscriber's channel is closed so its stream drains
// and ends, and done is closed. Idempotent.
func (b *broadcaster) close() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.closed {
		return
	}
	b.closed = true
	close(b.done)
	for sub := range b.subscribers {
		close(sub.channel)
	}
	b.subscribers = make(map[*subscription]struct{})
}

// isClosed reports whether the hub has been closed.
func (b *broadcaster) isClosed() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.closed
}

// closeNotify returns the channel closed exactly once when the hub closes, so a
// stream's live loop can select on it alongside its subscription channel and ctx.
func (b *broadcaster) closeNotify() <-chan struct{} { return b.done }

// currentHead reports the highest Seq published so far.
func (b *broadcaster) currentHead() uint64 {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.head
}
