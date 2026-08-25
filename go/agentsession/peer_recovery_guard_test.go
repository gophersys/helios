package agentsession_test

import (
	"context"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// The two guards the full-mesh recovery path owes (V3-F3 and V5), both driven by ONE substrate: a
// plane whose Send BLOCKS. That is not a contrived state — PeerLink.Send is documented as a
// blocking call (a socket handshake bounded by handshakeTimeout, or an inbox push that is bounded
// by nothing at all), and the whole reason fix round 1 moved the recovery off the pump is that the
// pump owns Seq and may never wait on it.
//
//	F3 — with a recovered send outstanding on the plane, the pump must keep assigning Seq. Removing
//	     the fix (calling peerLink.Send from routeRecoveredSend, on the pump) left every package
//	     green, so the fix was a comment.
//	V5 — a blocked plane fills the hand-off queue, and the pump then DROPS recoveries to avoid
//	     blocking. Today it drops them in SILENCE: the published EventPeerSent is verbatim, so a
//	     recovery the library threw away is byte-identical to one it routed. That is the exact
//	     silent hold the plane exists to make impossible.

// recoveryGuardDeadline bounds every wait here. A wait that runs out is a FAILURE naming what never
// happened, never a quiet return.
const recoveryGuardDeadline = 5 * time.Second

// recoveredSendCount is scripted well above the library's hand-off buffer so the overflow does not
// depend on that buffer's exact size: the deliver goroutine takes one and blocks on the plane, the
// buffer absorbs the next few, and everything after that is dropped.
const recoveredSendCount = 16

// TestPeerRecovery_PumpAdvancesWhileThePlaneSendBlocks is the F3 guard. It asserts the property the
// invariant is stated for twice (peer.go:72-74, peer_session.go:67-70) and nothing enforced: with a
// plane Send OUTSTANDING, the pump still publishes the next event and assigns it a higher Seq.
//
// FALSIFICATION (the bite): route the recovered send from routeRecoveredSend itself — the pre-fix
// shape — and the pump blocks inside the plane's Send. No event after the EventPeerSent is ever
// published, the stream ends at the deadline, and this arm fails. Proven by -overlay.
func TestPeerRecovery_PumpAdvancesWhileThePlaneSendBlocks(t *testing.T) {
	t.Parallel()
	plane := newBlockingPeerPlane()
	defer plane.release() // BEFORE the session Cleanup: Close joins the deliver goroutine.

	session := openRecoverySession(t, plane,
		agentsessiontest.PeerSentEvent(recoveredSend(1)),
		agentsessiontest.MessageEnd(),
		peerTerminal())

	ctx, cancel := context.WithTimeout(context.Background(), recoveryGuardDeadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "message review-c"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}

	sentSeq, seen := uint64(0), false
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("the stream ended with no event after the EventPeerSent (seen=%v, last Seq %d): the pump is blocked inside the plane's Send, so Seq stopped advancing",
				seen, sentSeq)
		}
		if event.Kind == agentsession.EventPeerSent {
			sentSeq, seen = event.Seq, true
			continue
		}
		if seen && event.Seq > sentSeq {
			break // the pump advanced past the recovery
		}
		if event.IsTerminal() {
			t.Fatalf("the session terminated at Seq %d without publishing anything after the EventPeerSent", event.Seq)
		}
	}

	// The advance only proves the invariant if the Send really is outstanding: a recovery that was
	// never attempted would let the pump advance for the wrong reason.
	plane.awaitAttempts(t, 1)
}

