//go:build lifecycle

package peerplane

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentsession"
)

// The plane's lifecycle probe (testMap #35): construct -> use over a REAL socket -> DOUBLE
// Close idempotent -> the socket goroutines return to baseline (goleak). It rides the
// `lifecycle` lane because Listen binds a real unix socket and SO_PEERCRED is Linux-only; the
// in-process client roundtrip here also CAPTURES the socket transport's coverage (client.go,
// listen.go, wire.go), which a sibling SUBPROCESS proof cannot.

// lifecycleClock is a real clock for the lifecycle root.
type lifecycleClock struct{}

func (lifecycleClock) Now() time.Time { return time.Now() }

// TestLifecycle_ConstructUseDoubleCloseGoleak drives the plane through its whole lifecycle and
// asserts the goroutine high-water returns to baseline after a double Close.
func TestLifecycle_ConstructUseDoubleCloseGoleak(t *testing.T) {
	defer goleak.VerifyNone(t) // registered first -> runs LAST, after every reap below

	ctx := context.Background()
	socket := filepath.Join(t.TempDir(), "mesh.sock")

	orchestrator, err := New(Config{SocketPath: socket, DeliveryDeadline: time.Second}, Deps{Clock: lifecycleClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	listenCtx, stopListen := context.WithCancel(ctx)
	// This reap runs BEFORE the deferred goleak (LIFO), so the listener/accept goroutines and
	// every accepted conn are gone before the goroutine high-water is asserted.
	defer func() {
		stopListen()
		_ = orchestrator.Close(ctx)       //nolint:errcheck // idempotent reap.
		time.Sleep(50 * time.Millisecond) // let the closed-conn reader goroutines unwind before goleak
	}()
	go func() { _ = orchestrator.Listen(listenCtx) }() //nolint:errcheck // Listen returns on ctx cancel.
	waitForSocketLifecycle(t, socket)

	// USE: two members dial the real socket, join, and exchange a message by MsgID.
	clientA, err := Dial(DialConfig{SocketPath: socket, JoinTimeout: 5 * time.Second}, Deps{Clock: lifecycleClock{}})
	if err != nil {
		t.Fatalf("Dial member-a: %v", err)
	}
	defer clientA.Close(ctx) //nolint:errcheck // idempotent reap (runs before goleak).
	clientB, err := Dial(DialConfig{SocketPath: socket, JoinTimeout: 5 * time.Second}, Deps{Clock: lifecycleClock{}})
	if err != nil {
		t.Fatalf("Dial member-b: %v", err)
	}
	defer clientB.Close(ctx) //nolint:errcheck // idempotent reap (runs before goleak).

	linkA, err := clientA.Join(ctx, "member-a", "")
	if err != nil {
		t.Fatalf("Join member-a: %v", err)
	}
	linkB, err := clientB.Join(ctx, "member-b", "")
	if err != nil {
		t.Fatalf("Join member-b: %v", err)
	}

	// Roster is readable over the wire and reports both members.
	roster, err := clientA.Roster(ctx, "member-a")
	if err != nil {
		t.Fatalf("Roster over socket: %v", err)
	}
	if len(roster) != 2 {
		t.Errorf("roster over socket has %d members, want 2: %+v", len(roster), roster)
	}

	msgID, err := linkA.Send(ctx, agentsession.PeerMessage{From: "member-a", To: "member-b", Body: "lifecycle"})
	if err != nil {
		t.Fatalf("Send over socket: %v", err)
	}
	got, ok := awaitInbound(t, linkB, 5*time.Second) // awaitInbound: reconciler_test.go (untagged, same package)
	if !ok {
		t.Fatal("member-b never received the socket-routed message")
	}
	if got.MsgID != msgID {
		t.Errorf("delivered MsgID = %q, want %q", got.MsgID, msgID)
	}
	linkB.Received(msgID)

	// DOUBLE Close is idempotent on both the client link and the orchestrator.
	if err := linkA.Close(ctx); err != nil {
		t.Errorf("client link Close: %v", err)
	}
	if err := linkA.Close(ctx); err != nil {
		t.Errorf("second client link Close must be idempotent: %v", err)
	}
	if err := orchestrator.Close(ctx); err != nil {
		t.Errorf("orchestrator Close: %v", err)
	}
	if err := orchestrator.Close(ctx); err != nil {
		t.Errorf("second orchestrator Close must be idempotent: %v", err)
	}
}

// waitForSocketLifecycle blocks until the orchestrator has bound the socket file.
func waitForSocketLifecycle(t *testing.T, socket string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(socket); err == nil {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("orchestrator never bound the socket %s", socket)
}
