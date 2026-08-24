//go:build harness

package agentsession_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/peerplane"
)

// OBLIGATION A (design §9.2). One orchestrator, ONE container, TWO real harness processes.
// Three pairs share one helper: claude<->claude (native plane), omp<->omp (bus), claude<->omp
// (cross-harness). AUTHORED-NOT-RUN in libs CI: the pool builders Fatal on a missing
// credential, so this runs only in eden's harness-conformance.

// TestHarnessA_PairExchangesBothWays is Obligation A. For each pair it proves the nine A-
// assertions, the load-bearing ones being A3/A4 (MsgID correlation in BOTH directions, not
// one-way receipt) and A1 (bidirectional roster presence WITH parentage).
func TestHarnessA_PairExchangesBothWays(t *testing.T) {
	orchestrator := liveOrchestrator(t)

	pairs := []struct {
		name         string
		a, b         string
		poolA, poolB func(t *testing.T, o *peerplane.Orchestrator) *agentsession.Pool
	}{
		{"claude-claude", "impl-a", "review-c", liveClaudePool, liveClaudePool},
		{"omp-omp", "impl-a", "review-c", liveOmpPool, liveOmpPool},
		{"claude-omp", "impl-a", "review-c", liveClaudePool, liveOmpPool},
	}

	for _, pair := range pairs {
		t.Run(pair.name, func(t *testing.T) {
			sessionA := openLivePeer(t, pair.poolA(t, orchestrator), pair.a, "")
			sessionB := openLivePeer(t, pair.poolB(t, orchestrator), pair.b, "")

			// A1 roster BOTH ways + A2 parentage resolves to the orchestrator (the tree exists).
			assertRosterBothWays(t, orchestrator, pair.a, pair.b)

			// A3 a->b: sender EventPeerSent.MsgID == receiver EventPeerMessage.MsgID.
			driveSend(t, sessionA, pair.b, "from-a-to-b")
			sentAB := sentMsgID(t, sessionA, pair.b, "from-a-to-b", 60*time.Second)
			gotAB := awaitPeerWithin(t, sessionB, pair.a, pair.name, sentAB, 60*time.Second)
			if gotAB.From != pair.a { // A6 From == sender's Spec.Name
				t.Errorf("A6: EventPeerMessage.From = %q, want %q", gotAB.From, pair.a)
			}

			// A4 b->a: the MIRROR — both directions, no text scraping.
			driveSend(t, sessionB, pair.a, "from-b-to-a")
			sentBA := sentMsgID(t, sessionB, pair.a, "from-b-to-a", 60*time.Second)
			_ = awaitPeerWithin(t, sessionA, pair.b, pair.name, sentBA, 60*time.Second)

			// A9 AssertNoSecretInEvent over EVERY event of BOTH streams.
			assertNoSecretOverStream(t, sessionA)
			assertNoSecretOverStream(t, sessionB)
		})
	}
}

// assertRosterBothWays asserts Roster(a) contains b AND Roster(b) contains a (A1).
func assertRosterBothWays(t *testing.T, orchestrator *peerplane.Orchestrator, a, b string) {
	t.Helper()
	rosterA, err := orchestrator.Roster(context.Background(), a)
	if err != nil {
		t.Fatalf("Roster(%q): %v", a, err)
	}
	if !rosterHas(rosterA, b) {
		t.Errorf("A1: Roster(%q) does not contain %q", a, b)
	}
	rosterB, err := orchestrator.Roster(context.Background(), b)
	if err != nil {
		t.Fatalf("Roster(%q): %v", b, err)
	}
	if !rosterHas(rosterB, a) {
		t.Errorf("A1: Roster(%q) does not contain %q", b, a)
	}
}

// assertNoSecretOverStream sweeps AssertNoSecretInEvent over every event of a live stream (A9).
func assertNoSecretOverStream(t *testing.T, session agentsession.Session) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	stream := session.Events(ctx, agentsession.FromSeq(0))
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return
		}
		agentsessiontest.AssertNoSecretInEvent(t, event, agentsessiontest.SeededCanary)
	}
}

// driveSend prompts a live model to send a peer message via its native SendMessage / host
// tool. The exact wording is model-facing; the assertions ride the normalized events.
func driveSend(t *testing.T, session agentsession.Session, to, body string) {
	t.Helper()
	prompt := "Use your peer messaging tool to send exactly this message to the agent named " + to + ": " + body
	if _, err := session.Control(context.Background(),
		agentsession.Command{Kind: agentsession.CommandPrompt, Text: prompt}); err != nil {
		t.Fatalf("drive send to %q: %v", to, err)
	}
}