// TestPeerRecovery_QueueOverflowIsLoudNotSilent is the V5 guard. With the plane blocked, the
// library's hand-off queue fills and the pump — which may not block — drops the rest. A drop is
// acceptable; a SILENT drop is not, because the model was told its native send failed and the
// library then promised to route it.
//
// THE CONTRACT this arm defines: every observed send stays on the stream, and a recovery the
// library did NOT hand to its router is published with a Detail that DIFFERS from the routing
// discriminator "native-send-unreachable" — one stable literal a consumer can branch on, spelled
// the same way for every dropped recovery. The arm pins the PROPERTY rather than the spelling, so
// the literal stays the library's to choose; it is "native-send-unrecovered" today.
//
// FALSIFICATION (the bite): today the published event is verbatim, so all 16 carry
// Detail="native-send-unreachable" whether they were routed or thrown away, and this arm fails
// naming how many the plane actually accepted.
func TestPeerRecovery_QueueOverflowIsLoudNotSilent(t *testing.T) {
	t.Parallel()
	plane := newBlockingPeerPlane()
	defer plane.release() // BEFORE the session Cleanup: Close joins the deliver goroutine.

	script := make([]agentsession.Event, 0, recoveredSendCount+1)
	for i := range recoveredSendCount {
		script = append(script, agentsessiontest.PeerSentEvent(recoveredSend(i)))
	}
	script = append(script, peerTerminal())
	session := openRecoverySession(t, plane, script...)

	sent := collectPeerSent(t, session)
	if len(sent) != recoveredSendCount {
		t.Fatalf("the stream carries %d EventPeerSent, want %d: an observed send must never be dropped from the transcript",
			len(sent), recoveredSendCount)
	}
	assertOverflowIsLoud(t, sent, plane.attempts())
}

// assertOverflowIsLoud pins the loudness contract over the published sends: at least one carries a
// Detail other than the routing discriminator, every such Detail is the SAME stable literal, and
// none of them claims acceptance.
func assertOverflowIsLoud(t *testing.T, sent []agentsession.PeerMessage, attempted int) {
	t.Helper()
	details := make(map[string]int, 2)
	for i := range sent {
		details[sent[i].Detail]++
		if sent[i].Accepted {
			t.Errorf("a recovered send was published Accepted=true; nothing accepted it: %+v", sent[i])
		}
	}
	loud := make([]string, 0, len(details))
	for detail := range details {
		if detail != peerRecoveryDetail {
			loud = append(loud, detail)
		}
	}
	switch {
	case len(loud) == 0:
		t.Fatalf("all %d recovered sends published Detail=%q while the plane accepted only %d of them: a recovery the library DROPPED is byte-identical to one it routed — the model was told the native send failed and then told nothing at all",
			len(sent), peerRecoveryDetail, attempted)
	case len(loud) > 1:
		t.Errorf("the dropped recoveries carry %d different Details %v; a consumer branches on ONE stable literal, not on a family", len(loud), loud)
	}
	for _, detail := range loud {
		if detail == "" {
			t.Errorf("a dropped recovery was published with an EMPTY Detail: it is distinguishable only by absence, which no consumer can branch on")
		}
		if detail == peerUnparsedDetail {
			t.Errorf("a dropped recovery reuses %q, which means the OPPOSITE — a send the native plane really did accept", peerUnparsedDetail)
		}
	}
	t.Logf("published Details across %d recoveries (plane accepted %d): %v", len(sent), attempted, details)
}

// openRecoverySession opens ONE addressable session over the blocking plane. CapPartial is what
// claude declares — the recovery exists precisely because its own plane cannot reach the peer.
//
//nolint:ireturn // Session is the contract's returned port; the helper mirrors Pool.Open.
func openRecoverySession(t *testing.T, plane agentsession.PeerPlane, script ...agentsession.Event) agentsession.Session {
	t.Helper()
	adapter := newSpecRecordingAdapter(peerMessagingManifest(agentsession.CapPartial), script...)
	session, err := newBindingPool(t, adapter, plane).Open(context.Background(), bindingSpec("impl-a"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.
	return session
}

// recoveredSend builds one adapter-surfaced recovery instruction: a send the harness's own plane
// refused, carrying the payload the library is expected to route.
func recoveredSend(index int) agentsession.PeerMessage {
	return agentsession.PeerMessage{
		To:       "review-c",
		Body:     "recovery-" + strconv.Itoa(index),
		Accepted: false,
		Detail:   peerRecoveryDetail,
	}
}

// collectPeerSent drives the turn to its terminal and returns every EventPeerSent payload the
// session published, in order. It FAILS on a stream that ends early: a truncated stream would make
// the count assertion pass for the wrong reason.
func collectPeerSent(t *testing.T, session agentsession.Session) []agentsession.PeerMessage {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), recoveryGuardDeadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "message review-c"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	var sent []agentsession.PeerMessage
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("the stream ended without a terminal after %d EventPeerSent: the pump stalled", len(sent))
		}
		if event.Kind == agentsession.EventPeerSent && event.Peer != nil {
			sent = append(sent, *event.Peer)
		}
		if event.IsTerminal() {
			return sent
		}
	}
}

