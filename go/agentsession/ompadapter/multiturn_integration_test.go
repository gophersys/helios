//go:build integration

// The MULTI-TURN half of the omp adapter's host-leveraging lane (ADR-0020 dimension (d)) for
// contract revision R1: THREE consecutive Prompts on ONE agentsession.Session over ONE
// processConn, driving THREE real stub-harness executions — omp's headless json mode is
// one-shot per turn, so the per-turn exec model is the thing under test and it is driven for
// real, never mocked.
//
//	go test -tags integration ./ -race -count=1 -run TestIntegration_StubBinary_ThreeConsecutivePrompts
//
// The shared REAL-subprocess scaffolding (fakeCanary, vaultReference, buildStub, newPool,
// integrationClock, readyObserved) lives in harness_helpers_test.go; turnEndToken lives in
// turnend_test.go, the untagged file that pins the parser half of the same revision.
package ompadapter_test

import (
	"bytes"
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets"
)

// multiTurnCount is the number of consecutive Prompts one session must serve. Three, not two:
// two proves only that a second turn is admitted, while three proves the turn ordinal keeps
// advancing and no once-per-process latch is hiding behind the first follow-up.
const multiTurnCount = 3

// multiTurnDeadline bounds the whole three-turn exchange. Three stub execs are ~1.5s of paced
// output apiece, so a generous bound still fails fast rather than hanging the lane.
const multiTurnDeadline = 90 * time.Second

// TestIntegration_StubBinary_ThreeConsecutivePromptsOnOneSession is the R1 exit proof for the
// omp adapter on a REAL process: one Open, one conn, three Prompts, three stub executions, and
// the session alive throughout.
//
// It asserts, on the genuine subprocess stream:
//
//	(a) three TURN boundaries — one per Prompt, each carrying its own turn's ledger and its own
//	    echoed prompt text (the stub echoes its last positional argv, so identical text across
//	    boundaries would mean one exec answered twice);
//	(b) turn ordinals 0, 1 and 2 — the pump advances the ordinal on the AwaitingInput->Running
//	    edge a follow-up Prompt draws, an edge no adapter could reach before R1;
//	(c) ZERO session terminals before Close — a turn boundary ends a TURN;
//	(d) ONE Stream opened at Seq 0 BEFORE the first Prompt delivers all three turns gap-free —
//	    a viewer attached at the start does not lose the session at the first turn boundary;
//	(e) three stub EXECUTIONS on ONE conn — three `session` + three `agent_start` frames, each
//	    surfaced as EventExtension, and the Ready handshake NOT re-fired by any of them;
//	(f) the requested Close then produces the session's ONE terminal, an EventResult;
//	(g) the credential canary never leaks, across all three turns.
//
// Today it fails at the SECOND Prompt: turn one's `agent_end` normalizes to the session-terminal
// EventResult, the pump latches a terminal State, and guardControl refuses the follow-up. That
// is the R1 defect exactly — an eden omp session cannot take a second turn, so a
// receive-then-reply peer exchange is impossible.
func TestIntegration_StubBinary_ThreeConsecutivePromptsOnOneSession(t *testing.T) {
	t.Parallel()
	stub := buildStub(t)
	pool := newPool(t, ompadapter.MustNewForTest(t, ompadapter.Config{Binary: stub}))

	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-read", Tool: "read", ReadOnly: true}},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		t.Fatalf("Open over the stub subprocess: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	ctx, cancel := context.WithTimeout(context.Background(), multiTurnDeadline)
	defer cancel()

	// ONE stream, opened at Seq 0 BEFORE the first Prompt, read across every turn: assertion (d).
	stream := session.Events(ctx, agentsession.FromSeq(0))

	log := &turnLog{}
	for turn := range multiTurnCount {
		prompt := fmt.Sprintf("turn-%d-prompt", turn)
		if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: prompt}); err != nil {
			t.Fatalf("Prompt %d of %d was refused: %v — ONE omp session did not survive turn %d (R1: an agent_end ends the TURN and parks the session in %v, where Prompt is already legal)",
				turn+1, multiTurnCount, err, turn, agentsession.StateAwaitingInput)
		}
		log.readThroughBoundary(t, ctx, stream, turn+1)
	}

	// The session is still alive after three turns; the deliberate Close is what ends it.
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("Close after %d turns: %v", multiTurnCount, err)
	}
	log.readToStreamEnd(ctx, stream)

	assertThreeDistinctBoundaries(t, log.boundaries)
	assertTurnOrdinalsAdvance(t, log.events)
	assertThreeExecsAndOneReady(t, log.events, log.firstBoundarySeq)
	assertSoleTerminalIsTheRequestedClose(t, log.events)
	assertMultiTurnSeqAndNoLeak(t, log.events)
}

