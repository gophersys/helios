//go:build lifecycle

package agentsession_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentsession"
)

// This is the ADR-0020 dimension (c) arm for contract revision R1. The existing lifecycle probe
// drives a harness that hands the session a real EventResult — a SESSION terminal, which R1
// leaves exactly as it is — so it never reaches the shape R1 creates: a harness that ends only
// its TURN and stays alive, waiting for the next Prompt. That is the session Close now has to
// reap, and the one whose terminal Close now has to produce.
//
// It shares the scripted conn with terminal_test.go (an untagged file, so it compiles into this
// lane too), which keeps ONE definition of what a post-R1 turn looks like.

// TestLifecycle_TurnEndingHarnessIsReapedWithAResultTerminal drives construct -> use -> Close ->
// double Close over a harness that ends TURNS and never the session: the conn must be reaped
// exactly once, the second Close must be a no-op, no goroutine may outlive the session, and the
// one terminal the session ever carries must be the EventResult the Close produced.
//
// Today the reap and the idempotency already hold; what fails is the terminal itself — the pump
// cannot tell a requested Close from process death, so a clean shutdown of a healthy session is
// recorded as EventFailed{ReasonTransport}. A consumer folding that transcript sees a run that
// failed in transport when nothing failed at all.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling's goroutines would make it flaky, so the lifecycle/leak probe runs serially.
func TestLifecycle_TurnEndingHarnessIsReapedWithAResultTerminal(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	conn := newTurnConn(gracefulClose, turnBody("the answer"), turnBody("the follow-up answer"))
	session, transcriptEvents := openScriptedSession(t, conn)

	// USE: one real turn, drained to its boundary. The session is alive at this point — that is
	// the whole premise of the lane.
	promptAndAwaitTurnBoundary(t, session)

	// CLOSE, then CLOSE AGAIN: idempotent, and the second must not append a second terminal.
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("first Close: %v", err)
	}
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("second Close must be a no-op: %v", err)
	}

	// The conn was reaped exactly once: its driver has exited and its channels are closed.
	select {
	case <-conn.done:
	default:
		t.Errorf("the harness conn was not reaped by Close (its driver is still running)")
	}

	terminal := soleTerminal(t, transcriptEvents())
	if terminal.Kind != agentsession.EventResult {
		t.Errorf("a turn-ending harness closed on request produced %s (detail=%q); a deliberate reap must record EventResult, not a transport fault",
			terminal.Kind, terminalDetail(terminal))
	}
	if terminal.Terminal != nil && terminal.Terminal.Outcome != agentsession.TurnCompleted {
		t.Errorf("requested-close Outcome = %v, want TurnCompleted", terminal.Terminal.Outcome)
	}
}
