package agentruntime_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
)

// This file re-pins the TWO libs-side consumer drain loops named by contract revision R1:
// runtime.go:132 (the sidecar pump) and advisor.go:313 (the one-shot reviewer drain). Both break
// on Event.IsTerminal() today, which was correct while a harness turn and a harness session were
// the same thing. Under R1 a clean `result`/`agent_end` ends only the TURN: the loops must break
// on the TURN BOUNDARY, then Close, then drain the session terminal the Close produces.
//
// The existing tests in this package are NOT wrong under R1 — their scripts hand the session a
// real EventResult, which stays terminal. They simply never exercise the path R1 creates, so the
// gap is covered here rather than by rewriting them.

// eventTurnEnd is the EventKind contract revision R1 APPENDS to the agentsession taxonomy — the
// member immediately after the current last one — spelled positionally so this file compiles
// BEFORE the constant exists. Its identity is pinned by the token assertion below.
const eventTurnEnd = agentsession.EventThinkingProgress + 1

// turnBoundary is one clean TURN end as a post-R1 adapter emits it: the per-turn authoritative
// ledger and the turn's final text, on an event that does NOT end the session.
func turnBoundary(text string) agentsession.Event {
	return agentsession.Event{
		Kind: eventTurnEnd,
		Terminal: &agentsession.TerminalPayload{
			Outcome: agentsession.TurnCompleted,
			Ledger: agentsession.TokenLedger{
				UsageMeter: agentsession.UsageMeter{
					Model: "fake-fable-5", Harness: "fake",
					InputTokens: 120, OutputTokens: 8, CostMicros: 13, Cumulative: true,
				},
				Turns: 1,
			},
			ResultText: text,
			StopReason: "end_turn",
		},
	}
}

// TestTurnBoundary_RendersTheAppendedToken pins the IDENTITY of the member this file addresses
// positionally, so a Round B that appends some OTHER member first fails loudly here instead of
// letting the drain tests below quietly exercise the wrong kind.
func TestTurnBoundary_RendersTheAppendedToken(t *testing.T) {
	t.Parallel()
	if got := eventTurnEnd.String(); got != "turn-end" {
		t.Errorf("the EventKind appended after %s renders %q, want \"turn-end\" — the R1 turn-boundary member is not in the taxonomy yet",
			agentsession.EventThinkingProgress, got)
	}
}

// TestRun_TurnBoundaryEndsTheRunAndTheSessionTerminalReachesTheBus re-pins runtime.go:132. A
// harness that ends its TURN and stays alive must still drive the sidecar to a clean
// session-end: the pump breaks on the boundary, Closes the session, and publishes the terminal
// the Close produces — so the B5 gateway's replay still ends on a terminal.
//
// Today the pump only breaks on IsTerminal(), so it blocks on a session that is alive and
// waiting for its next Prompt: Run never returns and the sidecar hangs on a healthy agent.
func TestRun_TurnBoundaryEndsTheRunAndTheSessionTerminalReachesTheBus(t *testing.T) {
	t.Parallel()
	runtime, bus, _ := agentruntimetest.NewRuntime(t, fastHeartbeat,
		scriptedMessageStart(),
		scriptedTextDelta("the answer"),
		turnBoundary("the answer"),
	)

	reason := runBounded(t, runtime, 3*time.Second)
	if reason != agentruntime.TerminationSessionEnd {
		t.Fatalf("termination reason = %s, want session-end", reason)
	}

	events := bus.Events()
	if len(events) == 0 {
		t.Fatal("no events reached the bus")
	}
	if !busCarriesTurnBoundary(events) {
		t.Errorf("no turn-boundary event reached the bus; the turn's own ledger and result text were never published")
	}
	if last := events[len(events)-1]; !last.Event.IsTerminal() {
		t.Errorf("the last published event is %s, not a terminal; Close must produce the session terminal the replay ends on",
			last.Event.Kind)
	}
}

