package agentsessiontest

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/errors"
)

// This file adds the peer surface of the canonical fake: the deterministic peer/subagent Event
// builders, an in-memory agentsession.PeerPlane (registry + router, no socket) so every peer
// conformance case runs in the fast unit lane, and RequireLiveCredential — the harness lane's
// FAIL-NOT-SKIP replacement for a token-or-skip helper.

// defaultInboxDepth bounds the per-peer inbound queue of the in-memory plane (peerplane's
// InboxDepth default). Overflow is a LOUD error to the sender, never a silent drop.
const defaultInboxDepth = 64

// PeerMessageEvent builds an inbound EventPeerMessage carrying message (an inter-session
// message that ARRIVED for this session).
//
//nolint:gocritic // PeerMessage is the contract's copyable value record; the builder takes it by value.
func PeerMessageEvent(message agentsession.PeerMessage) agentsession.Event {
	clone := message
	return agentsession.Event{Kind: agentsession.EventPeerMessage, Time: fixedEmitTime, Peer: &clone}
}

// PeerSentEvent builds an EventPeerSent carrying message (this session's observed send +
// receipt). Accepted==false marks accepted-for-routing-but-never-delivered (the root bounce).
//
//nolint:gocritic // PeerMessage is the contract's copyable value record; the builder takes it by value.
func PeerSentEvent(message agentsession.PeerMessage) agentsession.Event {
	clone := message
	return agentsession.Event{Kind: agentsession.EventPeerSent, Time: fixedEmitTime, Peer: &clone}
}

// SubagentMessageEvent builds an EventSubagentMessage carrying message (a parent<->child
// message inside one harness process — a DISTINCT function from peer messaging).
//
//nolint:gocritic // SubagentMessage is the contract's copyable value record; the builder takes it by value.
func SubagentMessageEvent(message agentsession.SubagentMessage) agentsession.Event {
	clone := message
	return agentsession.Event{Kind: agentsession.EventSubagentMessage, Time: fixedEmitTime, Subagent: &clone}
}

// RequireLiveCredential returns the named environment variable's value, FAILING the test (never
// a t.Skip) when it is unset. It is the harness lane's replacement for a token-or-skip helper:
// the lane has NO skip path in existence, because a test that cannot run is a failure, not a
// pass (ADR-0020 FAIL-NOT-SKIP).
func RequireLiveCredential(t *testing.T, name string) string {
	t.Helper()
	value := os.Getenv(name)
	if value == "" {
		t.Fatalf("live credential %q is unset: the harness lane requires it (FAIL-NOT-SKIP, never a t.Skip)", name)
	}
	return value
}

// PeerPlane is an in-memory agentsession.PeerPlane: a registry + full-mesh router with no
// socket and no reconciler, so every peer conformance case runs in the fast unit lane. It
// enforces the same body bound and envelope-terminator rejection the real plane does.
type PeerPlane struct {
	mu      sync.Mutex
	members map[string]*peerMember
	counter int
}

// peerMember is one registered session: its name, its tree parent, and its buffered inbound
// queue (the messages the plane routed to it over the bus).
type peerMember struct {
	name    string
	parent  string
	inbound chan agentsession.PeerMessage
}

// NewPeerPlane returns an empty in-memory plane. It starts no goroutine, so a plane a test
// wires into Deps and never explicitly closes leaves nothing to leak.
func NewPeerPlane() *PeerPlane {
	return &PeerPlane{members: make(map[string]*peerMember)}
}

// Join registers name under parent and returns its link. A duplicate name is a conflict (the
// real plane's JoinError{duplicate} analog); this fake keeps the surface minimal.
//
//nolint:ireturn // returns the agentsession.PeerLink port (the contract surface).
func (p *PeerPlane) Join(_ context.Context, name, parent string) (agentsession.PeerLink, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if _, exists := p.members[name]; exists {
		return nil, errors.Wrap(errors.KindConflict, "agentsessiontest: peer join",
			errDuplicatePeer)
	}
	p.members[name] = &peerMember{
		name:    name,
		parent:  parent,
		inbound: make(chan agentsession.PeerMessage, defaultInboxDepth),
	}
	return &peerLink{plane: p, name: name}, nil
}

