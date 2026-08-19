package agentsession_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// This file pins the TURN half of contract revision R1: a session survives its own turn, and
// the (state x command) legality matrix does NOT move to make that true.
//
// The matrix guard is load-bearing in the negative direction. R1's blast radius is that
// StateAwaitingInput finally becomes REACHABLE on a real adapter, which puts
// LegalControls(AwaitingInput) = {Prompt, Abort} into live service for the first time. That is
// the one cell R1 is allowed to exercise — and not one cell of the matrix may change to let it.

// TestLegalControls_MatrixIsByteStableAcrossEveryState pins the WHOLE (state x command) matrix
// as literal data, so R1 cannot buy multi-turn by loosening a legality cell — most temptingly
// by admitting Prompt in StateRunning, which would let a follow-up prompt "work" while a turn
// is still in flight. It passes today and must keep passing byte-for-byte.
func TestLegalControls_MatrixIsByteStableAcrossEveryState(t *testing.T) {
	t.Parallel()
	// The expected sets, in CommandKind (iota) order, written out independently of the
	// implementation. Every one of the 8 states is present: a missing row would silently
	// narrow the guard.
	want := []struct {
		state agentsession.State
		legal []agentsession.CommandKind
	}{
		{agentsession.StateInitializing, []agentsession.CommandKind{agentsession.CommandAbort}},
		{agentsession.StateReady, []agentsession.CommandKind{agentsession.CommandPrompt, agentsession.CommandAbort}},
		{agentsession.StateRunning, []agentsession.CommandKind{agentsession.CommandSteer, agentsession.CommandAbort}},
		{agentsession.StateAwaitingInput, []agentsession.CommandKind{agentsession.CommandPrompt, agentsession.CommandAbort}},
		{agentsession.StateAwaitingPermission, []agentsession.CommandKind{agentsession.CommandAbort}},
		{agentsession.StateCompleted, nil},
		{agentsession.StateFailed, nil},
		{agentsession.StateAborted, nil},
	}
	if len(want) != 8 {
		t.Fatalf("the matrix guard covers %d states, want all 8", len(want))
	}
	for _, row := range want {
		got := agentsession.LegalControls(row.state)
		if len(got) != len(row.legal) {
			t.Errorf("LegalControls(%v) = %v, want %v (the legality matrix moved)", row.state, tokensOf(got), tokensOf(row.legal))
			continue
		}
		for i := range got {
			if got[i] != row.legal[i] {
				t.Errorf("LegalControls(%v)[%d] = %v, want %v (order is the wire projection the UI keys off)",
					row.state, i, got[i], row.legal[i])
			}
		}
	}
}

// TestTurnEnd_RendersTheAppendedTurnBoundaryToken pins the IDENTITY of the appended member.
// Every multi-turn test in this package spells the turn-boundary kind positionally (see
// eventTurnEnd in terminal_test.go) so the suite compiles before the constant exists; this test
// is what stops that from silently testing the wrong member. It fails today because nothing is
// declared at the ordinal yet, so String() falls back to the "extension" token.
func TestTurnEnd_RendersTheAppendedTurnBoundaryToken(t *testing.T) {
	t.Parallel()
	if got := eventTurnEnd.String(); got != "turn-end" {
		t.Errorf("the EventKind appended after %s renders %q, want \"turn-end\" — the R1 turn-boundary member and its token row are not in the taxonomy yet",
			agentsession.EventThinkingProgress, got)
	}
	if eventTurnEnd.String() == agentsession.EventExtension.String() {
		t.Errorf("the turn-boundary kind renders the same token as EventExtension (%q): it has no token row of its own",
			agentsession.EventExtension)
	}
	// A turn boundary is NOT a session terminal — that is the whole revision.
	if (agentsession.Event{Kind: eventTurnEnd}).IsTerminal() {
		t.Errorf("the turn-boundary kind must NOT satisfy IsTerminal(); Event.IsTerminal stays {Result, Failed, Aborted}")
	}
}

