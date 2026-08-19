//go:build harness

package agentsession_test

import (
	"context"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/peerplane"
)

// OBLIGATION B (design §9.2). Orchestrator + N sessions (EDEN_MESH_N, default 4 = 2 claude +
// 2 omp) in a REAL tree root -> 2 children -> 2 grandchildren, all mutually addressable.
// AUTHORED-NOT-RUN in libs CI (Fatal on a missing credential).

// meshMember is one node in the live tree.
type meshMember struct {
	name    string
	parent  string
	session agentsession.Session
}

// TestHarnessB_MeshAllPairsReachable is Obligation B: a real tree whose every node reaches
// every other (b reaches c although neither is the other's ancestor — the tree is registry +
// audit, never a reachability restriction), the roster contains NO stranger (the claude
// containment assertion), and the goroutine high-water returns to baseline.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set.
func TestHarnessB_MeshAllPairsReachable(t *testing.T) {
	defer goleak.VerifyNone(t)
	orchestrator := liveOrchestrator(t)
	claude := liveClaudePool(t, orchestrator)
	omp := liveOmpPool(t, orchestrator)

	// root -> {impl-a, review-c} -> {impl-a1, review-c1}: parentage IS the tree edge.
	members := []meshMember{
		{name: "impl-a", parent: ""},
		{name: "review-c", parent: ""},
		{name: "impl-a1", parent: "impl-a"},
		{name: "review-c1", parent: "review-c"},
	}
	pools := []*agentsession.Pool{claude, omp, claude, omp}
	for i := range members {
		members[i].session = openLivePeer(t, pools[i], members[i].name, members[i].parent)
	}

	// M1 parentage: every non-root node's Parent resolves in the roster.
	assertParentage(t, orchestrator, members)

	// ALL-PAIRS reachability: a grandchild of one subtree reaches a grandchild of another.
	driveSend(t, members[2].session, members[3].name, "cross-subtree")
	sent := sentMsgID(t, members[2].session, members[3].name, "cross-subtree", 60*time.Second)
	_ = awaitPeerWithin(t, members[3].session, members[2].name, "mesh", sent, 60*time.Second)

	// The roster contains NO stranger: only the four declared names.
	assertNoStranger(t, orchestrator, "impl-a", []string{"impl-a", "review-c", "impl-a1", "review-c1"})
}

// assertParentage asserts every member's declared Parent appears as its roster Parent (M1).
func assertParentage(t *testing.T, orchestrator *peerplane.Orchestrator, members []meshMember) {
	t.Helper()
	roster, err := orchestrator.Roster(context.Background(), "impl-a")
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	byName := map[string]agentsession.Peer{}
	for _, peer := range roster {
		byName[peer.Name] = peer
	}
	for _, member := range members {
		peer, ok := byName[member.name]
		if !ok {
			t.Errorf("M1: %q missing from the roster", member.name)
			continue
		}
		if peer.Parent != member.parent {
			t.Errorf("M1: %q Parent = %q, want %q", member.name, peer.Parent, member.parent)
		}
	}
}

// assertNoStranger asserts the roster seen from name contains exactly the allowed set — no
// stray host-roster session leaked into the eden mesh (the claude containment assertion).
func assertNoStranger(t *testing.T, orchestrator *peerplane.Orchestrator, name string, allowed []string) {
	t.Helper()
	permitted := map[string]bool{}
	for _, a := range allowed {
		permitted[a] = true
	}
	roster, err := orchestrator.Roster(context.Background(), name)
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	for _, peer := range roster {
		if !permitted[peer.Name] {
			t.Errorf("a STRANGER %q is in the eden roster — host-roster containment leaked", peer.Name)
		}
	}
	_ = time.Second
}
