package agentsessiontest

import (
	"runtime"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// stateTransitions projects the SessionState transitions from a drained stream.
func stateTransitions(events []agentsession.Event) []agentsession.StatePayload {
	var out []agentsession.StatePayload
	for i := range events {
		ev := &events[i]
		if ev.Kind == agentsession.EventSessionState && ev.State != nil {
			out = append(out, *ev.State)
		}
	}
	return out
}

// terminalCount counts terminal events in a drained stream (must be exactly one).
func terminalCount(events []agentsession.Event) int {
	count := 0
	for i := range events {
		ev := &events[i]
		if ev.IsTerminal() {
			count++
		}
	}
	return count
}

// legalEdge mirrors the library's legal transition graph for the suite's independent
// check (Initializing->Ready->{Running<->AwaitingInput | AwaitingPermission}->terminal).
func legalEdge(from, to agentsession.State) bool {
	if from.IsTerminal() {
		return false
	}
	switch to {
	case agentsession.StateInitializing:
		return from == agentsession.StateInitializing
	case agentsession.StateReady:
		return from == agentsession.StateInitializing
	case agentsession.StateRunning:
		return from == agentsession.StateReady ||
			from == agentsession.StateAwaitingInput ||
			from == agentsession.StateAwaitingPermission
	case agentsession.StateAwaitingInput:
		return from == agentsession.StateRunning
	case agentsession.StateAwaitingPermission:
		return from == agentsession.StateRunning
	case agentsession.StateCompleted, agentsession.StateFailed, agentsession.StateAborted:
		return true
	default:
		return false
	}
}

// assertToolCorrelation proves every EventToolUpdate/ToolEnd correlates to an
// EventToolStart by CallID.
func assertToolCorrelation(t *testing.T, events []agentsession.Event) {
	t.Helper()
	started := map[string]bool{}
	for i := range events {
		ev := &events[i]
		if ev.Tool == nil {
			continue
		}
		switch ev.Kind {
		case agentsession.EventToolStart:
			started[ev.Tool.CallID] = true
		case agentsession.EventToolUpdate, agentsession.EventToolEnd:
			if !started[ev.Tool.CallID] {
				t.Errorf("%s for CallID %q has no preceding EventToolStart", ev.Kind, ev.Tool.CallID)
			}
		default:
		}
	}
}

// assertNoGap proves a drained slice is strictly Seq-contiguous and dup-free.
func assertNoGap(t *testing.T, events []agentsession.Event) {
	t.Helper()
	for i := 1; i < len(events); i++ {
		if events[i].Seq != events[i-1].Seq+1 {
			t.Errorf("gap or dup at index %d: Seq %d follows %d", i, events[i].Seq, events[i-1].Seq)
		}
	}
}

// equalSeqs reports whether two Seq slices are identical.
func equalSeqs(a, b []uint64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// runtimeGosched yields the processor, letting other goroutines run (used to pace a slow
// subscriber into demotion without a sleep).
func runtimeGosched() { runtime.Gosched() }

// seqs projects events to their Seq numbers (for fan-out parity assertions).
func seqs(events []agentsession.Event) []uint64 {
	out := make([]uint64, len(events))
	for i := range events {
		ev := &events[i]
		out[i] = ev.Seq
	}
	return out
}