// turnLog accumulates the ONE stream's whole event log plus the per-turn boundary events, so
// every assertion below reads the same recording rather than re-draining the session.
type turnLog struct {
	events           []agentsession.Event
	boundaries       []agentsession.Event
	firstBoundarySeq uint64
}

// readThroughBoundary reads the live tail up to and including turn n's boundary — the event
// carrying that turn's TerminalPayload. A SESSION terminal reached here is the pre-R1 defect and
// fails immediately (assertion (c)); a stream that ends here means the session died at a turn
// boundary (assertion (d)).
func (l *turnLog) readThroughBoundary(t *testing.T, ctx context.Context, stream agentsession.Stream, turn int) { //nolint:revive // ctx-after-t mirrors the other stream helpers in this package's lanes.
	t.Helper()
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("the ONE stream opened at Seq 0 ended during turn %d of %d (%d event(s) read): %v — a viewer attached before the first Prompt must survive every turn boundary",
				turn, multiTurnCount, len(l.events), stream.Err())
		}
		l.events = append(l.events, event)
		if event.Terminal == nil {
			continue
		}
		l.boundaries = append(l.boundaries, event)
		if l.firstBoundarySeq == 0 {
			l.firstBoundarySeq = event.Seq
		}
		// The boundary is recorded either way, and the terminality is an Errorf rather than a
		// Fatalf, so the run goes on to attempt the NEXT Prompt: a session latched terminal here
		// refuses it, and both halves of the defect are on the record instead of only the first.
		if event.IsTerminal() {
			t.Errorf("turn %d of %d ended the SESSION on a %s terminal (detail=%q) — an agent_end that reports a clean stop is a TURN boundary; the omp PROCESS exits, the SESSION does not",
				turn, multiTurnCount, event.Kind, terminalDetailOf(event))
		}
		return
	}
}

// readToStreamEnd drains whatever the requested Close appended, so the terminal assertion reads
// the complete recording. The stream ends when the fan-out closes.
func (l *turnLog) readToStreamEnd(ctx context.Context, stream agentsession.Stream) {
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return
		}
		l.events = append(l.events, event)
	}
}

// assertThreeDistinctBoundaries proves assertion (a): one boundary per Prompt, each a turn-end
// rather than a session terminal, each carrying its own turn's ledger and its own echoed prompt.
func assertThreeDistinctBoundaries(t *testing.T, boundaries []agentsession.Event) {
	t.Helper()
	if len(boundaries) != multiTurnCount {
		t.Fatalf("%d turn boundaries across %d Prompts, want %d", len(boundaries), multiTurnCount, multiTurnCount)
	}
	seen := make(map[string]int, multiTurnCount)
	for i := range boundaries {
		boundary := &boundaries[i]
		if got := boundary.Kind.String(); got != turnEndToken {
			t.Errorf("turn %d boundary token = %q, want %q", i+1, got, turnEndToken)
		}
		if boundary.Terminal.Ledger.Harness != "omp" {
			t.Errorf("turn %d boundary ledger lost the omp attribution: %+v", i+1, boundary.Terminal.Ledger)
		}
		if boundary.Terminal.Ledger.InputTokens == 0 || boundary.Terminal.Ledger.OutputTokens == 0 {
			t.Errorf("turn %d boundary carries no per-turn accounting: %+v", i+1, boundary.Terminal.Ledger)
		}
		seen[boundary.Terminal.ResultText]++
	}
	if len(seen) != multiTurnCount {
		t.Errorf("the %d turn boundaries carried %d distinct result texts (%v); the stub echoes its own invocation's prompt, so a repeat means one exec answered twice",
			multiTurnCount, len(seen), seen)
	}
}

