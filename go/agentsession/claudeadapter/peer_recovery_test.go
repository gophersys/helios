package claudeadapter_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// The FULL-MESH recovery path — the COORDINATOR OVERRIDE (Mateo's design ruling, full mesh v1).
//
// Claude's native plane can only reach another claude session. A claude model asked to message
// an omp peer therefore drives SendMessage, and the CLI answers "No agent named '<x>' is
// reachable." The design does NOT accept a one-way mesh: the ADAPTER surfaces the failed send
// plus the payload recovered from the tool_use INPUT as a normalized fact, and the LIBRARY —
// which is the only side holding the PeerLink — routes it over the plane so the peer really
// receives it. The library half is pinned in agentsession/peer_recovery_test.go; this file
// pins the adapter half, and the caveat that goes with it.
//
// Both halves are pinned deliberately, because each is the obvious way to "fix" the other:
// faking a success to the model would satisfy the recovery and destroy the caveat, and
// dropping the recovery would satisfy the caveat and destroy the mesh.

// peerRecoveryDetail is the redacted reason on the recovered send. It is the DISCRIMINATOR the
// library branches on to decide that this particular EventPeerSent is a routing instruction and
// not merely an unhappy receipt — it must therefore differ from "send-receipt-unparsed", which
// is a send the library must NOT re-route (that one really was accepted by the native plane).
const peerRecoveryDetail = "native-send-unreachable"

// nativeUnreachableMarker is the substring of the real CLI failure the normalized tool result
// must still carry. Quoted from the committed probe report probe-2.json (finding "P1
// ADDRESSABILITY"), where the measured tool_result was
// {"success":false,"message":"No agent named 'dbad3a' is reachable.\nUse ListAgents to see
// everyone you can message."}.
const nativeUnreachableMarker = "is reachable"

// TestPeerRecovery_UnreachableSendSurfacesRecoveredPayload is test 11, adapter half. A
// SendMessage whose target is not another claude session fails natively; the binding must
// recover {to, body} from the tool_use INPUT — the only place they exist, since the failing
// tool_result carries neither — and surface them as an EventPeerSent that is explicitly NOT
// accepted, carrying the discriminator the library routes on.
//
// FALSIFICATION: emitting nothing (the message is lost and the mesh is one-way), or emitting
// Accepted:true (the library would believe the native plane delivered it and never route it).
func TestPeerRecovery_UnreachableSendSurfacesRecoveredPayload(t *testing.T) {
	t.Parallel()
	events := normalizePeerStream(t, peerFixtureLines(t, fixtureSendUnreadable))

	sent := eventsOfKind(events, agentsession.EventPeerSent)
	if len(sent) != 1 {
		t.Fatalf("a natively-unreachable SendMessage must still yield exactly 1 EventPeerSent carrying the recovered payload, got %d; kinds: %s",
			len(sent), renderKinds(events))
	}
	message := sent[0].Peer
	if message == nil {
		t.Fatalf("EventPeerSent carried a nil Peer payload")
	}
	if message.To != "review-c" {
		t.Errorf("Peer.To = %q, want %q — recovered from the tool_use input.to (the failing tool_result carries no destination)",
			message.To, "review-c")
	}
	if message.Body != "PROBE-FULLMESH cross-harness body" {
		t.Errorf("Peer.Body = %q, want the body recovered VERBATIM from the tool_use input.message; a digest would break delivery",
			message.Body)
	}
	if message.Accepted {
		t.Errorf("Peer.Accepted = true; the native plane REFUSED this send, so nothing has accepted it for routing yet")
	}
	if message.Detail != peerRecoveryDetail {
		t.Errorf("Peer.Detail = %q, want %q — the discriminator the library routes on; %q means an accepted send whose id was unreadable and must NOT be re-routed",
			message.Detail, peerRecoveryDetail, "send-receipt-unparsed")
	}
	if message.MsgID != "" {
		t.Errorf("Peer.MsgID = %q, want \"\": the native plane minted no id, and the plane's own id is minted at the library's Send",
			message.MsgID)
	}
}

// TestPeerRecovery_NativeFailureIsStillReported is test 12 — the model-visible caveat, pinned so
// that nobody "fixes" the recovery by hiding the failure. The recovery happens BEHIND the model:
// the model already saw the CLI say the peer is unreachable, and Eden does not get to rewrite
// that. The normalized tool result must therefore still carry the native failure text, and the
// tool call must still be correlated to its tool_use_id.
//
// FALSIFICATION: swallowing the EventToolEnd once the recovery fires, or rewriting its digest
// into a synthetic success — either makes the transcript disagree with what the model was told,
// which is the one thing a transcript exists to prevent.
func TestPeerRecovery_NativeFailureIsStillReported(t *testing.T) {
	t.Parallel()
	events := normalizePeerStream(t, peerFixtureLines(t, fixtureSendUnreadable))

	var ends []agentsession.Event
	for i := range events {
		if events[i].Kind == agentsession.EventToolEnd && events[i].Tool != nil &&
			events[i].Tool.CallID == peerSendToolUseID {
			ends = append(ends, events[i])
		}
	}
	if len(ends) != 1 {
		t.Fatalf("the failed SendMessage must STILL yield exactly 1 EventToolEnd for tool_use_id %s, got %d; kinds: %s",
			peerSendToolUseID, len(ends), renderKinds(events))
	}
	digest := ends[0].Tool.ResultDigest
	if !strings.Contains(digest, nativeUnreachableMarker) {
		t.Errorf("EventToolEnd.ResultDigest = %q; it must still carry the native failure (%q) — the model was told the peer is unreachable and the transcript may not say otherwise",
			digest, nativeUnreachableMarker)
	}
	if strings.Contains(digest, `"success":true`) {
		t.Errorf("EventToolEnd.ResultDigest rewrites the failed send as a success: %q. The recovery routes the message; it never fakes the native result", digest)
	}

	// And the recovery really did fire on this same stream — the two halves coexist.
	if sent := eventsOfKind(events, agentsession.EventPeerSent); len(sent) != 1 {
		t.Errorf("the SAME stream must carry both the reported native failure AND the recovered EventPeerSent; got %d EventPeerSent", len(sent))
	}
}
