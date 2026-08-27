// White-box unit tests for the root reconciler — THE loudness core (design §5.3, testMap #31,
// break #7). They assert not only the in-band bounce (observable on the sender's Inbound) but
// the DURABLE record of it, which is exposed only through the unexported recordedUndelivered
// seam in export_test.go; that same-package assertion is why this file is white-box.
//
//nolint:testpackage // recordedUndelivered (export_test.go) is unexported by design so the .apibaseline stays frozen; white-box is the only way to assert the reconciler RECORDED the UndeliveredError, not merely bounced it.
package peerplane

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// The reconciler is THE loudness core. Send returns "accepted for routing", never
// "delivered": delivery is a LATER, separate fact — the receiver's Received reaching the root.
// A ledger row with no Received inside DeliveryDeadline is the silently-held message the probe
// found (zero trace on BOTH ends), and only the root can see it, because only the root holds
// both halves. It BOUNCES an in-band envelope from <mesh>.root to the sender AND records an
// UndeliveredError — never a sender-side timeout that fires on a merely-slow model.

// reconcilerClock is a real clock: the reconciler consults Deps.Clock and the deadline is
// kept small (below), so the bounce fires within the test's wait window without flakiness.
type reconcilerClock struct{}

func (reconcilerClock) Now() time.Time { return time.Now() }

// newReconcilerRoot builds a root with a short DeliveryDeadline, reaped on Cleanup.
func newReconcilerRoot(t *testing.T) *Orchestrator {
	t.Helper()
	orchestrator, err := New(Config{DeliveryDeadline: 100 * time.Millisecond}, Deps{Clock: reconcilerClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	t.Cleanup(func() { _ = orchestrator.Close(context.Background()) }) //nolint:errcheck // best-effort reap.
	return orchestrator
}

// TestReconciler_UndeliveredBouncesFromRoot is the positive case: a→b Send with b's Received
// SUPPRESSED must bounce to a from the mesh root inside DeliveryDeadline and record an
// UndeliveredError naming b + the msg_id.
func TestReconciler_UndeliveredBouncesFromRoot(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	orchestrator := newReconcilerRoot(t)

	linkA, err := orchestrator.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := orchestrator.Join(ctx, "review-c", ""); err != nil {
		t.Fatalf("Join review-c: %v", err)
	}

	msgID, err := linkA.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "review-c", Body: "did you get this?"})
	if err != nil {
		t.Fatalf("Send: %v", err)
	}
	// review-c NEVER calls Received — the message is accepted for routing but never delivered.

	assertBounceFromRoot(t, linkA, msgID)
	assertRecordedUndelivered(t, orchestrator, "review-c", msgID)
}

// assertBounceFromRoot asserts a bounce arrives on the sender's Inbound within the window and
// carries the root as From, the undelivered id as ReplyTo, and Accepted=false.
func assertBounceFromRoot(t *testing.T, link agentsession.PeerLink, msgID string) {
	t.Helper()
	bounce, ok := awaitInbound(t, link, 5*time.Second)
	if !ok {
		t.Fatalf("no bounce arrived for undelivered msg_id %q within the window — a silently held message went unobserved (the exact failure the reconciler exists to remove)", msgID)
	}
	if bounce.ReplyTo != msgID {
		t.Errorf("bounce.ReplyTo = %q, want the undelivered msg_id %q", bounce.ReplyTo, msgID)
	}
	if bounce.From == "impl-a" || bounce.From == "review-c" {
		t.Errorf("bounce.From = %q, want the mesh root (not a peer)", bounce.From)
	}
	if bounce.Accepted {
		t.Errorf("a bounce reports the ORIGINAL as NOT delivered: bounce carries Accepted=true")
	}
}

// assertRecordedUndelivered asserts the root RECORDED a typed UndeliveredError naming the peer
// and the msg_id, classified to the loudness Kind (errors.KindDeadline).
func assertRecordedUndelivered(t *testing.T, orchestrator *Orchestrator, name, msgID string) {
	t.Helper()
	recorded := recordedUndelivered(orchestrator)
	for _, undelivered := range recorded {
		if undelivered.Name == name && undelivered.MsgID == msgID {
			// The record is loudness-typed: its Kind() is the branchable classification the
			// transport boundary reads (errors.KindDeadline — an accepted message that never
			// arrived within DeliveryDeadline).
			if got := undelivered.Kind(); got != errors.KindDeadline {
				t.Errorf("UndeliveredError Kind = %v, want deadline", got)
			}
			return
		}
	}
	t.Fatalf("no UndeliveredError recorded for %s/%s; recorded=%+v", name, msgID, recorded)
}

// TestReconciler_DeliveredDoesNotBounce is the non-vacuity control: when b DOES call
// Received inside the deadline, the row is corroborated and NOTHING bounces — so the bounce
// above is a response to a real absence of delivery, not fired unconditionally.
func TestReconciler_DeliveredDoesNotBounce(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	orchestrator := newReconcilerRoot(t)

	linkA, err := orchestrator.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	linkB, err := orchestrator.Join(ctx, "review-c", "")
	if err != nil {
		t.Fatalf("Join review-c: %v", err)
	}

	msgID, err := linkA.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "review-c", Body: "ack me"})
	if err != nil {
		t.Fatalf("Send: %v", err)
	}
	// b takes delivery and corroborates it to the root.
	if _, ok := awaitInbound(t, linkB, 2*time.Second); !ok {
		t.Fatalf("review-c never received the message on its Inbound")
	}
	linkB.Received(msgID)

	// No bounce must arrive for a corroborated message within a window well past the deadline.
	if bounce, ok := awaitInbound(t, linkA, 500*time.Millisecond); ok {
		t.Fatalf("a corroborated message bounced anyway: %+v", bounce)
	}
	for _, undelivered := range recordedUndelivered(orchestrator) {
		if undelivered.MsgID == msgID {
			t.Fatalf("a corroborated message was recorded UndeliveredError: %+v", undelivered)
		}
	}
}

// awaitInbound waits up to timeout for one message on the link's Inbound channel.
//
//nolint:gocritic // agentsession.PeerMessage is the contract's copyable value; returned by value.
func awaitInbound(t *testing.T, link agentsession.PeerLink, timeout time.Duration) (agentsession.PeerMessage, bool) {
	t.Helper()
	select {
	case message := <-link.Inbound():
		return message, true
	case <-time.After(timeout):
		return agentsession.PeerMessage{}, false
	}
}
