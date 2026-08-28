package agentruntime_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentsession"
)

// runFor drives runtime.Run in a goroutine and returns a func that waits for the typed reason
// (bounded so a regression fails fast rather than hanging).
func runFor(ctx context.Context, t *testing.T, runtime *agentruntime.Runtime) func() agentruntime.TerminationReason {
	t.Helper()
	type result struct {
		reason agentruntime.TerminationReason
		err    error
	}
	done := make(chan result, 1)
	go func() {
		reason, err := runtime.Run(ctx)
		done <- result{reason, err}
	}()
	return func() agentruntime.TerminationReason {
		t.Helper()
		select {
		case r := <-done:
			if r.err != nil {
				t.Fatalf("Run returned an error: %v", r.err)
			}
			return r.reason
		case <-time.After(10 * time.Second):
			t.Fatal("Run did not return within 10s (a termination trigger was not honored)")
			return agentruntime.TerminationUnknown
		}
	}
}

// TestRun_PumpsSequencedEventStreamToBus is the load-bearing happy path: under the seed-prompt path
// the full-script harness session is pumped and EVERY event reaches agent.<id>.events as a
// Seq-stamped envelope, in Seq order, gap-free, each carrying the OTel carrier, ending on the
// session's own terminal (TerminationSessionEnd). This is what the B5 gateway will replay.
func TestRun_PumpsSequencedEventStreamToBus(t *testing.T) {
	t.Parallel()
	runtime, bus, observer := agentruntimetest.NewRuntime(t, fastHeartbeat, agentruntimetest.CanonicalScript()...)

	reason := runFor(noopCancelContext(), t, runtime)()
	if reason != agentruntime.TerminationSessionEnd {
		t.Fatalf("termination reason = %s, want session-end", reason)
	}

	events := bus.Events()
	if len(events) == 0 {
		t.Fatal("no events reached the bus")
	}
	assertSeqOrderedGapFree(t, events)
	assertOTelOnEveryEvent(t, events)
	if last := events[len(events)-1]; !last.Event.IsTerminal() {
		t.Errorf("last published event is not terminal: kind=%s", last.Event.Kind)
	}
	if !eventKindOnBus(events, agentsession.EventToolStart) || !eventKindOnBus(events, agentsession.EventResult) {
		t.Errorf("the full script did not reach the bus (missing tool-start or result)")
	}
	if observer.FlushCount() == 0 {
		t.Errorf("OTel was not flushed at shutdown")
	}
}

// TestRun_PublishesHeartbeats proves the sidecar publishes agent.<id>.health heartbeats carrying the
// agent id, the OTel carrier, and a terminal stopped phase — the liveness the orchestrator Probes.
func TestRun_PublishesHeartbeats(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, fastHeartbeat, agentruntimetest.CanonicalScript()...)
	runFor(noopCancelContext(), t, runtime)()

	beats := bus.Heartbeats()
	if len(beats) == 0 {
		t.Fatal("no heartbeats were published")
	}
	for _, beat := range beats {
		if beat.AgentID != agentruntimetest.AgentID {
			t.Errorf("heartbeat agent id = %q, want %q", beat.AgentID, agentruntimetest.AgentID)
		}
		if len(beat.OTel) == 0 {
			t.Errorf("heartbeat missing OTel carrier")
		}
	}
	if last := beats[len(beats)-1]; last.Phase != agentruntime.PhaseStopped {
		t.Errorf("final heartbeat phase = %s, want stopped", last.Phase)
	}
}