// assertTurnOrdinalsAdvance proves assertion (b): the pump stamped turn ordinals 0, 1 and 2.
func assertTurnOrdinalsAdvance(t *testing.T, events []agentsession.Event) {
	t.Helper()
	present := make(map[int]bool, multiTurnCount)
	highest := -1
	for i := range events {
		present[events[i].Turn] = true
		if events[i].Turn > highest {
			highest = events[i].Turn
		}
	}
	for ordinal := range multiTurnCount {
		if !present[ordinal] {
			t.Errorf("no event carried turn ordinal %d; the per-turn ordinal is not advancing across the %d turns (highest seen: %d)",
				ordinal, multiTurnCount, highest)
		}
	}
	if highest != multiTurnCount-1 {
		t.Errorf("the turn ordinal reached %d across %d turns, want %d", highest, multiTurnCount, multiTurnCount-1)
	}
}

// assertThreeExecsAndOneReady proves assertion (e): three stub EXECUTIONS rode one conn — three
// `session` and three `agent_start` startup frames, each preserved as an opaque EventExtension —
// and none of them re-fired the Ready handshake the library's Open already consumed.
func assertThreeExecsAndOneReady(t *testing.T, events []agentsession.Event, firstBoundarySeq uint64) {
	t.Helper()
	for _, frameType := range []string{"session", "agent_start"} {
		if got := countExtensionFrames(events, frameType); got != multiTurnCount {
			t.Errorf("%d %q startup frames surfaced as EventExtension, want %d — one per stub exec, each preserved verbatim on the ONE conn",
				got, frameType, multiTurnCount)
		}
	}
	for i := range events {
		event := &events[i]
		if event.Kind != agentsession.EventSessionState || event.State == nil || event.State.To != agentsession.StateReady {
			continue
		}
		if event.Seq > firstBoundarySeq {
			t.Errorf("a Ready transition was published at Seq %d, after turn 1's boundary at Seq %d — a per-turn omp exec's `session`/`agent_start` frame must stay an Extension and never re-open the handshake",
				event.Seq, firstBoundarySeq)
		}
	}
}

// assertSoleTerminalIsTheRequestedClose proves assertion (f): the session carries exactly ONE
// terminal for its whole life, and it is the EventResult the deliberate Close produced.
func assertSoleTerminalIsTheRequestedClose(t *testing.T, events []agentsession.Event) {
	t.Helper()
	var terminals []agentsession.Event
	for i := range events {
		if events[i].IsTerminal() {
			terminals = append(terminals, events[i])
		}
	}
	if len(terminals) != 1 {
		t.Fatalf("%d terminal events across a %d-turn session, want exactly 1 (the requested Close)", len(terminals), multiTurnCount)
	}
	terminal := &terminals[0]
	if terminal.Kind != agentsession.EventResult {
		t.Errorf("the requested Close produced %s (detail=%q), want result — a deliberate reap of a healthy session is not a fault",
			terminal.Kind, terminalDetailOf(*terminal))
	}
	if terminal.Terminal == nil || terminal.Terminal.Outcome != agentsession.TurnCompleted {
		t.Errorf("requested-close payload = %+v, want Outcome TurnCompleted", terminal.Terminal)
	}
}

// assertMultiTurnSeqAndNoLeak proves assertion (d)'s gap-free half and (g): the ONE stream
// delivered Seq 1..N with no gap across all three turns, and the credential canary never leaked.
func assertMultiTurnSeqAndNoLeak(t *testing.T, events []agentsession.Event) {
	t.Helper()
	var prev uint64
	for i := range events {
		if events[i].Seq != prev+1 {
			t.Fatalf("event %d Seq = %d, want %d — the multi-turn stream has a gap", i, events[i].Seq, prev+1)
		}
		prev = events[i].Seq
	}
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], fakeCanary)
	}
}

// countExtensionFrames counts the EventExtension events whose preserved raw frame declares the
// given top-level omp type.
func countExtensionFrames(events []agentsession.Event, frameType string) int {
	needle := []byte(`"type":"` + frameType + `"`)
	count := 0
	for i := range events {
		if events[i].Kind == agentsession.EventExtension && bytes.Contains(events[i].Extension, needle) {
			count++
		}
	}
	return count
}

// terminalDetailOf renders a terminal event's detail for a failure message, or "" when absent.
func terminalDetailOf(event agentsession.Event) string { //nolint:gocritic // Event is the contract's copyable value record (§2).
	if event.Terminal == nil {
		return ""
	}
	return event.Terminal.Detail
}
