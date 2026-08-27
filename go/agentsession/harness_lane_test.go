//go:build harness

// The harness lane (ADR-0020 §9.1 / ADR-0021): REAL harness processes + REAL models, with
// ZERO skip path in existence. A missing credential is a t.Fatalf naming the variable, never
// a t.Skip — a test that cannot run is a failure, not a pass. This lane does NOT run in libs
// CI (no credential, no harness pin); it runs in eden's harness-conformance at PR-2. It is
// authored here, red-first, so the obligations land with the contract they prove.
package agentsession_test

import (
	"context"
	"os/exec"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/agentsession/peerplane"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The credential variables this lane REQUIRES. require_env at the ctl.sh boundary and
// RequireLiveCredential in-test both FAIL, naming the variable, when one is unset.
const (
	claudeLiveToken = "CLAUDEADAPTER_LIVE_TOKEN"
	openRouterKey   = "OPENROUTER_API_KEY"
)

// harnessClock is a real clock for the live pools.
type harnessClock struct{}

func (harnessClock) Now() time.Time { return time.Now() }

// requirePinnedBinary FAILS (never skips) when the harness binary is absent — the FAIL-NOT-
// SKIP rule at the binary boundary. The pinned version is asserted by eden's harness-
// conformance; here we assert presence, naming the binary.
func requirePinnedBinary(t *testing.T, name string) {
	t.Helper()
	if _, err := exec.LookPath(name); err != nil {
		t.Fatalf("harness binary %q not on PATH: the harness lane requires it (never a skip)", name)
	}
}

// liveOrchestrator builds and Listens the tree ROOT over a real socket, reaped on Cleanup.
func liveOrchestrator(t *testing.T) *peerplane.Orchestrator {
	t.Helper()
	orchestrator, err := New1c(peerplane.Config{SocketPath: t.TempDir() + "/mesh.sock", DeliveryDeadline: 30 * time.Second},
		peerplane.Deps{Clock: harnessClock{}})
	if err != nil {
		t.Fatalf("peerplane.New: %v", err)
	}
	listenCtx, stopListen := context.WithCancel(context.Background())
	t.Cleanup(stopListen)
	go func() { _ = orchestrator.Listen(listenCtx) }() //nolint:errcheck // Listen returns on ctx cancel.
	return orchestrator
}

// New1c wraps peerplane.New so the lane reads as one call site (the tree root constructor).
func New1c(configuration peerplane.Config, dependencies peerplane.Deps) (*peerplane.Orchestrator, error) {
	return peerplane.New(configuration, dependencies)
}

// liveClaudePool builds a REAL claude-code pool wired to the peer plane. The token is taken
// verbatim from the operator env via RequireLiveCredential — never minted here.
func liveClaudePool(t *testing.T, orchestrator *peerplane.Orchestrator) *agentsession.Pool {
	t.Helper()
	token := agentsessiontest.RequireLiveCredential(t, claudeLiveToken)
	requirePinnedBinary(t, "claude")
	adapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		t.Fatalf("claudeadapter.New: %v", err)
	}
	return livePool(t, "claude-code", adapter, orchestrator, token)
}

// liveOmpPool builds a REAL omp pool wired to the peer plane.
func liveOmpPool(t *testing.T, orchestrator *peerplane.Orchestrator) *agentsession.Pool {
	t.Helper()
	key := agentsessiontest.RequireLiveCredential(t, openRouterKey)
	requirePinnedBinary(t, "omp")
	adapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		t.Fatalf("ompadapter.New: %v", err)
	}
	return livePool(t, "omp", adapter, orchestrator, key)
}

// livePool constructs a Pool over a real adapter with the peer plane injected.
func livePool(t *testing.T, harness string, adapter agentsession.Adapter, orchestrator *peerplane.Orchestrator, token string) *agentsession.Pool {
	t.Helper()
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: harness, Model: "live"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{harness: adapter},
			Secrets:    secretstest.New(map[string]string{"vault://eden/live#token": token}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      harnessClock{},
			Peer:       orchestrator,
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}
	return pool
}

// openLivePeer opens a live session with a caller-assigned peer Name/Parent, per-session
// t.TempDir() workspace (MANDATORY: <ws>/.omp-session collides otherwise), a cost ceiling so
// a runaway mesh cannot burn money, and reaps it on Cleanup.
//
//nolint:ireturn // returns the agentsession.Session port.
func openLivePeer(t *testing.T, pool *agentsession.Pool, name, parent string) agentsession.Session {
	t.Helper()
	session, err := pool.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Name:       name,
		Parent:     parent,
		Budget:     agentsession.Budget{MaxCostMicros: 2_000_000},
		Credential: secrets.Ref("vault://eden/live#token"),
	})
	if err != nil {
		t.Fatalf("live Open(name=%q): %v", name, err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort reap.
	return session
}

// awaitPeerWithin scans a session's live stream for an EventPeerMessage carrying msgID. The
// deadline branch is an ERROR that NAMES the msg_id, the peer, and the transport — never a
// partial return that a caller could read as success.
//
//nolint:gocritic // agentsession.PeerMessage is the contract's copyable value; returned by value.
func awaitPeerWithin(t *testing.T, session agentsession.Session, peer, transport, msgID string, deadline time.Duration) agentsession.PeerMessage {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), deadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("no EventPeerMessage msg_id=%q from peer=%q over transport=%q within %s", msgID, peer, transport, deadline)
		}
		if event.Kind == agentsession.EventPeerMessage && event.Peer != nil && event.Peer.MsgID == msgID {
			return *event.Peer
		}
	}
}

// sentMsgID drives a session to send a peer message and returns the observed EventPeerSent
// MsgID (the sender-side receipt id that must equal the receiver's origin id).
func sentMsgID(t *testing.T, session agentsession.Session, to, body string, deadline time.Duration) string {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), deadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("no EventPeerSent to peer=%q within %s", to, deadline)
		}
		if event.Kind == agentsession.EventPeerSent && event.Peer != nil && event.Peer.To == to {
			return event.Peer.MsgID
		}
	}
}
