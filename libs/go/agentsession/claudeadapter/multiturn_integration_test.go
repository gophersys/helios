//go:build integration

// The MULTI-TURN half of the claude adapter's host-leveraging lane (ADR-0020 dimension (d)) for
// contract revision R1: THREE consecutive Prompts on ONE agentsession.Session over ONE
// os/exec stub-harness PROCESS. Real claude's stream-json input mode keeps one process alive
// across a whole exchange — it reads a {"type":"user"} turn off stdin and answers it with one
// `result` line, then reads the next — so the turn-driven stub is driven the same way and the
// one-process/many-turns model is proven on a genuine subprocess, never mocked.
//
//	go test -tags integration ./ -race -count=1 -run TestIntegration_StubBinary_ThreeConsecutivePrompts
//
// The shared REAL-subprocess scaffolding (fakeCanary, buildStub, newPool, integrationClock)
// lives in integration_test.go; turnEndToken lives in turnend_test.go, the untagged file that
// pins the parser half of the same revision.
package claudeadapter_test

import (
	"bytes"
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets"
)

// multiTurnCount is the number of consecutive Prompts one session must serve. Three, not two:
// two proves only that a second turn is admitted, while three proves the turn ordinal keeps
// advancing and no once-per-process latch is hiding behind the first follow-up.
const multiTurnCount = 3

// multiTurnDeadline bounds the whole three-turn exchange on one real process, so a regression
// fails fast instead of hanging the lane.
const multiTurnDeadline = 90 * time.Second

// TestIntegration_StubBinary_ThreeConsecutivePromptsOnOneProcess is the R1 exit proof for the
// claude adapter on a REAL process: one Open, one process, three Prompts, and the session alive
// throughout.
//
// It asserts, on the genuine subprocess stream:
//
//	(a) three TURN boundaries — one per Prompt, each carrying its own turn's ledger and its own
//	    echoed prompt text (the stub weaves the turn's prompt into its `result`, so identical
//	    text across boundaries would mean one turn was replayed rather than three answered);
//	(b) turn ordinals 0, 1 and 2 — the pump advances the ordinal on the AwaitingInput->Running
//	    edge a follow-up Prompt draws, an edge no adapter could reach before R1;
//	(c) ZERO session terminals before Close — a `result` line ends a TURN;
//	(d) ONE Stream opened at Seq 0 BEFORE the first Prompt delivers all three turns gap-free —
//	    a viewer attached at the start does not lose the session at the first turn boundary;
//	(e) ONE process served all three — the once-per-session `system/init` line appears EXACTLY
//	    once while the per-turn `rate_limit_event` appears three times, so a respawn (which would
//	    re-emit init) is excluded, and the three turns carry three distinct tool call ids;
//	(f) the requested Close then produces the session's ONE terminal, an EventResult;
//	(g) the credential canary never leaks, across all three turns.
//
// Today it fails at turn one's boundary and then at the SECOND Prompt: the success `result`
// normalizes to the session-terminal EventResult, the pump latches a terminal State, and
// guardControl refuses the follow-up. That is the R1 defect exactly — an eden claude session
// cannot take a second turn, so a receive-then-reply peer exchange is impossible.
func TestIntegration_StubBinary_ThreeConsecutivePromptsOnOneProcess(t *testing.T) {
	t.Parallel()
	stub := buildStub(t)
	pool := newPool(t, claudeadapter.MustNewForTest(t, claudeadapter.Config{Binary: stub}))

	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-write", Tool: "Write"}},
		Credential: secrets.Ref("vault://eden/anthropic#setup-token"),
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
			t.Fatalf("Prompt %d of %d was refused: %v — ONE claude process did not survive turn %d (R1: a `result` line ends the TURN and parks the session in %v, where Prompt is already legal)",
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
	assertOneProcessServedEveryTurn(t, log.events)
	assertSoleTerminalIsTheRequestedClose(t, log.events)
	assertMultiTurnSeqAndNoLeak(t, log.events)
}

// turnLog accumulates the ONE stream's whole event log plus the per-turn boundary events, so
// every assertion below reads the same recording rather than re-draining the session.
type turnLog struct {
	events     []agentsession.Event
	boundaries []agentsession.Event
}

// readThroughBoundary reads the live tail up to and including turn n's boundary — the event
// carrying that turn's TerminalPayload. A stream that ends here means the session died at a turn
// boundary (assertion (d)); a boundary that is a SESSION terminal is the pre-R1 defect
// (assertion (c)).
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
		// The boundary is recorded either way, and the terminality is an Errorf rather than a
		// Fatalf, so the run goes on to attempt the NEXT Prompt: a session latched terminal here
		// refuses it, and both halves of the defect are on the record instead of only the first.
		if event.IsTerminal() {
			t.Errorf("turn %d of %d ended the SESSION on a %s terminal (detail=%q) — a success `result` is a TURN boundary; real claude emits one per turn and keeps reading stdin",
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
		if boundary.Terminal.Ledger.Harness != "claude-code" {
			t.Errorf("turn %d boundary ledger lost the claude-code attribution: %+v", i+1, boundary.Terminal.Ledger)
		}
		if boundary.Terminal.Ledger.InputTokens == 0 || boundary.Terminal.Ledger.OutputTokens == 0 {
			t.Errorf("turn %d boundary carries no per-turn accounting: %+v", i+1, boundary.Terminal.Ledger)
		}
		seen[boundary.Terminal.ResultText]++
	}
	if len(seen) != multiTurnCount {
		t.Errorf("the %d turn boundaries carried %d distinct result texts (%v); the stub weaves each turn's own prompt into its `result`, so a repeat means one turn was replayed",
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

// assertOneProcessServedEveryTurn proves assertion (e). The stub emits `system/init` ONCE per
// PROCESS and a `rate_limit_event` once per TURN, so one init beside three rate-limit frames is
// the measurement that three turns rode ONE process rather than three respawns. The three
// distinct tool call ids are the corroborating half: each turn ran its own tool call.
func assertOneProcessServedEveryTurn(t *testing.T, events []agentsession.Event) {
	t.Helper()
	if got := countExtensionFrames(events, `"subtype":"init"`); got != 1 {
		t.Errorf("%d `system/init` lines surfaced, want exactly 1 — claude emits it once per PROCESS, so more than one means the session respawned instead of taking the next turn on the live one",
			got)
	}
	if got := countExtensionFrames(events, `"type":"rate_limit_event"`); got != multiTurnCount {
		t.Errorf("%d per-turn `rate_limit_event` frames surfaced as EventExtension, want %d — one per turn, each preserved verbatim through the real pipe",
			got, multiTurnCount)
	}
	calls := make(map[string]bool, multiTurnCount)
	for i := range events {
		if events[i].Kind == agentsession.EventToolStart && events[i].Tool != nil {
			calls[events[i].Tool.CallID] = true
		}
	}
	if len(calls) != multiTurnCount {
		t.Errorf("%d distinct tool call ids across %d turns (%v); each turn runs its own tool call on the one process",
			len(calls), multiTurnCount, calls)
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

// countExtensionFrames counts the EventExtension events whose preserved raw frame carries the
// given verbatim json fragment.
func countExtensionFrames(events []agentsession.Event, fragment string) int {
	needle := []byte(fragment)
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
