package agentsession_test

import (
	"context"
	"encoding/json"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The LIBRARY half of the peer binding.
//
// STRUCTURAL FACT the whole design turns on: an Adapter cannot reach the plane. Adapter.Spawn
// receives no PeerLink, and Pool.Open calls Spawn (pool.go:81) BEFORE joinPeer (pool.go:95).
// So the eden_peer_send / eden_peer_list host-tool DEFINITIONS live in the LIBRARY and are
// injected by Pool.Open into its OWN COPY of spec.HostTools; they ride the harness's existing
// host-tool router unchanged. That is what these tests pin.

// The two host tools the library injects, named once here so a rename is one edit.
const (
	peerSendToolName = "eden_peer_send"
	peerListToolName = "eden_peer_list"
)

// peerBindingRef is the loggable credential reference the binding sessions open with.
const peerBindingRef = "vault://eden/anthropic#peer-binding" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// The FULL-MESH recovery seam. These literals are the contract between the two halves and are
// spelled identically in claudeadapter/peer_recovery_test.go, which pins that the REAL claude
// normalizer PRODUCES exactly this shape from the committed unreachable-send capture.
const (
	// peerRecoveryDetail is the redacted reason that marks an EventPeerSent as a routing
	// instruction rather than a receipt. It must differ from "send-receipt-unparsed", which
	// marks a send the native plane DID accept and which must never be re-routed.
	peerRecoveryDetail = "native-send-unreachable"

	// recoveredBody is the body of the committed unreachable-send fixture.
	recoveredBody = "PROBE-FULLMESH cross-harness body"

	// peerQuietWindow is how long the negative arm watches for a delivery that must never come.
	peerQuietWindow = 250 * time.Millisecond
)

// TestPeerHostTools_InjectedByDeclaredCapability is test 7. The gate is the ADAPTER'S OWN
// declared CapPeerMessaging status, not a hard-coded harness name: a harness whose model can
// drive Eden's host tools gets them, and one whose peer messaging is only partial (claude, whose
// model uses its NATIVE SendMessage instead) gets NEITHER — offering a model a tool its harness
// cannot honour is exactly the "declared but unproven" lie the manifest exists to prevent.
//
// The third arm is the aliasing pin. `append(spec.HostTools, ...)` on a slice with spare
// capacity writes THROUGH into the CALLER'S backing array — a caller that reuses its Spec for a
// second session would silently find Eden's tools in its own slice. The library must copy.
//
// FALSIFICATION: gating on route.Harness == "omp" (a new harness with a plane silently gets
// nothing), injecting unconditionally (a claude model is offered a tool it will never call and
// its --allowedTools would have to be widened, which the adapter is forbidden to do), or
// appending without copying (the caller's array is mutated).
func TestPeerHostTools_InjectedByDeclaredCapability(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name     string
		declared agentsession.CapStatus
		wantSend bool
		wantList bool
	}{
		{"CapFull gets both", agentsession.CapFull, true, true},
		{"CapPartial gets neither", agentsession.CapPartial, false, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			adapter := newSpecRecordingAdapter(peerMessagingManifest(tc.declared),
				agentsessiontest.MessageEnd())
			pool := newBindingPool(t, adapter, agentsessiontest.NewPeerPlane())

			// A caller slice with SPARE CAPACITY: an append-without-copy writes into it.
			callerTools := make([]agentsession.HostTool, 1, 4)
			callerTools[0] = agentsession.HostTool{Name: "project_lookup"}
			backing := callerTools[:cap(callerTools)]

			spec := bindingSpec("impl-a")
			spec.HostTools = callerTools
			session, err := pool.Open(context.Background(), spec)
			if err != nil {
				t.Fatalf("Open: %v", err)
			}
			t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

			spawned := adapter.spawnedSpec(t)
			if got := hasHostTool(spawned.HostTools, peerSendToolName); got != tc.wantSend {
				t.Errorf("%s injected into the spawned Spec = %v, want %v (adapter declares CapPeerMessaging=%v); tools: %v",
					peerSendToolName, got, tc.wantSend, tc.declared, hostToolNames(spawned.HostTools))
			}
			if got := hasHostTool(spawned.HostTools, peerListToolName); got != tc.wantList {
				t.Errorf("%s injected into the spawned Spec = %v, want %v (adapter declares CapPeerMessaging=%v); tools: %v",
					peerListToolName, got, tc.wantList, tc.declared, hostToolNames(spawned.HostTools))
			}
			// The caller's own tool always survives, whatever the gate decided.
			if !hasHostTool(spawned.HostTools, "project_lookup") {
				t.Errorf("the caller's own host tool was dropped; tools: %v", hostToolNames(spawned.HostTools))
			}

			// The caller's slice — length AND spare capacity — is untouched.
			if len(callerTools) != 1 {
				t.Errorf("the caller's HostTools slice grew to %d: Open must never mutate the caller's Spec", len(callerTools))
			}
			for i := 1; i < len(backing); i++ {
				if backing[i].Name != "" {
					t.Errorf("Open wrote %q into the caller's spare capacity at index %d — append(spec.HostTools, …) aliases the caller's array; copy first",
						backing[i].Name, i)
				}
			}
		})
	}
}