// TestTurn_OrdinalReachesTwoAcrossThreeFoldedTurns is the R1 multi-turn proof at the library
// level: three consecutive Prompts on ONE session, each answered by its own turn body, must
// carry turn ordinals 0, 1 and 2 with a distinct TurnID each.
//
// Today it fails at the SECOND Prompt. The turn-boundary event implies no lifecycle transition,
// so the session is still StateRunning when the follow-up arrives and guardControl rejects it
// with a StateError — which is exactly the defect: a claude/omp session cannot take a second
// turn, so a receive-then-reply exchange is impossible.
func TestTurn_OrdinalReachesTwoAcrossThreeFoldedTurns(t *testing.T) {
	t.Parallel()
	const turns = 3
	conn := newTurnConn(
		gracefulClose,
		turnBody("first turn answer"),
		turnBody("second turn answer"),
		turnBody("third turn answer"),
	)
	session, transcriptEvents := openScriptedSession(t, conn)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for turn := range turns {
		if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "prompt"}); err != nil {
			t.Fatalf("Prompt %d of %d was refused: %v — the session did not survive turn %d (R1: a turn boundary parks the session in %v, it does not end it)",
				turn+1, turns, err, turn, agentsession.StateAwaitingInput)
		}
		readThroughTurnBoundary(ctx, t, stream, turn+1)
	}
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("Close: %v", err)
	}

	ordinals, identifiers := turnOrdinalsAndIdentifiers(transcriptEvents())
	if got := maxOrdinal(ordinals); got != turns-1 {
		t.Errorf("the turn ordinal reached %d across %d turns, want %d (ordinals seen: %v)", got, turns, turns-1, ordinals)
	}
	for ordinal := range turns {
		if !ordinals[ordinal] {
			t.Errorf("no event carried turn ordinal %d; the per-turn ordinal is not advancing across turns", ordinal)
		}
	}
	if len(identifiers) < turns {
		t.Errorf("%d distinct TurnIDs across %d turns (%v); each turn must correlate under its own id",
			len(identifiers), turns, identifiers)
	}
}

// TestTurn_PermissionFirstTurnKeepsItsOwnOrdinal pins the ordinal against the ONE turn shape
// that does not open with an assistant message: a turn whose first harness event is a
// permission ask (the tool-first opening move — "read the file before you answer" — that both
// shipped harnesses emit).
//
// The ordinal advances on the AwaitingInput->Running edge an admitted Prompt draws, and the
// arming that identifies that edge is consumed by EVERY Running edge. A permission-first turn
// draws AwaitingInput->AwaitingPermission->Running instead, so the arming is spent on the
// SECOND edge, whose prior state is AwaitingPermission — the turn is never counted. Three
// admitted Prompts then report ordinals 0,0,1 with only two distinct TurnIDs, and every event
// of the middle turn is filed under the previous turn's correlation id: the exact silent
// mis-attribution the per-turn ordinal exists to prevent.
func TestTurn_PermissionFirstTurnKeepsItsOwnOrdinal(t *testing.T) {
	t.Parallel()
	const turns = 3
	conn := newTurnConn(
		gracefulClose,
		turnBody("first turn answer"),
		permissionFirstTurnBody("second turn answer"),
		turnBody("third turn answer"),
	)
	session, transcriptEvents := openScriptedSession(t, conn)

	promptEveryTurn(t, session, turns)
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("Close: %v", err)
	}

	ordinals, identifiers := turnOrdinalsAndIdentifiers(transcriptEvents())
	if got := maxOrdinal(ordinals); got != turns-1 {
		t.Errorf("the turn ordinal reached %d across %d admitted Prompts, want %d (ordinals seen: %v) — the permission-first turn spent its arming on the %v->%v edge and was never counted",
			got, turns, turns-1, ordinals, agentsession.StateAwaitingPermission, agentsession.StateRunning)
	}
	for ordinal := range turns {
		if !ordinals[ordinal] {
			t.Errorf("no event carried turn ordinal %d; a turn folded into its predecessor's ordinal", ordinal)
		}
	}
	if len(identifiers) != turns {
		t.Errorf("%d distinct TurnIDs across %d turns (%v); a permission-first turn must correlate under its OWN id, not its predecessor's",
			len(identifiers), turns, identifiers)
	}
}

