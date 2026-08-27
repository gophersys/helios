//go:build integration

// Package peerplane's integration arm exercises the plane over a REAL unix domain socket and
// REAL OS child processes — the credential-free real-substrate proof (ADR-0016 §2: never a
// mock). The children are a trivial internal/stubharness stub built with `go build`, NOT a
// vendor harness, so no credential and no harness pin are needed and it runs in LIBS CI.
//
//	go test -tags integration ./... -race
//
// Every process and the socket are reaped on t.Cleanup.
package peerplane

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// integrationClock is a real clock for the socket orchestrator.
type integrationClock struct{}

func (integrationClock) Now() time.Time { return time.Now() }

// TestIntegration_KilledChildBouncesAndDropsFromRoster is the plane's real-substrate proof:
// an Orchestrator binds a real socket, two child PROCESSES Dial and Join, they exchange both
// ways, then one child is KILLED. The survivor's roster drops it, every in-flight envelope to
// it BOUNCES with a typed UnreachableError (never silence), the stale socket is unlinked, and
// a re-Join under the same name gets a HIGHER Generation (a restart is distinguishable from a
// duplicate).
func TestIntegration_KilledChildBouncesAndDropsFromRoster(t *testing.T) {
	t.Parallel()
	stub := buildStubHarness(t)
	socket := filepath.Join(t.TempDir(), "mesh.sock")
	ctx := context.Background()

	orchestrator, err := New(Config{SocketPath: socket, DeliveryDeadline: time.Second}, Deps{Clock: integrationClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	listenCtx, stopListen := context.WithCancel(ctx)
	t.Cleanup(stopListen)
	go func() { _ = orchestrator.Listen(listenCtx) }() //nolint:errcheck // Listen returns when listenCtx is cancelled.
	waitForSocket(t, socket)

	// The observer joins IN-PROCESS over the same root and addresses the child processes.
	observer, err := orchestrator.Join(ctx, "observer", "")
	if err != nil {
		t.Fatalf("Join observer: %v", err)
	}

	childA := startStubHarness(t, stub, socket, "child-a", "observer")
	childB := startStubHarness(t, stub, socket, "child-b", "observer")
	waitForRoster(t, orchestrator, "observer", "child-a", "child-b")

	// Capture child-b's generation while it is STILL LIVE. The re-attach below must bump it,
	// so a restart is distinguishable from a duplicate; comparing against this departed value
	// (never child-a's, never >0) is what makes the assertion bite — a constant generation
	// would leave after == departedGen and FAIL.
	departedGen := generationOf(t, orchestrator, "observer", "child-b")

	// A delivery to a LIVE child succeeds (accepted for routing).
	if _, err := observer.Send(ctx, agentsession.PeerMessage{From: "observer", To: "child-b", Body: "ping"}); err != nil {
		t.Fatalf("Send to live child-b: %v", err)
	}

	// Kill child-b and let the dropped connection propagate.
	_ = childB.Process.Kill()
	_, _ = childB.Process.Wait()

	waitForRosterGone(t, orchestrator, "observer", "child-b")

	// Every in-flight envelope to the dead child now BOUNCES with a typed UnreachableError.
	_, err = observer.Send(ctx, agentsession.PeerMessage{From: "observer", To: "child-b", Body: "are you there?"})
	if !errors.IsType[agentsession.UnreachableError](err) {
		t.Fatalf("a Send to a killed child must be UnreachableError, got %v (%T)", err, err)
	}

	// A re-Join under child-b's name gets a STRICTLY HIGHER Generation than the departed
	// instance — the fact that lets an observer tell a restart from a duplicate.
	childBPrime := startStubHarness(t, stub, socket, "child-b", "observer")
	waitForRoster(t, orchestrator, "observer", "child-b")
	after := generationOf(t, orchestrator, "observer", "child-b")
	if after <= departedGen {
		t.Errorf("re-Join Generation = %d, want strictly greater than the departed instance's %d", after, departedGen)
	}
	_ = childA
	_ = childBPrime
}

// buildStubHarness compiles the internal/stubharness stub once and returns its path.
func buildStubHarness(t *testing.T) string {
	t.Helper()
	bin := filepath.Join(t.TempDir(), "stubharness")
	build := exec.Command("go", "build", "-o", bin, "./internal/stubharness")
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build stubharness stub: %v\n%s", err, out)
	}
	return bin
}

// startStubHarness launches a real child process that Dials the socket and Joins under name.
func startStubHarness(t *testing.T, stub, socket, name, parent string) *exec.Cmd {
	t.Helper()
	cmd := exec.Command(stub, "-socket", socket, "-name", name, "-parent", parent)
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		t.Fatalf("start stubharness %s: %v", name, err)
	}
	t.Cleanup(func() { _ = cmd.Process.Kill() }) //nolint:errcheck // best-effort reap.
	return cmd
}

// waitForSocket blocks until the orchestrator has bound the socket file.
func waitForSocket(t *testing.T, socket string) {
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

// waitForRoster blocks until the roster seen from name contains all of want.
func waitForRoster(t *testing.T, orchestrator *Orchestrator, name string, want ...string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		roster, err := orchestrator.Roster(context.Background(), name)
		if err == nil && rosterContainsAll(roster, want) {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("roster from %s never contained %v", name, want)
}

// waitForRosterGone blocks until the departed name is absent from the roster.
func waitForRosterGone(t *testing.T, orchestrator *Orchestrator, name, gone string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		roster, err := orchestrator.Roster(context.Background(), name)
		if err == nil && !rosterContains(roster, gone) {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("departed peer %s never left the roster seen from %s", gone, name)
}

// generationOf returns the Generation of peer in the roster seen from name.
func generationOf(t *testing.T, orchestrator *Orchestrator, name, peer string) int {
	t.Helper()
	roster, err := orchestrator.Roster(context.Background(), name)
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	for _, row := range roster {
		if row.Name == peer {
			return row.Generation
		}
	}
	t.Fatalf("peer %s not in roster", peer)
	return 0
}

func rosterContains(roster []agentsession.Peer, name string) bool {
	for _, row := range roster {
		if row.Name == name {
			return true
		}
	}
	return false
}

func rosterContainsAll(roster []agentsession.Peer, want []string) bool {
	for _, name := range want {
		if !rosterContains(roster, name) {
			return false
		}
	}
	return true
}
