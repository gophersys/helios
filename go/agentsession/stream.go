package agentsession

import (
	"context"

	"github.com/gophersys/libs/go/errors"
)

// liveStream is the consumer-facing Stream: replay-then-tail off the durable
// transcript with no gap and no dup at the seam (the "Seq == transcript offset"
// invariant). It first drains the transcript [from+1 .. head] via ReadFrom, then
// attaches to the broadcaster's live tail; events already published during replay are
// deduplicated by Seq. A live subscriber that overflows its buffer is demoted and
// transparently catches up by re-reading the transcript from its last delivered Seq
// (never skipping). Closing ctx drops THIS stream only.
//
// Concurrency: a single consumer goroutine calls Next; the stream is NOT safe for
// concurrent Next calls (one Stream == one viewer). Multiple Streams over one Session
// are independent (fan-out). All per-stream state (pending, nextSeq) lives here, not
// on the shared session, so streams never race each other.
type liveStream struct {
	session      *session
	subscriber   *subscription
	pending      Stream // a partially-drained transcript replay reader, or nil when tailing live
	nextSeq      uint64 // the next Seq the consumer expects (dedup + gap detection)
	replayOpened bool   // whether the one-time initial transcript replay has been opened
	terminated   bool
	err          error
}

// newLiveStream registers a live subscriber FIRST (so nothing published during replay
// is lost), then begins replay from `from`. Every event published while replay runs
// is buffered on the subscriber channel and deduplicated by Seq at the seam.
func newLiveStream(s *session, from Cursor) *liveStream {
	subscriber, _ := s.broadcaster.subscribe()
	l := &liveStream{
		session:    s,
		subscriber: subscriber,
		nextSeq:    uint64(from) + 1,
	}
	return l
}

// Next blocks for the next event in strict Seq order. ok=false at end-of-stream
// (terminal reached, ctx canceled, or fault). It drains the durable transcript
// prefix first, then tails live, deduplicating across the seam by Seq.
func (l *liveStream) Next(ctx context.Context) (Event, bool) {
	if l.terminated {
		return Event{}, false
	}
	// Lazily open the replay reader on the first Next so newLiveStream stays I/O-free.
	if l.pending == nil && l.nextSeq > 0 && !l.replayOpened {
		l.openReplay(ctx, l.nextSeq-1)
		if l.terminated {
			return Event{}, false
		}
	}
	return l.deliver(ctx)
}

// Err reports a fault that ended the stream early (a transcript decode fault, a pod
// death). nil at a clean terminal end or an open stream.
func (l *liveStream) Err() error { return l.err }

// deliver is the main loop: drain the pending replay reader, then tail live, demoting
// to a fresh replay on subscriber overflow, ending on terminal/close/ctx/fault.
func (l *liveStream) deliver(ctx context.Context) (Event, bool) {
	for {
		if l.pending != nil {
			if event, ok, advanced := l.drainPending(ctx); advanced {
				return event, ok
			}
			if l.terminated {
				return Event{}, false
			}
			continue
		}
		if l.session.broadcaster.demoted(l.subscriber) {
			if !l.catchUp(ctx) {
				return Event{}, false
			}
			continue
		}
		event, ok, done := l.tailOnce(ctx)
		if done {
			return event, ok
		}
		// not done: loop (e.g. dedup skip, or switched to pending via close)
	}
}

// tailOnce performs one blocking live read. done=true means "return (event, ok) to
// the caller"; done=false means "continue the deliver loop" (a dedup skip or a
// transition to close-drain).
func (l *liveStream) tailOnce(ctx context.Context) (Event, bool, bool) {
	select {
	case <-ctx.Done():
		l.session.broadcaster.unsubscribe(l.subscriber)
		l.terminated = true
		return Event{}, false, true
	case <-l.session.broadcaster.closeNotify():
		l.openReplay(ctx, l.nextSeq-1) // drain any tail appended past the live channel
		return Event{}, false, false
	case event, ok := <-l.subscriber.channel:
		if !ok {
			l.openReplay(ctx, l.nextSeq-1)
			return Event{}, false, false
		}
		if event.Seq < l.nextSeq {
			return Event{}, false, false // dedup at the seam
		}
		l.advance(event)
		return event, true, true
	}
}

// drainPending reads the next event from the in-flight replay reader. advanced=true
// returns (event, ok) to the caller; advanced=false means the reader is exhausted (or
// produced a duplicate) and the deliver loop should re-evaluate.
func (l *liveStream) drainPending(ctx context.Context) (Event, bool, bool) {
	event, ok := l.pending.Next(ctx)
	if !ok {
		if e := l.pending.Err(); e != nil {
			l.fail(e)
			return Event{}, false, true
		}
		l.pending = nil
		// If the session has closed and we have drained the transcript to head, end.
		if l.session.broadcaster.isClosed() && l.nextSeq > l.session.broadcaster.currentHead() {
			l.session.broadcaster.unsubscribe(l.subscriber)
			l.terminated = true
			return Event{}, false, true
		}
		return Event{}, false, false
	}
	if event.Seq < l.nextSeq {
		return Event{}, false, false // dedup
	}
	l.advance(event)
	return event, true, true
}

// catchUp re-reads the durable transcript from the last delivered Seq for a demoted
// subscriber, then re-attaches it to the live tail. Returns false on a transcript
// fault (the stream has been failed).
func (l *liveStream) catchUp(ctx context.Context) bool {
	l.openReplay(ctx, l.nextSeq-1)
	if l.terminated {
		return false
	}
	l.session.broadcaster.reattach(l.subscriber)
	return true
}

// openReplay opens a transcript replay reader from `fromSeq` into l.pending. On a
// transcript fault it fails the stream.
func (l *liveStream) openReplay(ctx context.Context, fromSeq uint64) {
	l.replayOpened = true
	reader, err := l.session.transcript.ReadFrom(ctx, l.session.id, FromSeq(fromSeq))
	if err != nil {
		l.fail(errors.Wrap(errors.KindUnavailable, "agentsession: replay transcript", err))
		return
	}
	l.pending = reader
}

// advance records delivery of event: bumps the dedup cursor and marks terminal.
//
//nolint:gocritic // Event is the contract's copyable value record (§2); the stream advances on a value copy.
func (l *liveStream) advance(event Event) {
	l.nextSeq = event.Seq + 1
	if event.IsTerminal() {
		l.terminated = true
		l.session.broadcaster.unsubscribe(l.subscriber)
	}
}

// fail records a fault, unsubscribes, and terminates the stream.
func (l *liveStream) fail(err error) {
	l.err = err
	l.session.broadcaster.unsubscribe(l.subscriber)
	l.pending = nil
	l.terminated = true
}
