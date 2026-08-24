//go:build harness

package agentsession_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/peerplane"
	"github.com/gophersys/libs/go/errors"
)

// OBLIGATION C (design §9.2). Per harness: a parent spawns a REAL subagent, messages it, and
// the child answers — proving the subagent channel end to end AND its NON-CONFLATION with the
// peer plane. AUTHORED-NOT-RUN in libs CI (Fatal on a missing credential). The load-bearing
// negatives are S3 (no subagent id in the roster) and S4 (no EventPeerMessage for subagent
// traffic) — the real-substrate proof of design §8.

// TestHarnessC_SubagentIsDistinctFromPeer is Obligation C, run per harness.
func TestHarnessC_SubagentIsDistinctFromPeer(t *testing.T) {
	orchestrator := liveOrchestrator(t)
	t.Run("claude", func(t *testing.T) {
		runSubagentObligation(t, orchestrator, liveClaudePool(t, orchestrator))
	})
	t.Run("omp", func(t *testing.T) {
		runSubagentObligation(t, orchestrator, liveOmpPool(t, orchestrator))
	})
}

// runSubagentObligation drives one parent session through S1/S3/S4/S5 for one harness.
func runSubagentObligation(t *testing.T, orchestrator *peerplane.Orchestrator, pool *agentsession.Pool) {
	t.Helper()
	parent := openLivePeer(t, pool, "impl-a", "")

	// Drive the parent to spawn a subagent and message it (S1).
	if _, err := parent.Control(context.Background(), agentsession.Command{
		Kind: agentsession.CommandPrompt,
		Text: "Spawn a subagent to summarize the repository, then send it the instruction to begin.",
	}); err != nil {
		t.Fatalf("drive subagent spawn: %v", err)
	}

	sub := awaitSubagentWithin(t, parent, 90*time.Second)
	if sub.SubagentID == "" {
		t.Fatal("S1: EventSubagentMessage carried no SubagentID")
	}

	// S3 NON-CONFLATION: the subagent id is NEVER in the peer roster.
	roster, err := orchestrator.Roster(context.Background(), "impl-a")
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	for _, peer := range roster {
		if peer.Name == sub.SubagentID {
			t.Errorf("S3: subagent id %q appeared in the peer Roster", sub.SubagentID)
		}
	}

	// S5: a PEER send addressed to the subagent id resolves to no roster entry ->
	// UnreachableError. The probe joins the plane in-process to obtain a link.
	probe, err := orchestrator.Join(context.Background(), "subagent-probe", "")
	if err != nil {
		t.Fatalf("Join probe: %v", err)
	}
	_, sendErr := probe.Send(context.Background(), agentsession.PeerMessage{From: "subagent-probe", To: sub.SubagentID, Body: "reach a subagent"})
	if !errors.IsType[agentsession.UnreachableError](sendErr) {
		t.Fatalf("S5: a peer Send to a subagent id must be UnreachableError, got %v (%T)", sendErr, sendErr)
	}
}

// awaitSubagentWithin scans a parent's stream for an EventSubagentMessage, asserting S4 along
// the way: subagent traffic NEVER surfaces as EventPeerMessage.
//
//nolint:gocritic // agentsession.SubagentMessage is the contract's copyable value; returned by value.
func awaitSubagentWithin(t *testing.T, session agentsession.Session, deadline time.Duration) agentsession.SubagentMessage {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), deadline)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			t.Fatalf("no EventSubagentMessage within %s", deadline)
		}
		if event.Kind == agentsession.EventPeerMessage {
			t.Errorf("S4: subagent traffic surfaced as EventPeerMessage — the channels are conflated")
		}
		if event.Kind == agentsession.EventSubagentMessage && event.Subagent != nil {
			return *event.Subagent
		}
	}
}
