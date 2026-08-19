package agentsession_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
)

// The subagent channel is a DISTINCT function from peer messaging (design §8): two payload
// types, two event kinds, two capability bits, and — the load-bearing invariant — a subagent
// NEVER appears in the peer roster and is NEVER addressable across processes. This file pins
// the non-conflation the requirement says must never be violated (break #5 in the non-vacuity
// table: register a subagent on the plane -> a subagent in Roster -> FAIL).

// TestSubagent_MessageCarriesSubagentPayloadNotPeer proves the two payloads are separated by
// the TYPE SYSTEM, not by a runtime discriminator: an EventSubagentMessage carries a
// *SubagentMessage and its *PeerMessage side is nil, so a consumer cannot read subagent
// traffic through the peer payload by accident.
func TestSubagent_MessageCarriesSubagentPayloadNotPeer(t *testing.T) {
	t.Parallel()
	sub := agentsession.SubagentMessage{SubagentID: "s1", ParentTurn: "t1", Index: 0, ToChild: true, Digest: "spawn the linter"}
	script := []agentsession.Event{
		agentsessiontest.MessageStart("assistant"),
		agentsessiontest.SubagentMessageEvent(sub),
		agentsessiontest.MessageEnd(),
	}
	events := drainPeerSession(t, script)

	var found *agentsession.Event
	for i := range events {
		if events[i].Kind == agentsession.EventSubagentMessage {
			found = &events[i]
		}
		if events[i].Kind == agentsession.EventPeerMessage {
			t.Errorf("subagent traffic surfaced as EventPeerMessage — the two channels are conflated")
		}
	}
	if found == nil {
		t.Fatal("no EventSubagentMessage surfaced for the scripted subagent message")
	}
	if found.Subagent == nil {
		t.Fatal("EventSubagentMessage carries no *SubagentMessage payload")
	}
	if found.Subagent.SubagentID != "s1" {
		t.Errorf("SubagentID = %q, want s1", found.Subagent.SubagentID)
	}
	if found.Peer != nil {
		t.Errorf("EventSubagentMessage populated the *PeerMessage side (%+v) — the payloads must not conflate", found.Peer)
	}
}

// TestSubagent_NeverInRoster is the S3 non-conflation invariant: the plane roster lists
// peers WITH parentage, and a subagent id — which is parent-local and has no plane
// registration path at all — never appears. Registering peers must not smuggle a subagent
// into the roster.
func TestSubagent_NeverInRoster(t *testing.T) {
	t.Parallel()
	plane := agentsessiontest.NewPeerPlane()
	ctx := context.Background()

	if _, err := plane.Join(ctx, "impl-a", ""); err != nil {
		t.Fatalf("Join impl-a: %v", err)
	}
	if _, err := plane.Join(ctx, "review-c", ""); err != nil {
		t.Fatalf("Join review-c: %v", err)
	}

	roster, err := plane.Roster(ctx, "impl-a")
	if err != nil {
		t.Fatalf("Roster: %v", err)
	}
	for _, peer := range roster {
		if peer.Name == "s1" || peer.Name == "impl-a-s1" {
			t.Errorf("a subagent id %q appeared in the peer Roster — the channels are conflated", peer.Name)
		}
	}
	// The peers themselves ARE present (the roster is not vacuously empty).
	if !rosterHas(roster, "impl-a") || !rosterHas(roster, "review-c") {
		t.Fatalf("roster is missing a registered peer: %+v", roster)
	}
}

// TestSubagent_NotPeerAddressable is S5: a peer Send addressed to a subagent id resolves to
// no roster entry and returns a typed UnreachableError — a subagent is never addressable
// across the peer plane.
func TestSubagent_NotPeerAddressable(t *testing.T) {
	t.Parallel()
	plane := agentsessiontest.NewPeerPlane()
	ctx := context.Background()

	link, err := plane.Join(ctx, "impl-a", "")
	if err != nil {
		t.Fatalf("Join: %v", err)
	}

	// Compile-level non-conflation: the ONLY payload Send accepts is a PeerMessage. There is
	// no overload taking a SubagentMessage — the plane API physically cannot accept one.
	var _ func(context.Context, agentsession.PeerMessage) (string, error) = link.Send

	_, err = link.Send(ctx, agentsession.PeerMessage{From: "impl-a", To: "s1", Body: "hello subagent"})
	if !errors.IsType[agentsession.UnreachableError](err) {
		t.Fatalf("a peer Send to a subagent id must be UnreachableError, got %v (%T)", err, err)
	}
	assertKindNotFound(t, err)
}

// rosterHas reports whether the roster contains a peer named name.
func rosterHas(roster []agentsession.Peer, name string) bool {
	for _, peer := range roster {
		if peer.Name == name {
			return true
		}
	}
	return false
}

// assertKindNotFound asserts err classifies to errors.KindNotFound (the loudness Kind an
// UnreachableError carries).
func assertKindNotFound(t *testing.T, err error) {
	t.Helper()
	if got := errors.KindOf(err); got != errors.KindNotFound {
		t.Errorf("KindOf = %v, want not-found (err: %v)", got, err)
	}
}
