package agentsession_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The SeededCanary sweep over the two NEW model-facing surfaces this slice adds: the peer
// message bodies that cross the plane, and the ROSTER the eden_peer_list host tool renders.
//
// The roster is the one of the two that is easy to get wrong. It is assembled by the LIBRARY
// from data the library holds — which includes the Spec, and therefore sits one careless field
// away from the credential reference, the workspace path and the session's own inbound queue.
// A roster that renders a struct instead of the five roster fields leaks whatever else that
// struct happened to carry, straight into the model's context.

// peerCanaryBody is a needle planted in an inbound peer body: untrusted foreign prose that a
// compromised peer could use to smuggle a value into a surface Eden renders for the model.
const peerCanaryBody = "SEEDED-CANARY-peer-body-9f8e7d6c-do-not-leak" // #nosec G101 -- a test redaction needle, not a real credential

// TestPeerCanary_RosterToolRendersOnlyRosterFields is test 10, library half. Two needles are in
// play at once: the CREDENTIAL the session resolved (canarySecret, from canary_test.go) and a
// peer BODY that already arrived on this session's plane. The roster the model is handed must
// contain neither.
//
// FALSIFICATION: rendering the Spec, the InjectedCredential, or anything derived from the
// session's inbound queue into the roster answer. Either needle appearing in the tool result is
// a value the model can read and repeat.
func TestPeerCanary_RosterToolRendersOnlyRosterFields(t *testing.T) {
	t.Parallel()
	plane := agentsessiontest.NewPeerPlane()
	sender, err := plane.Join(context.Background(), "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}

	adapter := newSpecRecordingAdapter(peerMessagingManifest(agentsession.CapFull),
		agentsessiontest.MessageEnd())
	session, err := newCanaryBindingPool(t, adapter, plane).Open(context.Background(), bindingSpec("review-c"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	// A peer body carrying a needle really does arrive on this session before the roster is read.
	if _, err := sender.Send(context.Background(), agentsession.PeerMessage{
		From: "impl-a", To: "review-c", Body: peerCanaryBody,
	}); err != nil {
		t.Fatalf("Send seeded peer body: %v", err)
	}

	tool, found := findHostTool(adapter.spawnedSpec(t).HostTools, peerListToolName)
	if !found {
		t.Fatalf("%s was not injected into the spawned Spec; tools: %v",
			peerListToolName, hostToolNames(adapter.spawnedSpec(t).HostTools))
	}
	if tool.Handler == nil {
		t.Fatalf("%s was injected with a nil Handler", peerListToolName)
	}
	roster, err := tool.Handler(context.Background(), []byte(`{}`))
	if err != nil {
		t.Fatalf("%s Handler: %v", peerListToolName, err)
	}
	rendered := string(roster)

	if strings.Contains(rendered, canarySecret) {
		t.Errorf("the credential canary leaked into the %s answer the MODEL reads: %q", peerListToolName, rendered)
	}
	if strings.Contains(rendered, peerCanaryBody) {
		t.Errorf("an inbound peer BODY leaked into the %s answer: %q. The roster answers WHO exists, never WHAT was said", peerListToolName, rendered)
	}
	if strings.Contains(rendered, peerBindingRef) {
		t.Errorf("the credential REFERENCE leaked into the %s answer: %q", peerListToolName, rendered)
	}
	// The roster must still be useful: it names the peers.
	for _, want := range []string{"impl-a", "review-c"} {
		if !strings.Contains(rendered, want) {
			t.Errorf("%s answered %q, which does not name the peer %q — a roster nothing can be addressed from is not a roster",
				peerListToolName, rendered, want)
		}
	}
}

// TestPeerCanary_CredentialNeverReachesAPeerEvent is the stream half: a session whose credential
// resolves to the needle exchanges real peer traffic, and NO event it publishes may carry the
// needle. It runs the whole-session sweep (AssertNoSecretInStream) rather than a field list, so
// a payload added later is covered without editing this test.
func TestPeerCanary_CredentialNeverReachesAPeerEvent(t *testing.T) {
	t.Parallel()
	plane := agentsessiontest.NewPeerPlane()
	adapter := newSpecRecordingAdapter(
		peerMessagingManifest(agentsession.CapFull),
		agentsessiontest.PeerSentEvent(agentsession.PeerMessage{
			MsgID: "msg-canary", To: "review-c", Body: "an ordinary body", Accepted: true,
		}),
		agentsessiontest.PeerMessageEvent(agentsession.PeerMessage{
			MsgID: "msg-canary-in", From: "review-c", Body: "an ordinary reply", Verified: true,
		}),
		peerTerminal(),
	)
	session, err := newCanaryBindingPool(t, adapter, plane).Open(context.Background(), bindingSpec("impl-a"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	ctx, cancel := context.WithTimeout(context.Background(), peerBindingDeadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}

	var published []agentsession.Event
	var sawPeer bool
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			break
		}
		published = append(published, event)
		if event.Kind == agentsession.EventPeerSent || event.Kind == agentsession.EventPeerMessage {
			sawPeer = true
		}
		if event.IsTerminal() {
			break
		}
	}
	if !sawPeer {
		t.Fatalf("no peer event reached the stream, so the sweep asserted nothing; kinds: %v", kindsOf(published))
	}
	agentsessiontest.AssertNoSecretInStream(t, published, canarySecret)
}

// newCanaryBindingPool builds a binding pool whose provider resolves the credential reference to
// the CANARY, so the needle is genuinely present in the resolve->inject seam this session ran.
func newCanaryBindingPool(t *testing.T, adapter agentsession.Adapter, plane agentsession.PeerPlane) *agentsession.Pool {
	t.Helper()
	key := agentsession.RouteKey{Role: "assistant"}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			key: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{peerBindingRef: canarySecret}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      bindingClock{},
			Peer:       plane,
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}