// TestPeerHostTool_SendMintsTheMessageID is test 8, the post-Join arm. The injected
// eden_peer_send is the omp-side counterpart of claude's native SendMessage: it drives the
// session's own PeerLink.Send and answers the model with the MsgID the plane minted, which is
// the id the receiver will see as its origin. Without that id in the answer the model has no
// way to reference what it just sent, and no correlation is possible at all.
//
// FALSIFICATION: answering with a locally-invented id (nothing on the plane knows it), or
// answering before the plane accepted (an unreachable peer would look sent).
func TestPeerHostTool_SendMintsTheMessageID(t *testing.T) {
	t.Parallel()
	plane := agentsessiontest.NewPeerPlane()
	receiver, err := plane.Join(context.Background(), "review-c", "")
	if err != nil {
		t.Fatalf("Join review-c: %v", err)
	}

	adapter := newSpecRecordingAdapter(peerMessagingManifest(agentsession.CapFull),
		agentsessiontest.MessageEnd())
	pool := newBindingPool(t, adapter, plane)
	session, err := pool.Open(context.Background(), bindingSpec("impl-a"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

	tool, found := findHostTool(adapter.spawnedSpec(t).HostTools, peerSendToolName)
	if !found {
		t.Fatalf("%s was not injected into the spawned Spec; tools: %v",
			peerSendToolName, hostToolNames(adapter.spawnedSpec(t).HostTools))
	}
	if tool.Handler == nil {
		t.Fatalf("%s was injected with a nil Handler: a tool the model can call and nothing can serve", peerSendToolName)
	}

	const body = "please review the pump change"
	result, err := tool.Handler(context.Background(),
		[]byte(`{"to":"review-c","body":"`+body+`"}`))
	if err != nil {
		t.Fatalf("%s Handler: %v", peerSendToolName, err)
	}
	var answer struct {
		MsgID string `json:"msg_id"`
	}
	if err := json.Unmarshal(result, &answer); err != nil {
		t.Fatalf("%s answered with something the model cannot read (%q): %v", peerSendToolName, result, err)
	}
	if answer.MsgID == "" {
		t.Fatalf("%s answered %q with no msg_id; the model cannot reference what it sent", peerSendToolName, result)
	}

	select {
	case delivered := <-receiver.Inbound():
		if delivered.MsgID != answer.MsgID {
			t.Errorf("the plane routed MsgID %q but the tool answered %q — the answer must be the id the plane MINTED, never a local invention",
				delivered.MsgID, answer.MsgID)
		}
		if delivered.From != "impl-a" {
			t.Errorf("delivered From = %q, want %q (the sending session's Spec.Name)", delivered.From, "impl-a")
		}
		if delivered.Body != body {
			t.Errorf("delivered Body = %q, want %q verbatim", delivered.Body, body)
		}
	case <-time.After(peerBindingDeadline):
		t.Fatalf("%s answered %q but the plane never routed anything to review-c within %s",
			peerSendToolName, result, peerBindingDeadline)
	}
}

// TestPeerRecovery_LibraryRoutesTheRecoveredSend is test 11, the DELIVERY half — and the
// COORDINATOR OVERRIDE's load-bearing obligation. Mateo ruled FULL MESH v1: A3 (claude -> omp)
// MUST deliver. Claude's native plane cannot reach a non-claude peer, so the adapter recovers
// {to, body} from the failed SendMessage and the LIBRARY — the only side holding a PeerLink —
// routes it over the bus.
//
// It asserts the DELIVERY, not the intent: the target peer's harness must actually be handed
// the body over the plane, through the real Pool / pump / deliver goroutine.
//
// THE SEAM between the two halves is the shape of the recovered EventPeerSent, and each half
// is pinned in its own package against the SAME literals:
//
//	produce — claudeadapter/peer_recovery_test.go asserts the REAL normalizer emits exactly
//	          EventPeerSent{To, Body, Accepted:false, Detail:"native-send-unreachable"} from the
//	          committed unreachable capture (claudeadapter's white-box seams are test-only, so
//	          this package cannot drive that normalizer directly).
//	route   — this test scripts exactly that event and asserts the library routes it.
//
// The second arm is the discrimination pin: an ORDINARY EventPeerSent (one the native plane
// really did accept) must NOT be routed, or every native message would be delivered twice.
//
// FALSIFICATION: a library that merely publishes the recovered fact produces a green "recovery"
// event and a peer that never hears anything — a one-way mesh wearing a full-mesh event. A
// library that routes every EventPeerSent double-delivers every accepted native send.
func TestPeerRecovery_LibraryRoutesTheRecoveredSend(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name        string
		sent        agentsession.PeerMessage
		wantRouted  bool
		wantMessage string
	}{
		{
			name: "recovered unreachable send is routed",
			sent: agentsession.PeerMessage{
				To:       "review-c",
				Body:     recoveredBody,
				Accepted: false,
				Detail:   peerRecoveryDetail,
			},
			wantRouted:  true,
			wantMessage: recoveredBody,
		},
		{
			name: "an accepted native send is NOT re-routed",
			sent: agentsession.PeerMessage{
				MsgID:    "de781fd3-d875-42be-8ae1-8ede89ad6f20",
				To:       "review-c",
				Body:     recoveredBody,
				Accepted: true,
			},
			wantRouted: false,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			plane := agentsessiontest.NewPeerPlane()

			// review-c: an idle receiving session on the same plane. Its fake adapter records
			// every control frame the library's deliver goroutine hands it.
			receiverAdapter := newSpecRecordingAdapter(peerMessagingManifest(agentsession.CapFull),
				agentsessiontest.MessageEnd())
			receiver, err := newBindingPool(t, receiverAdapter, plane).Open(context.Background(), bindingSpec("review-c"))
			if err != nil {
				t.Fatalf("Open review-c: %v", err)
			}
			t.Cleanup(func() { _ = receiver.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

			// impl-a: the claude session whose native send failed. CapPartial is what claude
			// declares — the recovery exists precisely because its plane cannot reach review-c.
			senderAdapter := newSpecRecordingAdapter(peerMessagingManifest(agentsession.CapPartial),
				agentsessiontest.PeerSentEvent(tc.sent), peerTerminal())
			sender, err := newBindingPool(t, senderAdapter, plane).Open(context.Background(), bindingSpec("impl-a"))
			if err != nil {
				t.Fatalf("Open impl-a: %v", err)
			}
			t.Cleanup(func() { _ = sender.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.

			ctx, cancel := context.WithTimeout(context.Background(), peerBindingDeadline)
			defer cancel()
			stream := sender.Events(ctx, agentsession.FromSeq(0))
			if _, err := sender.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "message review-c"}); err != nil {
				t.Fatalf("Prompt: %v", err)
			}
			for {
				event, ok := stream.Next(ctx)
				if !ok || event.IsTerminal() {
					break
				}
			}

			if !tc.wantRouted {
				assertNoPeerDelivery(t, receiverAdapter, peerQuietWindow)
				return
			}
			delivered := awaitPeerDelivery(t, receiverAdapter, peerBindingDeadline)
			from, _, _, _, body, _, ok := controlframe.DecodePeer(delivered)
			if !ok {
				t.Fatalf("review-c received %q, which is not a peer control frame", delivered)
			}
			if from != "impl-a" {
				t.Errorf("delivered From = %q, want %q — the library routes it, so From is the SENDING SESSION's name, never the model's claim", from, "impl-a")
			}
			if body != tc.wantMessage {
				t.Errorf("delivered body = %q, want %q — the body recovered from the failed native send, verbatim", body, tc.wantMessage)
			}
		})
	}
}

// assertNoPeerDelivery watches for a quiet window and fails if any peer frame arrives.
func assertNoPeerDelivery(t *testing.T, adapter *specRecordingAdapter, within time.Duration) {
	t.Helper()
	deadline := time.Now().Add(within)
	for time.Now().Before(deadline) {
		for _, command := range adapter.Received() {
			if strings.HasPrefix(command.Text, controlframe.PeerPrefix) {
				t.Fatalf("an ALREADY-ACCEPTED native send was routed over the plane as well: %q — the peer receives it twice", command.Text)
			}
		}
		time.Sleep(5 * time.Millisecond)
	}
}

// awaitPeerDelivery waits until the receiving session's adapter has been handed a peer control
// frame, or FAILS naming every frame it did receive. It never returns quietly on a timeout: a
// silent empty result here would read as "no delivery expected", which is the opposite of what
// this test asserts.
func awaitPeerDelivery(t *testing.T, adapter *specRecordingAdapter, within time.Duration) string {
	t.Helper()
	deadline := time.Now().Add(within)
	for {
		var seen []string
		for _, command := range adapter.Received() {
			if strings.HasPrefix(command.Text, controlframe.PeerPrefix) {
				return command.Text
			}
			seen = append(seen, command.Text)
		}
		if time.Now().After(deadline) {
			t.Fatalf("review-c's harness received no peer delivery within %s; it received: %v — the recovered send was published but never ROUTED",
				within, seen)
		}
		time.Sleep(5 * time.Millisecond)
	}
}

// ── binding helpers ───────────────────────────────────────────────────────────────────────────.

// peerBindingDeadline bounds every wait in this file. A wait that runs out is a FAILURE naming
// what never arrived, never a quiet return.
const peerBindingDeadline = 5 * time.Second

// specRecordingAdapter is the canonical fake with ONE addition: it records the Spec each Spawn
// was handed. That Spec is the only place a test can observe what the LIBRARY injected, because
// injection happens inside Pool.Open, between the caller's Spec and the adapter's Spawn.
type specRecordingAdapter struct {
	*agentsessiontest.Adapter

	mu     sync.Mutex
	spawns []agentsession.Spec
}

// newSpecRecordingAdapter builds the recording fake with a declared manifest and a script.
//
//nolint:gocritic // CapabilityManifest is the contract's copyable DATA record; the fake mirrors the by-value seam.
func newSpecRecordingAdapter(manifest agentsession.CapabilityManifest, script ...agentsession.Event) *specRecordingAdapter {
	return &specRecordingAdapter{Adapter: agentsessiontest.New(script...).WithManifest(manifest)}
}

// Spawn records the Spec, then delegates to the canonical fake.
//
//nolint:gocritic,ireturn // contract §2/§3: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the fake mirrors the frozen seam.
func (a *specRecordingAdapter) Spawn(ctx context.Context, spec agentsession.Spec, route agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	a.mu.Lock()
	a.spawns = append(a.spawns, spec)
	a.mu.Unlock()
	return a.Adapter.Spawn(ctx, spec, route, cred)
}

// spawnedSpec returns the Spec the single Spawn was handed, failing when there was not exactly one.
func (a *specRecordingAdapter) spawnedSpec(t *testing.T) agentsession.Spec {
	t.Helper()
	a.mu.Lock()
	defer a.mu.Unlock()
	if len(a.spawns) != 1 {
		t.Fatalf("expected exactly one Spawn, got %d", len(a.spawns))
	}
	return a.spawns[0]
}

// peerMessagingManifest declares CapPeerMessaging at the given status and every other
// capability CapFull, so the gate under test is the peer status alone.
func peerMessagingManifest(status agentsession.CapStatus) agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapFull,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapFull,
		agentsession.CapNativeBudget:       agentsession.CapFull,
		agentsession.CapPermissionPrompt:   agentsession.CapFull,
		agentsession.CapPartialToolResults: agentsession.CapFull,
		agentsession.CapPeerMessaging:      status,
	}}
}

