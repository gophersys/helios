package agentsession_test

import (
	"context"
	"regexp"
	"testing"
	"time"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a)). These properties drive the
// REAL Pool/Session/pump against the in-memory NewPeerPlane fake — the plane is the
// conformance two-binding partner, NOT a mock of the library under test.

// peerNameGrammar is the addressability grammar §4.2 pins: a Spec.Name is safe as a CLI
// argument, a unix-socket filename, AND a roster entry (a space or '[' would break the
// "name [ref]" form the harness roster uses). The property below asserts the Open-time
// validation is TOTAL over this grammar — accept every match, reject every non-match.
var peerNameGrammar = regexp.MustCompile(`^[a-z][a-z0-9-]{1,61}[a-z0-9]$`)

// TestProperty_PeerDedupeRingEmitsExactlyOnce is the C5 exactly-once core (design §6, break
// #4 in the non-vacuity table). A message can arrive twice — the bus AND a native plane can
// both deliver the same MsgID — so the library carries a bounded per-session ring of 256
// MsgIDs and a second arrival of an id already seen is dropped. This drives the REAL pump:
// the scripted fake emits the SAME EventPeerMessage N>=2 times (the double-delivery shape),
// and the property asserts the live tail carries EXACTLY ONE EventPeerMessage for that id.
//
// Non-vacuity: the paired TestProperty_PeerDedupeRingPassesDistinctIDs proves a DISTINCT id
// is never swallowed, so "emit exactly once" is not satisfied by dropping everything.
func TestProperty_PeerDedupeRingEmitsExactlyOnce(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		msgID := rapid.StringMatching(`[0-9a-f]{8}`).Draw(rt, "msgID")
		copies := rapid.IntRange(2, 8).Draw(rt, "copies") // a duplicate arrives 2..8 times
		body := rapid.StringN(0, 64, 64).Draw(rt, "body")

		inbound := agentsession.PeerMessage{MsgID: msgID, From: "review-c", Body: body, Verified: true}
		script := []agentsession.Event{agentsessiontest.MessageStart("assistant")}
		for range copies {
			script = append(script, agentsessiontest.PeerMessageEvent(inbound))
		}
		script = append(script, agentsessiontest.MessageEnd())

		events := drainPeerSession(t, script)

		var got int
		for i := range events {
			if events[i].Kind == agentsession.EventPeerMessage && events[i].Peer != nil && events[i].Peer.MsgID == msgID {
				got++
			}
		}
		if got != 1 {
			rt.Fatalf("MsgID %q arrived %d times on the wire; the 256-id dedupe ring must emit EXACTLY ONE EventPeerMessage, got %d", msgID, copies, got)
		}
	})
}

// TestProperty_PeerDedupeRingPassesDistinctIDs is the non-vacuity partner: two DISTINCT
// MsgIDs both surface, so the ring drops duplicates WITHOUT dropping legitimate traffic.
func TestProperty_PeerDedupeRingPassesDistinctIDs(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		a := rapid.StringMatching(`[0-9a-f]{8}`).Draw(rt, "a")
		b := rapid.StringMatching(`[0-9a-f]{8}`).Draw(rt, "b")
		if a == b {
			rt.Skip("drew equal ids")
		}
		script := []agentsession.Event{
			agentsessiontest.MessageStart("assistant"),
			agentsessiontest.PeerMessageEvent(agentsession.PeerMessage{MsgID: a, From: "review-c", Body: "one"}),
			agentsessiontest.PeerMessageEvent(agentsession.PeerMessage{MsgID: b, From: "review-c", Body: "two"}),
			agentsessiontest.MessageEnd(),
		}
		events := drainPeerSession(t, script)
		seen := map[string]int{}
		for i := range events {
			if events[i].Kind == agentsession.EventPeerMessage && events[i].Peer != nil {
				seen[events[i].Peer.MsgID]++
			}
		}
		if seen[a] != 1 || seen[b] != 1 {
			rt.Fatalf("distinct ids must each surface once: %q=%d %q=%d", a, seen[a], b, seen[b])
		}
	})
}