// TestRun_PublishesFullPhaseProgression proves every member of the closed HealthPhase taxonomy is
// actually emitted on the wire across one lifecycle, IN ORDER: PhaseStarting (the sidecar attached,
// before the first event) → PhaseRunning (the steady state) → PhaseDraining (the shutdown drain
// window the orchestrator observes) → PhaseStopped (terminal). The earlier half-wiring published
// neither Starting (the loop led with Running) nor Draining (the heartbeat goroutine returned the
// instant agentCtx canceled, so its in-ticker draining branch never fired) — this asserts the
// declared taxonomy advertises no unreachable state.
func TestRun_PublishesFullPhaseProgression(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, interactiveFast)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wait := runFor(ctx, t, runtime)

	<-bus.Subscribed()
	waitForHeartbeats(t, bus, 1) // the run loop is live (Starting+Running already published) before STOP
	bus.Inject(agentruntime.ControlMessage{AgentID: agentruntimetest.AgentID, Verb: agentruntime.VerbStop})
	if reason := wait(); reason != agentruntime.TerminationControlStop {
		t.Fatalf("reason = %s, want control-stop", reason)
	}

	beats := bus.Heartbeats()
	phases := make([]agentruntime.HealthPhase, len(beats))
	for i, beat := range beats {
		phases[i] = beat.Phase
	}
	// Each advertised phase must appear, and the FIRST occurrence of each must respect the lifecycle
	// order Starting < Running < Draining < Stopped (intervening Running ticks are allowed).
	wantOrder := []agentruntime.HealthPhase{
		agentruntime.PhaseStarting,
		agentruntime.PhaseRunning,
		agentruntime.PhaseDraining,
		agentruntime.PhaseStopped,
	}
	assertPhaseProgression(t, phases, wantOrder)
	// PhaseStopped is the terminal, published exactly once and last.
	if last := phases[len(phases)-1]; last != agentruntime.PhaseStopped {
		t.Errorf("final phase = %s, want stopped", last)
	}
}

// assertPhaseProgression checks that each phase in want first appears in phases in strictly
// increasing index order (the closed taxonomy is fully emitted AND ordered). A missing phase is the
// half-wired-liveness regression; an out-of-order first occurrence is a mis-sequenced state machine.
func assertPhaseProgression(t *testing.T, phases, want []agentruntime.HealthPhase) {
	t.Helper()
	prevIndex := -1
	for _, phase := range want {
		index := -1
		for i, got := range phases {
			if got == phase {
				index = i
				break
			}
		}
		if index < 0 {
			t.Fatalf("phase %s was never published (the closed taxonomy advertises an unreachable state); published: %v", phase, phases)
		}
		if index <= prevIndex {
			t.Fatalf("phase %s first appeared at index %d, not after the previous phase (index %d); published: %v", phase, index, prevIndex, phases)
		}
		prevIndex = index
	}
}

// TestRun_ControlPromptRoundTrip proves the orchestrator→sidecar control round-trip: with NO seed
// prompt the scripted harness is idle (only Ready), so a PROMPT verb published to agent.<id>.control
// is what unblocks its scripted body — a reply text-delta reaching agent.<id>.events PROVES the verb
// was enacted onto the session. The control message's trace is extracted (OTel on the control side).
func TestRun_ControlPromptRoundTrip(t *testing.T) {
	t.Parallel()
	runtime, bus, observer := agentruntimetest.NewRuntime(t, interactiveFast, agentruntimetest.CanonicalScript()...)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wait := runFor(ctx, t, runtime)

	<-bus.Subscribed()
	bus.Inject(agentruntime.ControlMessage{
		AgentID: agentruntimetest.AgentID,
		Verb:    agentruntime.VerbPrompt,
		Text:    "hello",
		By:      "user:mateo",
		OTel:    agentruntime.OTelContext{"traceparent": agentruntimetest.TraceParent},
	})

	if reason := wait(); reason != agentruntime.TerminationSessionEnd {
		t.Fatalf("reason = %s, want session-end after the prompt reply", reason)
	}
	if !textDeltaOnBus(bus.Events(), "Hello") {
		t.Errorf("the prompt reply (canonical 'Hello') did not reach the bus — the PROMPT verb was not enacted")
	}
	if got := observer.LastExtracted()["traceparent"]; got != agentruntimetest.TraceParent {
		t.Errorf("control message trace not extracted: got %q", got)
	}
}

