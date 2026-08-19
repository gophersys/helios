package peerplane

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// The reconciler is THE loudness core (design §5.3, testMap #31, break #7). Send returns
// "accepted for routing", never "delivered": delivery is a LATER, separate fact — the
// receiver's Received reaching the root. A ledger row with no Received inside
// DeliveryDeadline is the silently-held message the probe found (zero trace on BOTH ends),
// and only the root can see it, because only the root holds both halves. It BOUNCES an
// in-band envelope from <mesh>.root to the sender AND records an UndeliveredError — never a
// sender-side timeout that fires on a merely-slow model.

// reconcilerClock is a real clock: the reconciler consults Deps.Clock and the deadline is
// kept small (below), so the bounce fires within the test's wait window without flakiness.
type reconcilerClock struct{}

func (reconcilerClock) Now() time.Time { return time.Now() }

// TestReconciler_UndeliveredBouncesFromRoot is the positive case: a→b Send with b's Received
// SUPPRESSED must bounce to a from the mesh root inside DeliveryDeadline and record an
// UndeliveredError naming b + the msg_id.
func TestReconciler_UndeliveredBouncesFromRoot(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	orchestrator, err := New(Config{DeliveryDeadline: 100 * time.Millisecond}, Deps{Clock: reconcilerClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	t.Cleanup(func() { _ = orchestrator.Close(ctx) }) //nolint:errcheck // best-effort reap.

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

	bounce, ok := awaitInbound(t, linkA, 5*time.Second)
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

	// The root also RECORDED a typed UndeliveredError (the errors.AsType-branchable record).
	recorded := recordedUndelivered(orchestrator)
	var matched bool
	for _, undelivered := range recorded {
		if undelivered.Name == "review-c" && undelivered.MsgID == msgID {
			matched = true
		}
	}
	if !matched {
		t.Fatalf("no UndeliveredError recorded for review-c/%s; recorded=%+v", msgID, recorded)
	}
	// The recorded error is loudness-typed.
	if len(recorded) > 0 {
		if _, isErr := error(recorded[0]).(interface{ Error() string }); !isErr {
			t.Errorf("UndeliveredError does not satisfy error")
		}
		_ = errors.KindOf(recorded[0])
	}
}

// TestReconciler_DeliveredDoesNotBounce is the non-vacuity control: when b DOES call
// Received inside the deadline, the row is corroborated and NOTHING bounces — so the bounce
// above is a response to a real absence of delivery, not fired unconditionally.
func TestReconciler_DeliveredDoesNotBounce(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	orchestrator, err := New(Config{DeliveryDeadline: 100 * time.Millisecond}, Deps{Clock: reconcilerClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	t.Cleanup(func() { _ = orchestrator.Close(ctx) }) //nolint:errcheck // best-effort reap.

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