// ── the blocking plane ────────────────────────────────────────────────────────────────────────.

// blockingPeerPlane is an agentsession.PeerPlane whose Send accepts the message and then BLOCKS
// until the test releases it — the documented behavior of both real planes (a socket handshake, an
// unbounded inbox push), held open so the library's two hand-off guarantees are observable.
type blockingPeerPlane struct {
	released chan struct{}
	inbound  chan agentsession.PeerMessage

	mu        sync.Mutex
	attempted int
}

// newBlockingPeerPlane builds the plane. Nothing is released until the test says so.
func newBlockingPeerPlane() *blockingPeerPlane {
	return &blockingPeerPlane{
		released: make(chan struct{}),
		inbound:  make(chan agentsession.PeerMessage),
	}
}

// Join hands back a link onto this plane. It never refuses: the refusal paths are pinned elsewhere.
//
//nolint:ireturn // returns the agentsession.PeerLink port (the contract surface).
func (p *blockingPeerPlane) Join(_ context.Context, _, _ string) (agentsession.PeerLink, error) {
	return &blockingPeerLink{plane: p}, nil
}

// Roster reports an empty mesh; no case here reads it.
func (p *blockingPeerPlane) Roster(_ context.Context, _ string) ([]agentsession.Peer, error) {
	return nil, nil
}

// release unblocks every outstanding and future Send. It is idempotent so a deferred release and an
// explicit one cannot panic on a double close.
func (p *blockingPeerPlane) release() {
	p.mu.Lock()
	defer p.mu.Unlock()
	select {
	case <-p.released:
	default:
		close(p.released)
	}
}

// attempts reports how many sends reached the plane.
func (p *blockingPeerPlane) attempts() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.attempted
}

// awaitAttempts waits until at least want sends have reached the plane, FAILING when they never do:
// a pump that advanced because the recovery was silently skipped proves nothing about the hand-off.
func (p *blockingPeerPlane) awaitAttempts(t *testing.T, want int) {
	t.Helper()
	deadline := time.Now().Add(recoveryGuardDeadline)
	for time.Now().Before(deadline) {
		if p.attempts() >= want {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("the plane saw %d sends within %s, want at least %d: the recovery never reached the plane at all, so the pump's advance proves nothing",
		p.attempts(), recoveryGuardDeadline, want)
}

// blockingPeerLink is one session's attachment to the blocking plane.
type blockingPeerLink struct{ plane *blockingPeerPlane }

// Inbound carries nothing: this plane routes to no one.
func (l *blockingPeerLink) Inbound() <-chan agentsession.PeerMessage { return l.plane.inbound }

// Send records the attempt and BLOCKS until the plane is released.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record; the port takes it by value.
func (l *blockingPeerLink) Send(ctx context.Context, _ agentsession.PeerMessage) (string, error) {
	l.plane.mu.Lock()
	l.plane.attempted++
	minted := "msg-" + strconv.Itoa(l.plane.attempted)
	l.plane.mu.Unlock()
	select {
	case <-l.plane.released:
	case <-ctx.Done():
	}
	return minted, nil
}

// Received is a no-op: nothing here corroborates a delivery.
func (l *blockingPeerLink) Received(_ string) {}

// Close leaves the plane; there is nothing to reap.
func (l *blockingPeerLink) Close(_ context.Context) error { return nil }