// newBindingPool builds a Pool over the recording adapter and an INJECTED plane, so several
// sessions in one test can share one plane and actually reach each other.
func newBindingPool(t *testing.T, adapter agentsession.Adapter, plane agentsession.PeerPlane) *agentsession.Pool {
	t.Helper()
	key := agentsession.RouteKey{Role: "assistant"}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			key: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{peerBindingRef: agentsessiontest.SeededCanary}),
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

// bindingSpec is the session spec one addressable peer opens with.
func bindingSpec(name string) agentsession.Spec {
	return agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Name:       name,
		Credential: secrets.Ref(peerBindingRef),
	}
}

// bindingClock is a deterministic Clock for the binding pools.
type bindingClock struct{}

func (bindingClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// hasHostTool reports whether a host-tool set contains a name.
func hasHostTool(tools []agentsession.HostTool, name string) bool {
	_, found := findHostTool(tools, name)
	return found
}

// findHostTool returns the named host tool.
func findHostTool(tools []agentsession.HostTool, name string) (agentsession.HostTool, bool) {
	for i := range tools {
		if tools[i].Name == name {
			return tools[i], true
		}
	}
	return agentsession.HostTool{}, false
}

// hostToolNames lists a host-tool set's names for a failure message.
func hostToolNames(tools []agentsession.HostTool) []string {
	names := make([]string, 0, len(tools))
	for i := range tools {
		names = append(names, tools[i].Name)
	}
	return names
}
