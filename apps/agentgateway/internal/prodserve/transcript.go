package prodserve

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// transcript is the production composition's in-process agentsession.Transcript: it assigns the
// monotonic per-session Seq (Seq == transcript offset, the agentsession invariant) and serves
// FromSeq replay. The propose turn opens through the shared agentsession pool (Deps.Transcript),
// which appends the harness stream here; the SAME instance backs the gateway's post-mortem
// transcript route. It mirrors the proven in-process transcript the live-local (internal/liveserve),
// orchestrator-role, and agent-runtime compositions each carry — the same mechanism, kept
// composition-local so the production binary imports no test package (agentsessiontest is
// test-only). Guarded by mu. NOTE: agentsession.New REQUIRES a non-nil Transcript (Seq assignment
// lives there) — a nil here is a construction error, the exact crash-loop v0.1.7 shipped.
type transcript struct {
	mu         sync.Mutex
	bySessions map[string][]agentsession.Event
}

// newTranscript constructs an empty in-process transcript.
func newTranscript() *transcript {
	return &transcript{bySessions: make(map[string][]agentsession.Event)}
}

// Append durably (in-process) stores one Event and returns the 1-based Seq it was assigned.
//
//nolint:gocritic // agentsession.Event is the contract's copyable value record (§2); the Transcript seam takes it by value.
func (t *transcript) Append(_ context.Context, event agentsession.Event) (uint64, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if event.SessionID == "" {
		return 0, errors.New(errors.KindInvalid, "prodserve transcript: append requires a SessionID")
	}
	existing := t.bySessions[event.SessionID]
	seq := uint64(len(existing)) + 1
	event.Seq = seq
	t.bySessions[event.SessionID] = append(existing, event)
	return seq, nil
}

// ReadFrom returns the stored events [from+1 .. head] for replay as a one-shot Stream, snapshotted
// under the lock so a concurrent Append cannot corrupt the view.
//
//nolint:ireturn // contract: Transcript.ReadFrom returns the agentsession.Stream port (the frozen seam).
func (t *transcript) ReadFrom(_ context.Context, sessionID string, from agentsession.Cursor) (agentsession.Stream, error) {
	t.mu.Lock()
	stored := t.bySessions[sessionID]
	start := int(from) // #nosec G115 -- from is a bounded replay cursor; an out-of-range value is clamped below.
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

// replayStream is a one-shot agentsession.Stream over a snapshot of stored events (gap-free,
// dup-free by construction — the snapshot is contiguous and ordered).
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
	_ agentsession.Transcript = (*transcript)(nil)
	_ agentsession.Stream     = (*replayStream)(nil)
)
