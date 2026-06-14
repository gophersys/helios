package agentruntime_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// errFakePublish is the seeded bus-publish failure for the publish-error-does-not-stall-pump test.
var errFakePublish = errors.New(errors.KindUnavailable, "fake bus publish failure")

// fastHeartbeat shrinks the heartbeat interval so a short test observes several beats, and seeds an
// InitialPrompt so the scripted fake harness (which waits for the first prompt before streaming its
// body) actually streams its canonical script to a terminal under the seed-prompt path.
func fastHeartbeat(configuration *agentruntime.Config) {
	configuration.HeartbeatInterval = 5 * time.Millisecond
	configuration.DrainTimeout = 5 * time.Second
	configuration.InitialPrompt = "go"
}

// interactiveFast shrinks the heartbeat but leaves InitialPrompt empty — the interactive path where
// the first turn arrives as a control PROMPT verb (not a seed). Used for the control round-trip and
// the idle stop/kill/signal tests.
func interactiveFast(configuration *agentruntime.Config) {
	configuration.HeartbeatInterval = 5 * time.Millisecond
	configuration.DrainTimeout = 5 * time.Second
}

// assertSeqOrderedGapFree proves the published envelopes are strictly Seq-ordered with no holes — the
// load-bearing replay invariant (a gateway replays by ascending Seq; a gap or a reorder breaks it).
func assertSeqOrderedGapFree(t *testing.T, events []agentruntime.EventEnvelope) {
	t.Helper()
	var prev uint64
	for i := range events {
		if events[i].Seq != prev+1 {
			t.Fatalf("envelope %d Seq = %d, want %d (Seq must be gap-free and ordered)", i, events[i].Seq, prev+1)
		}
		if events[i].Event.Seq != events[i].Seq {
			t.Errorf("envelope %d: envelope Seq %d != event Seq %d", i, events[i].Seq, events[i].Event.Seq)
		}
		prev = events[i].Seq
	}
}

// assertOTelOnEveryEvent proves EVERY published envelope carries the OTel trace carrier (the
// ADR-0022 invariant — OTel context rides every message).
func assertOTelOnEveryEvent(t *testing.T, events []agentruntime.EventEnvelope) {
	t.Helper()
	for i := range events {
		if events[i].OTel[keyTraceParent] != agentruntimetest.TraceParent {
			t.Errorf("envelope %d (seq=%d) missing the OTel traceparent carrier: %v", i, events[i].Seq, events[i].OTel)
		}
	}
}

// keyTraceParent is the W3C carrier key the assertions check.
const keyTraceParent = "traceparent"

// eventKindOnBus reports whether any published envelope carries an event of the given kind.
func eventKindOnBus(events []agentruntime.EventEnvelope, kind agentsession.EventKind) bool {
	for i := range events {
		if events[i].Event.Kind == kind {
			return true
		}
	}
	return false
}

// textDeltaOnBus reports whether a published text-delta event carries the given delta.
func textDeltaOnBus(events []agentruntime.EventEnvelope, delta string) bool {
	for i := range events {
		ev := &events[i].Event
		if ev.Kind == agentsession.EventTextDelta && ev.Message != nil && ev.Message.Delta == delta {
			return true
		}
	}
	return false
}

// waitForHeartbeats polls the fake bus until at least n heartbeats are published or the deadline
// passes (a test that asserts liveness without racing the ticker).
func waitForHeartbeats(t *testing.T, bus *agentruntimetest.FakeBus, n int) {
	t.Helper()
	deadline := time.After(5 * time.Second)
	for {
		if len(bus.Heartbeats()) >= n {
			return
		}
		select {
		case <-deadline:
			t.Fatalf("did not observe %d heartbeats (saw %d)", n, len(bus.Heartbeats()))
		case <-time.After(2 * time.Millisecond):
		}
	}
}

// noopCancelContext returns a background ctx (a readability alias at call sites that pass a parent).
func noopCancelContext() context.Context { return context.Background() }
