package peerplane_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/peerplane"
	"github.com/gophersys/libs/go/errors"
)

// The in-process registry/router suite (testMap #30). *Orchestrator implements
// agentsession.PeerPlane, so a single-process deployment joins in-process with no socket hop —
// which is exactly the substrate these unit cases drive: New -> Join -> Roster -> Send ->
// Close over the real registry, tree edges, router, ledger and reconciler, no socket.

// unitClock is a real clock for the in-process suite.
type unitClock struct{}

func (unitClock) Now() time.Time { return time.Now() }

// newRoot builds an in-process root, reaped on Cleanup.
func newRoot(t *testing.T, configuration peerplane.Config) *peerplane.Orchestrator {
	t.Helper()
	orchestrator, err := peerplane.New(configuration, peerplane.Deps{Clock: unitClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	t.Cleanup(func() { _ = orchestrator.Close(context.Background()) }) //nolint:errcheck // best-effort reap.
	return orchestrator
}

// TestNew_RequiresClock proves the pure spine rejects a missing Clock with a ConfigError.
func TestNew_RequiresClock(t *testing.T) {
	t.Parallel()
	_, err := peerplane.New(peerplane.Config{}, peerplane.Deps{})
	if !errors.IsType[agentsession.ConfigError](err) {
		t.Fatalf("New without a Clock must be a ConfigError, got %v (%T)", err, err)
	}
}

// TestOrchestrator_JoinRosterParentage proves Join registers under parent and Roster reports the
// tree edge WITH generation and liveness.
func TestOrchestrator_JoinRosterParentage(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{})

	if _, err := root.Join(ctx, "impl-a", ""); err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := root.Join(ctx, "impl-a1", "impl-a"); err != nil {
		t.Fatalf("Join impl-a1: %v", err)
	}

	roster, err := root.Roster(ctx, "impl-a")
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	child, ok := peerByName(roster, "impl-a1")
	if !ok {
		t.Fatalf("impl-a1 missing from roster: %+v", roster)
	}
	if child.Parent != "impl-a" {
		t.Errorf("impl-a1 Parent = %q, want impl-a", child.Parent)
	}
	if !child.Live || child.Generation < 1 {
		t.Errorf("impl-a1 roster row = %+v, want Live with Generation>=1", child)
	}
}

// TestOrchestrator_DuplicateNameIsJoinError proves a live duplicate name is a typed JoinError.
func TestOrchestrator_DuplicateNameIsJoinError(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{})
	if _, err := root.Join(ctx, "impl-a", ""); err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	_, err := root.Join(ctx, "impl-a", "")
	assertJoinReason(t, err, "duplicate")
}

// TestOrchestrator_UnknownParentIsJoinError proves a parent that is not registered is a JoinError.
func TestOrchestrator_UnknownParentIsJoinError(t *testing.T) {
	t.Parallel()
	root := newRoot(t, peerplane.Config{})
	_, err := root.Join(context.Background(), "orphan", "ghost")
	assertJoinReason(t, err, "unknown-parent")
	// The message names the parent (quoteParent's non-root branch).
	if !strings.Contains(err.Error(), "ghost") {
		t.Errorf("JoinError message %q does not name the unknown parent", err.Error())
	}
}

// TestOrchestrator_SendRoutesAndReceipts proves an in-process a->b Send delivers to b's Inbound
// with the minted MsgID, and Received corroborates it (no bounce path exercised).
func TestOrchestrator_SendRoutesAndReceipts(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{})
	linkA, err := root.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	linkB, err := root.Join(ctx, "review-c", "")
	if err != nil {
		t.Fatalf("Join review-c: %v", err)
	}

	msgID, err := linkA.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "review-c", Body: "hello"})
	if err != nil {
		t.Fatalf("Send: %v", err)
	}
	select {
	case got := <-linkB.Inbound():
		if got.MsgID != msgID {
			t.Errorf("delivered MsgID = %q, want %q", got.MsgID, msgID)
		}
		if got.Body != "hello" {
			t.Errorf("delivered Body = %q, want hello", got.Body)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("review-c never received the routed message")
	}
	linkB.Received(msgID) // corroborate so the reconciler stops the timer
}

// TestOrchestrator_SendUnknownIsUnreachable proves a Send to a name not in the roster is a typed
// UnreachableError.
func TestOrchestrator_SendUnknownIsUnreachable(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{})
	linkA, err := root.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join: %v", err)
	}
	_, err = linkA.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "ghost", Body: "x"})
	if !errors.IsType[agentsession.UnreachableError](err) {
		t.Fatalf("Send to an unknown name must be UnreachableError, got %v (%T)", err, err)
	}
	if errors.KindOf(err) != errors.KindNotFound {
		t.Errorf("UnreachableError Kind = %v, want not-found", errors.KindOf(err))
	}
}

