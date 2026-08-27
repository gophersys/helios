package agentsession_test

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// MANIFEST TRUTHFULNESS for CapPeerMessaging (05 §3).
//
// The frozen .apibaseline is BLIND to this: adding a map entry to a CapabilityManifest changes
// no exported symbol, so apidiff stays green while an adapter starts advertising a capability
// nothing implements. The manifest is DATA, and data can lie. This table is the only mechanical
// thing standing between a declaration and a promise: every status an adapter declares must be
// bound to an executable proof arm, and a status with no arm is a FAILURE — not a gap.
//
// The arms prove the LIBRARY-SEAM half of each claim (what a consumer gets when it wires that
// adapter with a plane). The WIRE half of each claim is proven in the adapter's own package:
// claudeadapter/peer_test.go for the native origin/receipt binding, ompadapter/peer_test.go for
// the envelope delivery.

// peerMessagingProofArm is a runnable proof of one declared CapPeerMessaging status. Every
// status any adapter declares MUST have one.
type peerMessagingProofArm struct {
	// what names the promise the status makes, so a failure says which promise broke.
	what string
	// prove runs the promise against the real library and the in-memory plane.
	prove func(t *testing.T, status agentsession.CapStatus)
}

// peerMessagingProofArms binds each declarable status to its proof. CapAbsent has NO arm on
// purpose: "absent" is not a claim a peer binding may make once the binding exists, so an
// adapter still declaring CapAbsent falls through to the no-arm failure below.
var peerMessagingProofArms = map[agentsession.CapStatus]peerMessagingProofArm{
	agentsession.CapPartial: {
		what:  "reachable INBOUND over the plane, but Eden injects NO peer host tools (the model uses the harness's own send)",
		prove: provePartialPeerMessaging,
	},
	agentsession.CapFull: {
		what:  "Eden injects the peer host tools AND a send through them is routed by the plane",
		prove: proveFullPeerMessaging,
	},
}

// TestPeerManifest_EveryDeclaredStatusHasAProofArm is test 9. It walks the two real adapters,
// reads what each DECLARES for CapPeerMessaging, and refuses any declaration it cannot execute.
//
// FALSIFICATION: declaring CapFull on claude (whose model cannot be given Eden host tools
// without widening --allowedTools, which the adapter is forbidden to do), or leaving either
// adapter at CapAbsent after shipping a peer binding — the manifest would then under-declare a
// working capability and every consumer would gate the feature off.
func TestPeerManifest_EveryDeclaredStatusHasAProofArm(t *testing.T) {
	t.Parallel()

	claude, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		t.Fatalf("claudeadapter.New: %v", err)
	}
	omp, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		t.Fatalf("ompadapter.New: %v", err)
	}

	adapters := []struct {
		harness  string
		manifest agentsession.CapabilityManifest
		want     agentsession.CapStatus
		why      string
	}{
		{
			harness:  "claude-code",
			manifest: claude.Manifest(),
			want:     agentsession.CapPartial,
			why:      "claude rides its NATIVE cross-session plane: it is addressable and receives, but a cross-harness send from a claude model is out of scope for v1 (the library recovers that one)",
		},
		{
			harness:  "omp",
			manifest: omp.Manifest(),
			want:     agentsession.CapFull,
			why:      "omp carries peer traffic on the LIBRARY-owned plane through host tools on its rpc router — Eden owns both ends",
		},
	}

	for _, adapter := range adapters {
		t.Run(adapter.harness, func(t *testing.T) {
			t.Parallel()
			declared := adapter.manifest.Status(agentsession.CapPeerMessaging)
			if declared == agentsession.CapAbsent {
				t.Fatalf("%s declares CapPeerMessaging=CapAbsent. A shipped peer binding that declares nothing is a capability every consumer gates OFF: %s",
					adapter.harness, adapter.why)
			}
			if declared != adapter.want {
				t.Errorf("%s declares CapPeerMessaging=%v, want %v — %s", adapter.harness, declared, adapter.want, adapter.why)
			}
			arm, found := peerMessagingProofArms[declared]
			if !found {
				t.Fatalf("%s declares CapPeerMessaging=%v and NO proof arm is registered for that status. A declaration nothing executes is a promise nothing keeps",
					adapter.harness, declared)
			}
			arm.prove(t, declared)
		})
	}
}

