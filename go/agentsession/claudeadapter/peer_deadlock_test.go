package claudeadapter_test

import (
	"context"
	"io"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
)

// The F4 DEADLOCK GUARD (V3). Fix round 1 moved writeMu off Send and into the leaf writers so a
// peer delivery queues its event with NO lock held. Nothing pinned that: removing the fix — taking
// writeMu around queuePeerEvent again — left all eight packages GREEN, which makes the fix a
// comment rather than a contract.
//
// The wedge is reachable with no process at all: the conn's events channel is UNBUFFERED and the
// scanner is its sole sender, so a session whose consumer has stopped reading blocks the scanner
// on its very first publish. The scanner is also the only drainer of peerEvents, so peerEvents
// fills, and the next delivery blocks in the queue push. If that push happens under writeMu, then
// Close — which takes writeMu to close stdin — can never run, and the session is UNKILLABLE.
//
// This is the state a real deployment reaches whenever a viewer disconnects mid-delivery, which is
// why the guard is a deadline on Close rather than an inspection of which lock is held.

// closeDeadline bounds Close. A Close that has not returned by then is the deadlock: this test
// FAILS naming it rather than hanging until the package timeout, where it would read as an
// infrastructure stall instead of a defect.
const closeDeadline = 2 * time.Second

// TestPeerDelivery_CloseIsBoundedWhileADeliveryIsWedged is the F4 guard.
//
// FALSIFICATION (the bite): wrap queuePeerEvent back in c.writeMu.Lock()/Unlock() — the pre-fix
// shape — and Close never returns, so this test fails on its deadline. Proven by -overlay of a
// peer.go carrying exactly that two-line change (the tracked file is never touched).
func TestPeerDelivery_CloseIsBoundedWhileADeliveryIsWedged(t *testing.T) {
	t.Parallel()
	conn, stop := newUndrainedClaudeConn(t)

	frame, err := controlframe.EncodePeer(claudePeerFrom, claudePeerTo, claudePeerMsgID, "", claudePeerBody, true)
	if err != nil {
		t.Fatalf("EncodePeer: %v", err)
	}

	// Deliver until the queue is full and one more delivery is wedged in the push. The count is
	// far above the delivery buffer so the wedge does not depend on its exact size.
	const deliveries = 64
	var completed atomic.Int64
	senderDone := make(chan struct{})
	go func() {
		defer close(senderDone)
		for range deliveries {
			if sendErr := conn.Send(context.Background(),
				agentsession.Command{Kind: agentsession.CommandPrompt, Text: frame}); sendErr != nil {
				return
			}
			completed.Add(1)
		}
	}()

	waitForWedgedDelivery(t, &completed, senderDone)

	// THE ASSERTION: Close must return while that delivery is still wedged.
	closed := make(chan error, 1)
	go func() { closed <- conn.Close(context.Background()) }()
	select {
	case closeErr := <-closed:
		if closeErr != nil {
			t.Errorf("Close returned %v while a peer delivery was wedged; it must reap the conn, not fail", closeErr)
		}
	case <-time.After(closeDeadline):
		t.Fatalf("Close did not return within %s while a peer delivery was wedged in the event queue: the delivery holds writeMu across the queue push and Close needs writeMu — the session is unkillable",
			closeDeadline)
	}

	stop(t, senderDone)
}

// waitForWedgedDelivery blocks until a delivery is stuck in the event-queue push — the state the
// Close assertion needs. It FAILS rather than returning quietly on either degenerate outcome: a
// sender that finishes every delivery means nothing ever wedged and the assertion below would be
// vacuous, and a sender that never completes even one means the wedge is somewhere else entirely.
func waitForWedgedDelivery(t *testing.T, completed *atomic.Int64, senderDone <-chan struct{}) {
	t.Helper()
	deadline := time.Now().Add(closeDeadline)
	stable, last := 0, int64(-1)
	for time.Now().Before(deadline) {
		select {
		case <-senderDone:
			t.Fatalf("every delivery completed (%d): nothing was ever wedged, so the Close assertion would prove nothing — the event queue drained when it must not",
				completed.Load())
		default:
		}
		current := completed.Load()
		if current > 0 && current == last {
			if stable++; stable >= 5 {
				return
			}
		} else {
			stable, last = 0, current
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("no delivery ever completed within %s (%d done): the wedge is not the event queue", closeDeadline, completed.Load())
}

// newUndrainedClaudeConn builds the REAL conn over in-memory pipes with NOBODY reading its events
// — the state a session reaches when its consumer goes away. The returned stop function reaps it:
// it starts draining (which releases the wedged scanner), closes the transport, and asserts both
// the scanner and the sender actually ended, so a leaked goroutine fails HERE rather than in the
// package's goleak TestMain against whichever test ran last.
func newUndrainedClaudeConn(t *testing.T) (agentsession.HarnessConn, func(*testing.T, <-chan struct{})) {
	t.Helper()
	reader, writer := io.Pipe()
	stdin := &claudeRecordingStdin{}
	conn := claudeadapter.PipeConnForTest(agentsession.Spec{Name: claudePeerTo}, reader, stdin)

	stop := func(t *testing.T, senderDone <-chan struct{}) {
		t.Helper()
		drained := make(chan struct{})
		go func() {
			defer close(drained)
			for range conn.Events() { //nolint:revive // draining is the point; the events are not asserted on here.
			}
		}()
		_ = writer.Close() //nolint:errcheck // EOF for the conn's reader: what ends the scanner.
		_ = reader.Close() //nolint:errcheck // best-effort; ends the scanner if Close did not.
		select {
		case <-drained:
		case <-time.After(closeDeadline):
			t.Errorf("the conn's event channel was still open %s after Close: the scanner outlives the session", closeDeadline)
		}
		select {
		case <-senderDone:
		case <-time.After(closeDeadline):
			t.Errorf("the wedged delivery goroutine never returned %s after Close: a delivery that outlives its conn is a leak", closeDeadline)
		}
	}
	return conn, stop
}
