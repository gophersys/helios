package peerplane

import (
	"context"

	"github.com/gophersys/libs/go/agentsession"
)

// inProcLink is a member's attachment to the root WITHOUT a socket hop: a single-process
// deployment joins in-process and routes A -> root -> B through the registry directly.
type inProcLink struct {
	orchestrator *Orchestrator
	name         string
	node         *node
}

// Inbound returns the buffered queue of messages the plane routed to this session.
func (l *inProcLink) Inbound() <-chan agentsession.PeerMessage { return l.node.inbound }

// Send routes message.To through the root and returns the minted MsgID (accepted for routing, not
// delivered).
//
//nolint:gocritic // PeerMessage is the contract's copyable value record.
func (l *inProcLink) Send(_ context.Context, message agentsession.PeerMessage) (string, error) {
	return l.orchestrator.route(message)
}

// Received corroborates delivery to the root's reconciler. It never blocks.
func (l *inProcLink) Received(msgID string) { l.orchestrator.received(msgID) }

// Close leaves the tree, reparenting children and bouncing in-flight envelopes. Idempotent.
func (l *inProcLink) Close(_ context.Context) error {
	l.orchestrator.leave(l.name)
	return nil
}

// compile-time assertion: *inProcLink is an agentsession.PeerLink.
var _ agentsession.PeerLink = (*inProcLink)(nil)