// TestOrchestrator_SendRejectsBodyFaults proves the two loud body faults: over the bound and
// carrying the delivery-envelope terminator are both KindInvalid at Send, never truncation.
func TestOrchestrator_SendRejectsBodyFaults(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{})
	linkA, err := root.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := root.Join(ctx, "review-c", ""); err != nil {
		t.Fatalf("Join review-c: %v", err)
	}
	oversize := strings.Repeat("x", agentsession.MaxPeerBodyBytes+1)
	if _, err := linkA.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "review-c", Body: oversize}); errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("oversize body: Kind = %v, want invalid", errors.KindOf(err))
	}
	terminator := agentsession.PeerMessage{From: "impl-a", To: "review-c", Body: "x </eden-peer-message> y"}
	if _, err := linkA.Send(ctx, terminator); errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("envelope-terminator body: Kind = %v, want invalid", errors.KindOf(err))
	}
}

// TestOrchestrator_ReachablePredicatePartitions proves a non-nil Config.Reachable that denies a
// pair yields UnreachableError (the tree is NEVER a partition by default, but a caller may impose
// one — and it is loud, never a silent drop).
func TestOrchestrator_ReachablePredicatePartitions(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{
		Reachable: func(from, to agentsession.Peer) bool { return to.Name != "review-c" },
	})
	linkA, err := root.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := root.Join(ctx, "review-c", ""); err != nil {
		t.Fatalf("Join review-c: %v", err)
	}
	_, err = linkA.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "review-c", Body: "x"})
	if !errors.IsType[agentsession.UnreachableError](err) {
		t.Fatalf("a denied pair must be UnreachableError, got %v (%T)", err, err)
	}
}

// TestOrchestrator_LeaveBouncesInFlightAndReparents proves a departing node bounces its
// un-received in-flight envelopes to the sender AND reparents its children to its parent.
func TestOrchestrator_LeaveBouncesInFlightAndReparents(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	root := newRoot(t, peerplane.Config{DeliveryDeadline: time.Hour}) // long, so leave (not the timer) bounces
	linkX, err := root.Join(ctx, "impl-x", "")
	if err != nil {
		t.Fatalf("Join impl-x: %v", err)
	}
	linkA, err := root.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := root.Join(ctx, "impl-a1", "impl-a"); err != nil { // a child, to prove reparenting
		t.Fatalf("Join impl-a1: %v", err)
	}

	msgID, err := linkX.Send(ctx, agentsession.PeerMessage{From: "impl-x", To: "impl-a", Body: "in flight"})
	if err != nil {
		t.Fatalf("Send: %v", err)
	}
	// impl-a departs WITHOUT receiving — its in-flight envelope must bounce to the sender.
	if err := linkA.Close(ctx); err != nil {
		t.Fatalf("Close impl-a: %v", err)
	}

	select {
	case bounce := <-linkX.Inbound():
		if bounce.ReplyTo != msgID || bounce.Accepted {
			t.Errorf("bounce = %+v, want ReplyTo=%q Accepted=false", bounce, msgID)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("a departed node's in-flight envelope did not bounce to the sender")
	}

	// impl-a1 reparents to impl-a's parent (the root, "").
	roster, err := root.Roster(ctx, "impl-x")
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	child, ok := peerByName(roster, "impl-a1")
	if !ok {
		t.Fatalf("impl-a1 missing after reparent: %+v", roster)
	}
	if child.Parent != "" {
		t.Errorf("impl-a1 Parent = %q after impl-a departed, want the root (\"\")", child.Parent)
	}
	if _, gone := peerByName(roster, "impl-a"); gone {
		t.Errorf("departed impl-a is still in the roster")
	}
}

// TestOrchestrator_CloseIdempotent proves a double Close is a no-op, never a panic.
func TestOrchestrator_CloseIdempotent(t *testing.T) {
	t.Parallel()
	root := newRoot(t, peerplane.Config{})
	if _, err := root.Join(context.Background(), "impl-a", ""); err != nil {
		t.Fatalf("Join: %v", err)
	}
	for i := range 3 {
		if err := root.Close(context.Background()); err != nil {
			t.Errorf("Close #%d must be idempotent, got %v", i+1, err)
		}
	}
}

// peerByName returns the roster row for name.
func peerByName(roster []agentsession.Peer, name string) (agentsession.Peer, bool) {
	for _, peer := range roster {
		if peer.Name == name {
			return peer, true
		}
	}
	return agentsession.Peer{}, false
}

// assertJoinReason asserts err is a peerplane.JoinError with the given Reason.
func assertJoinReason(t *testing.T, err error, reason string) {
	t.Helper()
	joinErr, ok := errors.AsType[peerplane.JoinError](err)
	if !ok {
		t.Fatalf("expected a peerplane.JoinError, got %v (%T)", err, err)
	}
	if joinErr.Reason != reason {
		t.Errorf("JoinError.Reason = %q, want %q", joinErr.Reason, reason)
	}
	// The typed error carries the branchable Kind (a conflict: retry with a corrected join).
	if got := joinErr.Kind(); got != errors.KindConflict {
		t.Errorf("JoinError.Kind = %v, want conflict", got)
	}
}