// provePartialPeerMessaging is the CapPartial arm: the session is a real member of the plane
// (a peer can reach it), and Eden injects NO host tools — the harness's own messaging is the
// outbound path, so offering Eden's would be a second, unauthorized one.
func provePartialPeerMessaging(t *testing.T, status agentsession.CapStatus) {
	t.Helper()
	plane := agentsessiontest.NewPeerPlane()
	adapter := newSpecRecordingAdapter(peerMessagingManifest(status), agentsessiontest.MessageEnd())
	session, err := newBindingPool(t, adapter, plane).Open(context.Background(), bindingSpec("review-c"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	spawned := adapter.spawnedSpec(t)
	for _, name := range []string{peerSendToolName, peerListToolName} {
		if hasHostTool(spawned.HostTools, name) {
			t.Errorf("CapPartial must inject NO peer host tool, but %s was injected; tools: %v", name, hostToolNames(spawned.HostTools))
		}
	}

	// It is nonetheless a real member: another peer can address it and the delivery lands.
	sender, err := plane.Join(context.Background(), "impl-a", "")
	if err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := sender.Send(context.Background(), agentsession.PeerMessage{
		From: "impl-a", To: "review-c", Body: "reachable?",
	}); err != nil {
		t.Fatalf("a CapPartial session must still be REACHABLE on the plane, but Send failed: %v", err)
	}
	awaitPeerDelivery(t, adapter, peerBindingDeadline)
}

// proveFullPeerMessaging is the CapFull arm: Eden injects both peer host tools and a send
// driven through eden_peer_send is actually routed by the plane.
func proveFullPeerMessaging(t *testing.T, status agentsession.CapStatus) {
	t.Helper()
	plane := agentsessiontest.NewPeerPlane()
	receiver, err := plane.Join(context.Background(), "review-c", "")
	if err != nil {
		t.Fatalf("Join review-c: %v", err)
	}
	adapter := newSpecRecordingAdapter(peerMessagingManifest(status), agentsessiontest.MessageEnd())
	session, err := newBindingPool(t, adapter, plane).Open(context.Background(), bindingSpec("impl-a"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	spawned := adapter.spawnedSpec(t)
	for _, name := range []string{peerSendToolName, peerListToolName} {
		if !hasHostTool(spawned.HostTools, name) {
			t.Fatalf("CapFull must inject %s; tools: %v", name, hostToolNames(spawned.HostTools))
		}
	}
	tool, _ := findHostTool(spawned.HostTools, peerSendToolName)
	if tool.Handler == nil {
		t.Fatalf("%s was injected with a nil Handler", peerSendToolName)
	}
	result, err := tool.Handler(context.Background(), []byte(`{"to":"review-c","body":"cap-full proof"}`))
	if err != nil {
		t.Fatalf("%s Handler: %v", peerSendToolName, err)
	}
	var answer struct {
		MsgID string `json:"msg_id"`
	}
	if err := json.Unmarshal(result, &answer); err != nil || answer.MsgID == "" {
		t.Fatalf("%s answered %q, which carries no msg_id", peerSendToolName, result)
	}
	select {
	case delivered := <-receiver.Inbound():
		if delivered.Body != "cap-full proof" {
			t.Errorf("routed body = %q, want %q", delivered.Body, "cap-full proof")
		}
	case <-time.After(peerBindingDeadline):
		t.Fatalf("CapFull declares the plane carries the traffic, but nothing reached review-c within %s", peerBindingDeadline)
	}
}