// TestAdvisor_ReadsTheVerdictOffTheTurnBoundary re-pins advisor.go:313. The reviewer's verdict is
// the authoritative FINAL TEXT of its turn — for claude that is the `result` line, not a text
// delta — so the drain must read it off the turn boundary. Here the reviewer streams only its
// reasoning and puts the verdict where a real harness puts it.
//
// Today the drain does not recognize the boundary, waits out the whole adjudication budget, finds
// no accumulated text, and FAILS SAFE TO DENY — so a reviewer that clearly voted allow is
// recorded as a deny. That is a correctness failure, not just a slow one.
func TestAdvisor_ReadsTheVerdictOffTheTurnBoundary(t *testing.T) {
	t.Parallel()
	const verdict = "VERDICT: allow\nSCOPE: session\nRATIONALE: reading a doc is read-only and in the spirit of the goal"
	factory := newRecordingFactory(t,
		scriptedMessageStart(),
		scriptedThinkingDelta("weighing the request against the session goal"),
		turnBoundary(verdict),
	)
	advisor := newFastAdvisor(t, factory)

	decision, err := advisor.Advise(context.Background(), sampleRequest(), sampleAdvice())
	if err != nil {
		t.Fatalf("Advise returned an error: %v", err)
	}
	if !decision.Allow {
		t.Errorf("decision.Allow = false, want true — the reviewer's verdict rode the TURN BOUNDARY's result text and the drain never read it (rationale=%q)",
			decision.Rationale)
	}
	if decision.Scope != agentsession.ScopeSession {
		t.Errorf("decision.Scope = %s, want session (the verdict asked for a session-scoped allow)", decision.Scope)
	}
	if !strings.Contains(decision.By, "advisor:") {
		t.Errorf("decision.By = %q, want an advisor:<name> stamp", decision.By)
	}
}

// ── helpers ──────────────────────────────────────────────────────────────────────────────.

// runBounded drives Run and waits for its reason, canceling the run if it does not end on its
// own within the bound. The cancellation is what keeps a regression from leaking the pump
// goroutine into goleak's verifier, which would bury the real failure under a leak report.
func runBounded(t *testing.T, runtime *agentruntime.Runtime, bound time.Duration) agentruntime.TerminationReason {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan agentruntime.TerminationReason, 1)
	go func() {
		reason, err := runtime.Run(ctx)
		if err != nil {
			t.Errorf("Run returned an error: %v", err)
		}
		done <- reason
	}()
	select {
	case reason := <-done:
		return reason
	case <-time.After(bound):
		cancel()
		<-done // unwind the run so no goroutine outlives the test
		t.Fatalf("Run did not end within %s after the harness ended its TURN: the pump is still waiting for a session terminal on a session that is alive and awaiting its next Prompt",
			bound)
		return agentruntime.TerminationUnknown
	}
}

// busCarriesTurnBoundary reports whether a turn-boundary event (a non-terminal event carrying the
// turn's TerminalPayload) reached the bus.
func busCarriesTurnBoundary(events []agentruntime.EventEnvelope) bool {
	for i := range events {
		event := events[i].Event
		if event.Terminal != nil && !event.IsTerminal() {
			return true
		}
	}
	return false
}

// newFastAdvisor builds an Advisor with a SHORT adjudication budget, so the today-failing path
// (the drain waiting out the whole budget) reports in about a second instead of five.
func newFastAdvisor(t *testing.T, factory agentsession.Factory) *agentruntime.Advisor {
	t.Helper()
	advisor, err := agentruntime.NewAdvisor(
		agentruntime.AdvisorConfig{
			ReviewerRoute:      reviewerRoute,
			ReviewerWorkspace:  "/workspace/reviewer",
			ReviewerCredential: secrets.Ref(reviewerCredentialRef),
			WallClock:          time.Second,
			MaxCostMicros:      40_000,
			MaxTurns:           2,
		},
		agentruntime.AdvisorDeps{
			Sessions: factory,
			Observer: agentruntimetest.NewFakeObserver(),
			Clock:    agentruntimetest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("NewAdvisor: %v", err)
	}
	return advisor
}

// scriptedMessageStart / TextDelta / ThinkingDelta build the scripted lead-in events. They
// are spelled here rather than pulled from agentsessiontest so this file states the exact turn
// shape it depends on.
func scriptedMessageStart() agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventMessageStart,
		Message: &agentsession.MessagePayload{Role: "assistant"},
	}
}

func scriptedTextDelta(delta string) agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventTextDelta,
		Message: &agentsession.MessagePayload{Role: "assistant", Delta: delta},
	}
}

func scriptedThinkingDelta(delta string) agentsession.Event {
	return agentsession.Event{
		Kind:    agentsession.EventThinkingDelta,
		Message: &agentsession.MessagePayload{Role: "assistant", Delta: delta},
	}
}