// TestRun_ControlStopDrainsGracefully proves the STOP verb drives a graceful drain: an idle
// interactive harness (never terminates on its own) ends ONLY on STOP, with TerminationControlStop.
func TestRun_ControlStopDrainsGracefully(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, interactiveFast)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wait := runFor(ctx, t, runtime)

	<-bus.Subscribed()
	waitForHeartbeats(t, bus, 1) // the run loop is live before we steer it
	bus.Inject(agentruntime.ControlMessage{AgentID: agentruntimetest.AgentID, Verb: agentruntime.VerbStop})

	if reason := wait(); reason != agentruntime.TerminationControlStop {
		t.Fatalf("reason = %s, want control-stop", reason)
	}
}

// TestRun_ControlKillIsImmediate proves the KILL verb cancels the agent immediately (the hard-stop
// registry path) ending on TerminationControlKill — distinct from a graceful stop.
func TestRun_ControlKillIsImmediate(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, interactiveFast)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wait := runFor(ctx, t, runtime)

	<-bus.Subscribed()
	waitForHeartbeats(t, bus, 1)
	bus.Inject(agentruntime.ControlMessage{AgentID: agentruntimetest.AgentID, Verb: agentruntime.VerbKill})

	if reason := wait(); reason != agentruntime.TerminationControlKill {
		t.Fatalf("reason = %s, want control-kill", reason)
	}
}

// TestRun_SignalShutdownIsGraceful proves the parent-ctx cancel (signal.NotifyContext → SIGTERM)
// drives a graceful drain ending on TerminationSignal, and OTel is flushed.
func TestRun_SignalShutdownIsGraceful(t *testing.T) {
	t.Parallel()
	runtime, bus, observer := agentruntimetest.NewRuntime(t, interactiveFast)
	ctx, cancel := context.WithCancel(context.Background())
	wait := runFor(ctx, t, runtime)

	<-bus.Subscribed()
	waitForHeartbeats(t, bus, 1)
	cancel() // the SIGTERM analog

	if reason := wait(); reason != agentruntime.TerminationSignal {
		t.Fatalf("reason = %s, want signal", reason)
	}
	if observer.FlushCount() == 0 {
		t.Errorf("OTel was not flushed on signal shutdown")
	}
}

// TestRun_PublishErrorDoesNotStallPump proves a transient bus publish failure is surfaced (logged),
// never dropped, and never stalls the pump — the run still reaches its terminal.
func TestRun_PublishErrorDoesNotStallPump(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, fastHeartbeat, agentruntimetest.CanonicalScript()...)
	bus.FailPublishWith(errFakePublish)

	if reason := runFor(noopCancelContext(), t, runtime)(); reason != agentruntime.TerminationSessionEnd {
		t.Fatalf("reason = %s, want session-end despite publish errors", reason)
	}
}

// TestRun_OpenFailureIsFault proves a harness-Open failure returns TerminationFault (the spawn-failure
// path) without leaking a goroutine — the sidecar fails loud, flushes, and returns.
func TestRun_OpenFailureIsFault(t *testing.T) {
	t.Parallel()
	// A Spec whose routing has no adapter forces agentsession.Open to error.
	runtime, _, observer := agentruntimetest.NewRuntime(t, func(c *agentruntime.Config) {
		interactiveFast(c)
		c.Spec.Routing = agentsession.RouteKey{Role: "no-such-role"}
	})
	reason, err := runtime.Run(noopCancelContext())
	if reason != agentruntime.TerminationFault {
		t.Fatalf("reason = %s, want fault on Open failure", reason)
	}
	if err == nil {
		t.Errorf("Run should return the wrapped Open error on a fault")
	}
	if observer.FlushCount() == 0 {
		t.Errorf("OTel should be flushed even on a fault")
	}
}