// TestProperty_PeerNameGrammarIsTotal asserts the Open-time name validation is TOTAL over
// peerNameGrammar: a session opened with Deps.Peer set accepts EXACTLY the names the grammar
// matches, and a non-match is a ConfigError at Open (never a mangled argv, never a silent
// non-membership). It drives the REAL Pool.Open validation, so a validator that let an
// invalid slug through — or rejected a legal one — fails here.
func TestProperty_PeerNameGrammarIsTotal(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		// Draw across the boundary: mostly legal-ish slugs plus adversarial characters.
		name := rapid.StringMatching(`[a-zA-Z0-9_\- \[]{0,66}`).Draw(rt, "name")
		wantValid := peerNameGrammar.MatchString(name)

		err := openPeerNameValidate(t, name)
		if wantValid && err != nil {
			rt.Fatalf("name %q matches the grammar but Open rejected it: %v", name, err)
		}
		if !wantValid {
			if !errors.IsType[agentsession.ConfigError](err) {
				rt.Fatalf("name %q violates the grammar; Open must return a ConfigError, got %v (%T)", name, err, err)
			}
		}
	})
}

// drainPeerSession opens a peer-enabled session (Deps.Peer = NewPeerPlane, Spec.Name set),
// prompts once, and drains the live tail to terminal.
func drainPeerSession(t *testing.T, script []agentsession.Event) []agentsession.Event {
	t.Helper()
	session := openPeerSession(t, "impl-a", "", script)
	if _, err := session.Control(context.Background(),
		agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	stream := session.Events(context.Background(), agentsession.FromSeq(0))
	var out []agentsession.Event
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			return out
		}
		out = append(out, event)
		if event.IsTerminal() {
			return out
		}
	}
}

// openPeerSession builds a REAL Pool over the scripted fake with the in-memory peer plane
// injected and the caller-assigned Spec.Name/Parent, opens the session, and reaps it on
// Cleanup. It is the peer-enabled sibling of property_test.go:openScripted.
//
//nolint:ireturn // returns the agentsession.Session port (the contract surface).
func openPeerSession(t *testing.T, name, parent string, script []agentsession.Event) agentsession.Session {
	t.Helper()
	pool := newPeerPool(t, agentsessiontest.New(script...))
	session, err := pool.Open(context.Background(), peerSpec(name, parent))
	if err != nil {
		t.Fatalf("Open(name=%q): %v", name, err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort reap.
	return session
}

// openPeerNameValidate opens a peer-enabled session with the given name and returns the Open
// error (nil on accept). It closes any session it opens.
func openPeerNameValidate(t *testing.T, name string) error {
	t.Helper()
	pool := newPeerPool(t, agentsessiontest.New(agentsessiontest.MessageEnd()))
	session, err := pool.Open(context.Background(), peerSpec(name, ""))
	if err == nil {
		t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort reap.
	}
	return err
}

// newPeerPool builds a Pool whose Deps carry an in-memory peer plane.
func newPeerPool(t *testing.T, adapter *agentsessiontest.Adapter) *agentsession.Pool {
	t.Helper()
	key := agentsession.RouteKey{Role: "assistant"}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			key: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{peerCredentialRef: "peer-canary"}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      peerClock{},
			Peer:       agentsessiontest.NewPeerPlane(),
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}

// peerSpec is the session spec with a caller-assigned peer Name/Parent.
func peerSpec(name, parent string) agentsession.Spec {
	return agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Name:       name,
		Parent:     parent,
		Credential: secrets.Ref(peerCredentialRef),
	}
}

const peerCredentialRef = "vault://eden/anthropic#peer" // #nosec G101 -- a loggable secrets.Reference, not a secret value

type peerClock struct{}

func (peerClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }
