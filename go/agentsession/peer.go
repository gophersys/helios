package agentsession

import (
	"context"

	"github.com/gophersys/libs/go/errors"
)

// MaxPeerBodyBytes bounds a peer message body. A longer body is a LOUD typed error at Send —
// never a silent truncation, so the transcript stays verbatim within the bound and MsgID
// correlation is never broken by a digest.
const MaxPeerBodyBytes = 8 << 10

// PeerMessage is ONE inter-session message — the single home for the shape, cited by the Event
// payload AND by the PeerLink port (one concept, one home). It is a plain, copyable value.
type PeerMessage struct {
	MsgID    string // minted by the plane at Send; the SENDER's receipt id EQUALS the RECEIVER's origin id
	From     string // the sender's Spec.Name
	To       string // the recipient's Spec.Name; "" on an inbound event (it is this session)
	ReplyTo  string // the MsgID this answers; "" == not a reply
	Body     string // UNTRUSTED agent prose, at most MaxPeerBodyBytes, redacted at the normalization boundary
	Verified bool   // the transport kernel-verified the sender (claude verifiedPeerPid; the eden bus SO_PEERCRED)
	Accepted bool   // EventPeerSent only: false == accepted for routing but NEVER delivered (the root reconciler's bounce)
	Detail   string // EventPeerSent, Accepted==false: the redacted reason
}

// SubagentMessage is a message that crossed the parent<->child boundary inside ONE harness
// process. It is a SEPARATE type, not a discriminated PeerMessage: the peer plane physically
// cannot accept one, so the two functions are separated by the compiler rather than by a
// runtime check that documentation would then misdescribe as compile-checked.
type SubagentMessage struct {
	SubagentID string // parent-LOCAL; never a peer address, never in the tree roster
	ParentTurn string
	Index      int
	ToChild    bool   // true == parent -> child; false == child -> parent
	Digest     string // bounded, redacted
}

// Peer is one roster row: who exists, who opened it, which harness serves it, and whether it is
// live. Parent is what makes the TREE observable and therefore assertable; Generation
// distinguishes a re-attached instance from the departed one (a restart is not a duplicate).
type Peer struct {
	Name       string
	Parent     string // "" == a root session (the orchestrator is its parent)
	Harness    string // "claude-code" | "omp"
	Live       bool   // presence IS liveness; a departed peer is absent from the roster
	Generation int    // bumped on re-attach so a restart is distinguishable from a duplicate
}

// PeerPlane is the injected inter-session message plane. agentsession NEVER constructs it and
// NEVER opens a socket — it mirrors Adapter/HarnessConn, this library's established two-level
// seam shape. NO harness identity appears in this port.
type PeerPlane interface {
	// Join registers name under parent ("" == the tree root) and returns this session's link.
	// It completes only after a liveness handshake round trip, so a configuration that would
	// silently HOLD a message fails LOUDLY here rather than invisibly at the first real
	// message. A duplicate name, an unknown parent, a cycle, or a failed handshake is a typed
	// error — never a silent partial join.
	Join(ctx context.Context, name, parent string) (PeerLink, error)

	// Roster lists every peer reachable from name, WITH parentage. Reachability defaults to a
	// full MESH over TREE routing: the tree is registry, authorization and audit, not a
	// partition.
	Roster(ctx context.Context, name string) ([]Peer, error)
}

// PeerLink is one session's attachment to the plane — the exact shape of HarnessConn one level
// up. 4 methods, under the 5-method ceiling.
type PeerLink interface {
	// Inbound carries the messages the PLANE routed to this session OVER THE BUS. A message the
	// harness's own plane delivered natively does NOT appear here — it arrives as
	// EventPeerMessage from the adapter's normalizer. The library drains this on a DEDICATED
	// deliver goroutine, never the pump goroutine (which owns Seq and must never block writing
	// to the harness).
	Inbound() <-chan PeerMessage

	// Send delivers to message.To and returns the minted MsgID. It returns ACCEPTED FOR
	// ROUTING, never "delivered" — delivery is a later, separate fact (Received reaching the
	// root). An unknown, departed or unreachable peer is UnreachableError; a full recipient
	// inbox is errors.KindResourceExhausted TO THE SENDER — never a drop, never silence.
	Send(ctx context.Context, message PeerMessage) (msgID string, err error)

	// Received corroborates that this session actually took delivery. The library calls it from
	// the pump immediately after EventPeerMessage is emitted — the wire the root's reconciler
	// needs to distinguish an acceptance from a delivery. It MUST NOT block and returns no
	// error: the plane buffers.
	Received(msgID string)

	// Close leaves the tree and removes the name from every roster. Idempotent.
	Close(ctx context.Context) error
}

// UnreachableError reports a Send to a name that is not in the roster, has departed, or whose
// harness this plane cannot reach. It is the loudness guarantee, branchable by type
// (errors.AsType), never by a message string. It carries NO body, so it is redaction-safe.
type UnreachableError struct {
	Name   string
	Reason string
}

// Error renders the operator-safe message (a peer name, never a body).
func (e UnreachableError) Error() string {
	if e.Reason != "" {
		return "agentsession: peer unreachable: " + e.Name + " (" + e.Reason + ")"
	}
	return "agentsession: peer unreachable: " + e.Name
}

// Kind classifies UnreachableError as a not-found failure (the loudness Kind).
func (e UnreachableError) Kind() errors.Kind { return errors.KindNotFound }

// compile-time assertion: UnreachableError satisfies error with a stable Kind.
var _ error = UnreachableError{}