// TestTurn_FollowUpPromptIsLegalAfterATurnBoundary isolates the single lifecycle edge R1 adds:
// once a turn boundary has been folded, the session must be parked in StateAwaitingInput, where
// LegalControls already declares Prompt legal. Today the boundary implies no transition, the
// session is still Running, and the follow-up Prompt is a typed StateError naming that state —
// a state the frozen contract has always documented as "turn complete, awaiting the next
// Prompt" but that no adapter could ever reach.
func TestTurn_FollowUpPromptIsLegalAfterATurnBoundary(t *testing.T) {
	t.Parallel()
	conn := newTurnConn(gracefulClose, turnBody("first"), turnBody("second"))
	session, _ := openScriptedSession(t, conn)

	promptAndAwaitTurnBoundary(t, session)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "follow up"})
	if err == nil {
		return
	}
	stateError, ok := errors.AsType[agentsession.StateError](err)
	if !ok {
		t.Fatalf("follow-up Prompt failed with a non-StateError: %v (%T)", err, err)
	}
	t.Errorf("a follow-up Prompt after a turn boundary was refused in state %v: %v — R1 parks the session in %v, where Prompt is already declared legal",
		stateError.From, err, agentsession.StateAwaitingInput)
}

// ── helpers ──────────────────────────────────────────────────────────────────────────────.

// permissionFirstTurnBody is turnBody preceded by a permission round-trip, so the turn's FIRST
// harness event is the ask rather than the assistant message.
//
// The request deliberately carries NO PermissionPayload: a payload would send the pump down the
// resolution chain (advisor consult / pending human timer), which has nothing to do with the
// ordinal. With a nil payload the pump publishes the ask verbatim, and the ONLY thing under test
// is the lifecycle detour it forces — AwaitingInput->AwaitingPermission->Running.
func permissionFirstTurnBody(text string) []agentsession.Event {
	return append([]agentsession.Event{
		{Kind: agentsession.EventPermissionRequest},
		{Kind: agentsession.EventPermissionResolved},
	}, turnBody(text)...)
}

// readThroughTurnBoundary reads the live tail up to and including turn n's boundary event (the
// one carrying that turn's TerminalPayload), so the next Prompt is issued in the right phase.
func readThroughTurnBoundary(ctx context.Context, t *testing.T, stream agentsession.Stream, turn int) {
	t.Helper()
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("the stream ended during turn %d: %v — the session terminated at a TURN boundary", turn, stream.Err())
		}
		if event.IsTerminal() {
			t.Fatalf("turn %d ended the SESSION (terminal %s); a turn boundary must not be terminal", turn, event.Kind)
		}
		if event.Terminal != nil {
			return
		}
	}
}

// turnOrdinalsAndIdentifiers projects the distinct turn ordinals and TurnIDs the recorded
// session carried.
func turnOrdinalsAndIdentifiers(events []agentsession.Event) (ordinals map[int]bool, identifiers map[string]bool) {
	ordinals = make(map[int]bool)
	identifiers = make(map[string]bool)
	for i := range events {
		ordinals[events[i].Turn] = true
		if events[i].TurnID != "" {
			identifiers[events[i].TurnID] = true
		}
	}
	return ordinals, identifiers
}

// maxOrdinal returns the highest turn ordinal observed (-1 for none).
func maxOrdinal(ordinals map[int]bool) int {
	highest := -1
	for ordinal := range ordinals {
		if ordinal > highest {
			highest = ordinal
		}
	}
	return highest
}

// tokensOf renders a command set as its stable wire tokens for a failure message.
func tokensOf(commands []agentsession.CommandKind) []string {
	out := make([]string, 0, len(commands))
	for _, command := range commands {
		out = append(out, command.String())
	}
	return out
}
