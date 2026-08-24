package ompadapter_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
)

// The DELIVERY side of the peer binding on omp's `--mode rpc` transport.
//
// The library's deliver goroutine hands an adapter an inbound peer message as an ordinary
// control frame carrying the internal `eden:peer:` grammar (controlframe.EncodePeer). That
// grammar is INTERNAL: it is 0x1f-separated header fields whose only purpose is to survive the
// hop from the library to the adapter. What reaches the MODEL is a different thing entirely —
// the <eden-peer-message> envelope, which is why the encoder rejects a body that could close it.
//
// The two obligations are symmetric across BOTH adapters, which is why they are spelled the
// same way here and in claudeadapter/peer_conn_test.go: UNWRAP on the wire, and emit EXACTLY
// ONE EventPeerMessage for the delivery.

// The identifiers the delivery is asserted on.
const (
	peerDeliveryFrom  = "impl-a"
	peerDeliveryTo    = "review-c"
	peerDeliveryMsgID = "msg-7f3c"
	peerDeliveryBody  = "please review the pump change"
)

// TestPeerDelivery_UnwrapsControlFrameToEnvelope is test 6, omp half. Sending an inbound peer
// frame through the conn must do two things and nothing else:
//
//	WIRE  — omp receives the model-facing <eden-peer-message> envelope. The internal
//	        `eden:peer:` prefix and its 0x1f separators must NEVER reach the model: a model that
//	        reads them learns Eden's private control grammar and can forge a delivery by
//	        typing it, which is the whole reason the two forms are different.
//	EVENT — the conn publishes EXACTLY ONE EventPeerMessage. The delivery is a fact about this
//	        session and belongs on its stream; the library's dedupe ring bounds a second
//	        arrival, but the adapter must not manufacture the duplicate in the first place.
//
// FALSIFICATION: today the conn writes command.Text through unchanged, so the model would
// receive the raw `eden:peer:impl-a\x1freview-c\x1f…` frame and no peer event would be
// published at all.
func TestPeerDelivery_UnwrapsControlFrameToEnvelope(t *testing.T) {
	t.Parallel()
	harness := newRPCHarness(t, agentsession.Spec{Name: peerDeliveryTo})
	harness.completeHandshake()

	frame, err := controlframe.EncodePeer(peerDeliveryFrom, peerDeliveryTo, peerDeliveryMsgID, "", peerDeliveryBody, true)
	if err != nil {
		t.Fatalf("EncodePeer: %v", err)
	}
	if err := harness.conn.Send(context.Background(),
		agentsession.Command{Kind: agentsession.CommandPrompt, Text: frame}); err != nil {
		t.Fatalf("Send peer frame: %v", err)
	}

	written := harness.waitFrame("prompt carrying the peer delivery", func(f map[string]any) bool {
		return stringField(f, "type") == "prompt" && strings.Contains(stringField(f, "message"), peerDeliveryBody)
	})
	assertPeerEnvelopeOnTheWire(t, stringField(written, "message"))

	event := harness.waitEvent("the inbound EventPeerMessage", func(e *agentsession.Event) bool {
		return e.Kind == agentsession.EventPeerMessage
	})
	assertDeliveredPeerMessage(t, event)

	if count := countPeerMessages(harness); count != 1 {
		t.Errorf("one delivered frame published %d EventPeerMessage; the adapter must emit exactly one", count)
	}
}

// assertPeerEnvelopeOnTheWire pins what the MODEL is allowed to see: the envelope, the sender
// identity, the correlation id, the trust flag, and the body verbatim — and none of the
// internal grammar the library used to get it here.
func assertPeerEnvelopeOnTheWire(t *testing.T, wire string) {
	t.Helper()
	if strings.Contains(wire, controlframe.PeerPrefix) {
		t.Errorf("the internal %q frame reached the model verbatim: %q", controlframe.PeerPrefix, wire)
	}
	if strings.ContainsRune(wire, '\x1f') {
		t.Errorf("the internal 0x1f field separator reached the model: %q", wire)
	}
	if !strings.HasPrefix(wire, "<eden-peer-message") {
		t.Errorf("the delivery must open the <eden-peer-message> envelope; got %q", wire)
	}
	if !strings.HasSuffix(wire, "</eden-peer-message>") {
		t.Errorf("the delivery must close the </eden-peer-message> envelope; got %q", wire)
	}
	for _, want := range []string{peerDeliveryFrom, peerDeliveryMsgID, peerDeliveryBody, "verified"} {
		if !strings.Contains(wire, want) {
			t.Errorf("the envelope must carry %q so the model can tell WHO sent it, WHICH message it is, and whether the sender is kernel-verified; got %q",
				want, wire)
		}
	}
}

// assertDeliveredPeerMessage pins the published event against the frame the library encoded.
func assertDeliveredPeerMessage(t *testing.T, event *agentsession.Event) {
	t.Helper()
	if event.Peer == nil {
		t.Fatalf("EventPeerMessage carried a nil Peer payload")
	}
	if event.Peer.MsgID != peerDeliveryMsgID {
		t.Errorf("Peer.MsgID = %q, want %q — the id the plane minted and the root reconciler corroborates on",
			event.Peer.MsgID, peerDeliveryMsgID)
	}
	if event.Peer.From != peerDeliveryFrom {
		t.Errorf("Peer.From = %q, want %q", event.Peer.From, peerDeliveryFrom)
	}
	if event.Peer.Body != peerDeliveryBody {
		t.Errorf("Peer.Body = %q, want %q verbatim", event.Peer.Body, peerDeliveryBody)
	}
	if !event.Peer.Verified {
		t.Errorf("Peer.Verified = false; the frame carried verified=true, stamped by the plane from the SO_PEERCRED connection — the adapter may not downgrade it")
	}
}

// countPeerMessages counts every EventPeerMessage the harness has drained so far.
func countPeerMessages(harness *rpcHarness) int {
	harness.mu.Lock()
	defer harness.mu.Unlock()
	count := 0
	for i := range harness.events {
		if harness.events[i].Kind == agentsession.EventPeerMessage {
			count++
		}
	}
	return count
}
