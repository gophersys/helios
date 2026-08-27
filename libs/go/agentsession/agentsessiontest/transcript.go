package agentsessiontest

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// Transcript is an in-memory agentsession.Transcript so Seq assignment and FromSeq
// replay are exercised for REAL (not stubbed) in kernel tests. Append assigns a
// per-session monotonic Seq equal to the stored offset (Seq == transcript offset, the
// load-bearing invariant); ReadFrom serves [from+1 .. head] for replay and is available
// AFTER a session terminates (old-Run reload).
//
// Concurrency: Append (the pump's single writer) and ReadFrom (every viewer's replay)
// race; all state is guarded by mu. ReadFrom snapshots the prefix under the lock so a
// concurrent Append never corrupts a replay in flight.
type Transcript struct {
	mu       sync.Mutex
	bySessio map[string][]agentsession.Event
}

// NewTranscript constructs an empty in-memory transcript.
func NewTranscript() *Transcript {
	return &Transcript{bySessio: make(map[string][]agentsession.Event)}
}

// Append durably stores one Event and returns the Seq it was assigned (the 1-based
// transcript offset within the session). Called once per Event before fan-out, so every
// viewer sees identical Seq numbers.
//
//nolint:gocritic // contract §2: Transcript.Append takes the Event value (the immutable record; the fake mirrors the frozen seam).
func (t *Transcript) Append(_ context.Context, event agentsession.Event) (uint64, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if event.SessionID == "" {
		return 0, errors.New(errors.KindInvalid, "agentsessiontest: transcript append requires a SessionID")
	}
	existing := t.bySessio[event.SessionID]
	seq := uint64(len(existing)) + 1 // 1-based offset == Seq
	event.Seq = seq
	t.bySessio[event.SessionID] = append(existing, event)
	return seq, nil
}

// ReadFrom returns the stored events [from+1 .. head] for replay as a one-shot Stream.
// It snapshots under the lock so a concurrent Append cannot corrupt the view.
//
//nolint:ireturn // contract §2: Transcript.ReadFrom returns the Stream port (the frozen seam the fake mirrors).
func (t *Transcript) ReadFrom(_ context.Context, sessionID string, from agentsession.Cursor) (agentsession.Stream, error) {
	t.mu.Lock()
	stored := t.bySessio[sessionID]
	start := int(from) // #nosec G115 -- from is a bounded replay cursor (the last-seen Seq); replay begins at index `from`, and an out-of-range wrap is clamped by the start<0 guard below
	if start < 0 {
		start = 0
	}
	var snapshot []agentsession.Event
	if start < len(stored) {
		snapshot = make([]agentsession.Event, len(stored)-start)
		copy(snapshot, stored[start:])
	}
	t.mu.Unlock()
	return &replayStream{events: snapshot}, nil
}

// Len reports how many events are stored for a session (test introspection).
func (t *Transcript) Len(sessionID string) int {
	t.mu.Lock()
	defer t.mu.Unlock()
	return len(t.bySessio[sessionID])
}

// replayStream is a one-shot agentsession.Stream over a snapshot of stored events. It
// is gap-free and dup-free by construction (the snapshot is contiguous and ordered).
type replayStream struct {
	events []agentsession.Event
	index  int
}

// Next yields the next stored event in order; ok=false at end-of-snapshot.
func (r *replayStream) Next(_ context.Context) (agentsession.Event, bool) {
	if r.index >= len(r.events) {
		return agentsession.Event{}, false
	}
	event := r.events[r.index]
	r.index++
	return event, true
}

// Err is always nil: an in-memory snapshot never faults mid-read.
func (r *replayStream) Err() error { return nil }

// compile-time assertions.
var (
	_ agentsession.Transcript = (*Transcript)(nil)
	_ agentsession.Stream     = (*replayStream)(nil)
)