// Roster lists every registered peer WITH parentage — full mesh, so it lists all members (the
// tree is registry and audit, not a partition). A subagent id never appears: a subagent has no
// registration path here at all.
func (p *PeerPlane) Roster(_ context.Context, _ string) ([]agentsession.Peer, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	roster := make([]agentsession.Peer, 0, len(p.members))
	for _, member := range p.members {
		roster = append(roster, agentsession.Peer{
			Name:       member.name,
			Parent:     member.parent,
			Harness:    "fake",
			Live:       true,
			Generation: 1,
		})
	}
	return roster, nil
}

// route validates the body, mints the MsgID, and delivers the message to its addressee's inbound
// queue. An unknown To is a typed UnreachableError; a full inbox is KindResourceExhausted TO THE
// SENDER — never a silent drop.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record.
func (p *PeerPlane) route(message agentsession.PeerMessage) (string, error) {
	if len(message.Body) > agentsession.MaxPeerBodyBytes {
		return "", errors.Wrap(errors.KindInvalid, "agentsessiontest: peer send", errPeerBodyTooLarge)
	}
	if _, err := controlframe.EncodePeer(message.From, message.To, "", message.ReplyTo, message.Body, message.Verified); err != nil {
		return "", errors.Wrap(errors.KindInvalid, "agentsessiontest: peer send", err)
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	target, ok := p.members[message.To]
	if !ok {
		return "", errors.Wrap(errors.KindNotFound, "agentsessiontest: peer send",
			agentsession.UnreachableError{Name: message.To, Reason: "not-in-roster"})
	}
	p.counter++
	message.MsgID = "msg-" + strconv.Itoa(p.counter)
	select {
	case target.inbound <- message:
		return message.MsgID, nil
	default:
		return "", errors.Wrap(errors.KindExhausted, "agentsessiontest: peer send",
			agentsession.UnreachableError{Name: message.To, Reason: "inbox-full"})
	}
}

// remove detaches a member from the registry (idempotent). It leaves the inbound channel for GC;
// no goroutine owns it.
func (p *PeerPlane) remove(name string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	delete(p.members, name)
}

// peerLink is one session's attachment to the in-memory plane.
type peerLink struct {
	plane *PeerPlane
	name  string
}

// Inbound returns the buffered queue of messages the plane routed to this session.
func (l *peerLink) Inbound() <-chan agentsession.PeerMessage {
	l.plane.mu.Lock()
	defer l.plane.mu.Unlock()
	if member, ok := l.plane.members[l.name]; ok {
		return member.inbound
	}
	// A closed link yields a nil channel (a receive blocks forever), which the deliver
	// goroutine only reaches after Close has already signaled it to stop.
	return nil
}

// Send routes message.To and returns the minted MsgID (accepted for routing, not delivered).
//
//nolint:gocritic // PeerMessage is the contract's copyable value record.
func (l *peerLink) Send(_ context.Context, message agentsession.PeerMessage) (string, error) {
	return l.plane.route(message)
}

// Received is a no-op on the in-memory plane: it has no reconciler, so a receipt corroborates
// nothing to bounce against. It never blocks.
func (l *peerLink) Received(_ string) {}

// Close leaves the tree, removing the name from every roster. Idempotent.
func (l *peerLink) Close(_ context.Context) error {
	l.plane.remove(l.name)
	return nil
}

// errDuplicatePeer / errPeerBodyTooLarge are the fake's sentinel causes (the black-box error
// Kinds are what a test branches on; these carry the human message).
var (
	errDuplicatePeer    = errors.New(errors.KindConflict, "agentsessiontest: duplicate peer name")
	errPeerBodyTooLarge = errors.New(errors.KindInvalid, "agentsessiontest: peer body exceeds MaxPeerBodyBytes")
)

// compile-time assertions: the in-memory plane and its link satisfy the agentsession ports.
var (
	_ agentsession.PeerPlane = (*PeerPlane)(nil)
	_ agentsession.PeerLink  = (*peerLink)(nil)
)
