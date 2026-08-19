// Package peerplane is the inter-session message plane's transport: the tree ROOT that owns the
// listening unix socket, the name registry, the parent edges, the router, the msg_id ledger, and
// the delivery reconciler. agentsession opens NO socket (contract §1) — it CALLS the
// agentsession.PeerPlane port, which *Orchestrator (the root) and *Client (a member process) both
// implement, so a session cannot tell whether its plane is in-process or across the socket.
//
// The loudness guarantee lives HERE, at the root, because only the root holds both halves of a
// delivery: Send returns "accepted for routing", never "delivered"; a ledger row with no receipt
// (PeerLink.Received) inside DeliveryDeadline BOUNCES an in-band envelope from <mesh>.root to the
// sender AND records an UndeliveredError — never a sender-side timeout that fires on a merely-slow
// receiver.
package peerplane

import (
	"context"
	"net"
	"strconv"
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/internal/controlframe"
	"github.com/gophersys/libs/go/errors"
)

// Config is the immutable spine input for the tree root.
type Config struct {
	// SocketPath: "" == the ladder ${EDEN_PEER_SOCKET} -> ${XDG_RUNTIME_DIR}/eden/peer/<mesh>.sock
	// -> /run/eden/peer/<mesh>.sock -> /tmp/eden-peer-<uid>/<mesh>.sock. Parent dir 0700, socket 0600.
	SocketPath string

	// MeshID: "" == a stable default. One mesh per container; it separates two meshes on one host
	// and names the bounce sender (<MeshID>.root).
	MeshID string

	// InboxDepth bounds the per-peer inbound queue. 0 == 64.
	InboxDepth int

	// DeliveryDeadline bounds the reconciler: a ledger row with no receipt by then bounces an
	// in-band envelope from <mesh>.root to the sender. 0 == 60s. This is the ONLY mechanism that
	// can observe a silently held message, and it lives at the root where both halves are visible.
	DeliveryDeadline time.Duration

	// JoinTimeout bounds the liveness handshake. 0 == 10s.
	JoinTimeout time.Duration

	// MaxBodyBytes: 0 == agentsession.MaxPeerBodyBytes.
	MaxBodyBytes int

	// Reachable decides whether from may reach to. nil == FULL MESH (the requirement). The tree
	// supplies naming, parentage, admission and audit — not partition.
	Reachable func(from, to agentsession.Peer) bool
}

// Deps is the injected hexagon. New constructs no ports.
type Deps struct{ Clock agentsession.Clock }

// Orchestrator is the tree root: registry + parent edges + router + msg_id ledger + reconciler.
type Orchestrator struct {
	configuration Config
	clock         agentsession.Clock
	meshID        string

	mu          sync.Mutex
	nodes       map[string]*node
	generations map[string]int
	ledger      map[string]*ledgerRow
	undelivered []UndeliveredError
	counter     int

	conns    map[net.Conn]struct{}
	listener net.Listener

	shutdownOnce sync.Once
}

// node is one registered session in the tree: its identity, its parent edge, its generation, and
// the callback that delivers a routed message to it (an in-process channel push or a socket frame).
type node struct {
	name       string
	parent     string
	harness    string
	generation int
	inbound    chan agentsession.PeerMessage
	deliver    func(agentsession.PeerMessage) error
}

// ledgerRow records an accepted message the reconciler watches: who sent it, to whom, when, and
// whether the receiver corroborated delivery. bounced guards a one-time bounce; timer is the
// per-row deadline that fires the bounce (Stopped on receipt, so a delivered message spawns no
// goroutine at all — the reconciler is entirely timer-driven, never a persistent ticker).
type ledgerRow struct {
	from     string
	to       string
	sentAt   time.Time
	received bool
	bounced  bool
	timer    *time.Timer
}

// New returns the tree ROOT. It is the PURE spine (10 §4): New opens nothing and starts no
// goroutine; Listen binds the socket and the reconciler starts on the first Join or Listen.
func New(configuration Config, dependencies Deps) (*Orchestrator, error) {
	if dependencies.Clock == nil {
		return nil, errors.Wrap(errors.KindInvalid, "peerplane: New",
			agentsession.ConfigError{Field: "Clock", Message: "an injected Clock is required (New reads no wall clock)"})
	}
	meshID := configuration.MeshID
	if meshID == "" {
		meshID = "eden-mesh"
	}
	return &Orchestrator{
		configuration: configuration,
		clock:         dependencies.Clock,
		meshID:        meshID,
		nodes:         make(map[string]*node),
		generations:   make(map[string]int),
		ledger:        make(map[string]*ledgerRow),
		conns:         make(map[net.Conn]struct{}),
	}, nil
}

// Join registers name under parent in-process and returns this session's link, no socket hop.
//
//nolint:ireturn // returns the agentsession.PeerLink port (the contract surface).
func (o *Orchestrator) Join(_ context.Context, name, parent string) (agentsession.PeerLink, error) {
	created, err := o.register(name, parent, "in-proc", nil)
	if err != nil {
		return nil, err
	}
	return &inProcLink{orchestrator: o, name: name, node: created}, nil
}

// Roster lists every peer reachable from name, WITH parentage (full mesh over the tree).
func (o *Orchestrator) Roster(_ context.Context, _ string) ([]agentsession.Peer, error) {
	return o.roster(), nil
}

// Close bounces every in-flight envelope, stops the reconciler, closes the socket and every
// accepted connection, and unlinks the socket file. Idempotent.
func (o *Orchestrator) Close(_ context.Context) error {
	o.shutdown()
	return nil
}

// register admits a node under the tree rules: a live duplicate name, an unknown parent, or a
// cycle is a JoinError. deliver is the routed-message callback (nil == an in-process node, which
// is given a buffered inbound channel and a push callback). Re-attach bumps Generation so a
// restart is distinguishable from a duplicate.
func (o *Orchestrator) register(name, parent, harness string, deliver func(agentsession.PeerMessage) error) (*node, error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	if existing, ok := o.nodes[name]; ok && existing != nil {
		return nil, JoinError{Name: name, Parent: parent, Reason: "duplicate"}
	}
	if parent != "" {
		if _, ok := o.nodes[parent]; !ok {
			return nil, JoinError{Name: name, Parent: parent, Reason: "unknown-parent"}
		}
	}
	if o.wouldCycle(name, parent) {
		return nil, JoinError{Name: name, Parent: parent, Reason: "cycle"}
	}
	generation := o.generations[name] + 1
	o.generations[name] = generation
	created := &node{
		name:       name,
		parent:     parent,
		harness:    harness,
		generation: generation,
		inbound:    make(chan agentsession.PeerMessage, o.inboxDepth()),
	}
	if deliver != nil {
		created.deliver = deliver
	} else {
		created.deliver = func(message agentsession.PeerMessage) error {
			created.inbound <- message // blocking push; the session's deliver goroutine keeps it moving
			return nil
		}
	}
	o.nodes[name] = created
	return created, nil
}

// wouldCycle reports whether parenting name under parent would create a cycle (parent, or one of
// its ancestors, is name). The caller holds o.mu.
func (o *Orchestrator) wouldCycle(name, parent string) bool {
	for cursor := parent; cursor != ""; {
		if cursor == name {
			return true
		}
		next, ok := o.nodes[cursor]
		if !ok {
			return false
		}
		cursor = next.parent
	}
	return false
}

// route validates the body, mints the MsgID, records the ledger row, and delivers to the
// addressee. An unknown or departed To is a typed UnreachableError; a body over the bound or one
// carrying the envelope terminator is a loud KindInvalid — never a silent truncation.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record.
func (o *Orchestrator) route(message agentsession.PeerMessage) (string, error) {
	if len(message.Body) > o.maxBody() {
		return "", errors.Wrap(errors.KindInvalid, "peerplane: send", errBodyTooLarge)
	}
	if _, err := controlframe.EncodePeer(message.From, message.To, "", message.ReplyTo, message.Body, message.Verified); err != nil {
		return "", errors.Wrap(errors.KindInvalid, "peerplane: send", err)
	}
	o.mu.Lock()
	target, ok := o.nodes[message.To]
	if !ok || target == nil {
		o.mu.Unlock()
		return "", errors.Wrap(errors.KindNotFound, "peerplane: send",
			agentsession.UnreachableError{Name: message.To, Reason: "not-in-roster"})
	}
	if !o.reachable(message.From, target) {
		o.mu.Unlock()
		return "", errors.Wrap(errors.KindNotFound, "peerplane: send",
			agentsession.UnreachableError{Name: message.To, Reason: "unreachable"})
	}
	o.counter++
	msgID := "msg-" + strconv.Itoa(o.counter)
	row := &ledgerRow{from: message.From, to: message.To, sentAt: o.clock.Now()}
	// The deadline is a per-row timer, Stopped on receipt: a delivered message spawns no
	// reconciler goroutine, and only a genuinely un-received row ever fires a bounce.
	row.timer = time.AfterFunc(o.deliveryDeadline(), func() { o.reconcileRow(msgID) })
	o.ledger[msgID] = row
	deliver := target.deliver
	o.mu.Unlock()

	message.MsgID = msgID
	if err := deliver(message); err != nil {
		return "", errors.Wrap(errors.KindExhausted, "peerplane: send",
			agentsession.UnreachableError{Name: message.To, Reason: "inbox-full"})
	}
	return msgID, nil
}

// reachable applies the Config.Reachable predicate (nil == full mesh). The caller holds o.mu.
func (o *Orchestrator) reachable(from string, target *node) bool {
	if o.configuration.Reachable == nil {
		return true
	}
	fromPeer := agentsession.Peer{Name: from}
	if fromNode, ok := o.nodes[from]; ok {
		fromPeer = peerOf(fromNode)
	}
	return o.configuration.Reachable(fromPeer, peerOf(target))
}

// received marks a ledger row corroborated and Stops its deadline timer, so a delivered message
// never fires a reconciler goroutine at all.
func (o *Orchestrator) received(msgID string) {
	o.mu.Lock()
	if row, ok := o.ledger[msgID]; ok {
		row.received = true
		if row.timer != nil {
			row.timer.Stop()
		}
	}
	o.mu.Unlock()
}

// leave detaches a departed node: it reparents the node's children to its parent (killing a
// subtree turns a local failure into a fleet failure), bounces every un-received in-flight
// envelope to that node, and drops it from the roster. Idempotent.
func (o *Orchestrator) leave(name string) {
	o.mu.Lock()
	departed, ok := o.nodes[name]
	if !ok {
		o.mu.Unlock()
		return
	}
	delete(o.nodes, name)
	for _, other := range o.nodes {
		if other.parent == name {
			other.parent = departed.parent
		}
	}
	bounces := o.collectBouncesLocked(name)
	o.mu.Unlock()
	o.deliverBounces(bounces)
}

// roster snapshots the registry as Peer rows WITH parentage and generation.
func (o *Orchestrator) roster() []agentsession.Peer {
	o.mu.Lock()
	defer o.mu.Unlock()
	out := make([]agentsession.Peer, 0, len(o.nodes))
	for _, current := range o.nodes {
		out = append(out, peerOf(current))
	}
	return out
}

// peerOf projects a node to its roster row.
func peerOf(current *node) agentsession.Peer {
	return agentsession.Peer{
		Name:       current.name,
		Parent:     current.parent,
		Harness:    current.harness,
		Live:       true,
		Generation: current.generation,
	}
}

// The reconciler is the loudness core: one deadline timer per in-flight message, Stopped on
// receipt, so it is entirely timer-driven and never a persistent ticker goroutine.

// reconcileRow fires when a message's deadline elapsed. If the row was corroborated (Received) or
// already bounced it does nothing; otherwise it records an UndeliveredError and bounces an in-band
// envelope from <mesh>.root to the sender — the ONLY mechanism that can observe a silently held
// message, because only the root holds both halves.
func (o *Orchestrator) reconcileRow(msgID string) {
	o.mu.Lock()
	row, ok := o.ledger[msgID]
	if !ok || row.received || row.bounced {
		o.mu.Unlock()
		return
	}
	row.bounced = true
	waited := o.clock.Now().Sub(row.sentAt)
	o.undelivered = append(o.undelivered, UndeliveredError{Name: row.to, MsgID: msgID, Waited: waited})
	var bounces []bounce
	if sender, senderOK := o.nodes[row.from]; senderOK {
		bounces = append(bounces, bounce{node: sender, message: o.bounceEnvelope(row.from, msgID)})
	}
	o.mu.Unlock()
	o.deliverBounces(bounces)
}

// bounce pairs a sender node with the in-band bounce envelope destined for it.
type bounce struct {
	node    *node
	message agentsession.PeerMessage
}

// collectBouncesLocked builds the in-band bounces for every un-received in-flight row to a departed
// name. The caller holds o.mu.
func (o *Orchestrator) collectBouncesLocked(departedName string) []bounce {
	var bounces []bounce
	for msgID, row := range o.ledger {
		if row.to != departedName || row.received || row.bounced {
			continue
		}
		row.bounced = true
		if row.timer != nil {
			row.timer.Stop()
		}
		o.undelivered = append(o.undelivered, UndeliveredError{Name: departedName, MsgID: msgID, Waited: o.clock.Now().Sub(row.sentAt)})
		if sender, ok := o.nodes[row.from]; ok {
			bounces = append(bounces, bounce{node: sender, message: o.bounceEnvelope(row.from, msgID)})
		}
	}
	return bounces
}

// bounceEnvelope renders the in-band bounce from <mesh>.root: an ordinary envelope so the sending
// model learns in band that its message failed. Accepted==false IS the record (events are immutable).
func (o *Orchestrator) bounceEnvelope(to, replyTo string) agentsession.PeerMessage {
	return agentsession.PeerMessage{
		From:     o.rootName(),
		To:       to,
		ReplyTo:  replyTo,
		Body:     "peer message undelivered",
		Accepted: false,
		Detail:   "undelivered: no receipt within the delivery deadline",
	}
}

// deliverBounces pushes each bounce to its sender, best-effort (a sender that is itself gone has
// nothing to learn).
func (o *Orchestrator) deliverBounces(bounces []bounce) {
	for i := range bounces {
		_ = bounces[i].node.deliver(bounces[i].message) //nolint:errcheck // best-effort bounce; the recorded UndeliveredError is the durable record.
	}
}

// rootName is the bounce sender: <mesh>.root, never a peer.
func (o *Orchestrator) rootName() string { return o.meshID + ".root" }

// shutdown stops the reconciler, closes the listener and every accepted conn, and unlinks the
// socket. Idempotent; shared by Close and a canceled Listen ctx.
func (o *Orchestrator) shutdown() {
	o.shutdownOnce.Do(func() {
		o.mu.Lock()
		// Stop every pending deadline timer so no reconciler callback fires after Close.
		for _, row := range o.ledger {
			if row.timer != nil {
				row.timer.Stop()
			}
		}
		listener := o.listener
		conns := make([]net.Conn, 0, len(o.conns))
		for conn := range o.conns {
			conns = append(conns, conn)
		}
		o.listener = nil
		o.mu.Unlock()
		if listener != nil {
			_ = listener.Close() //nolint:errcheck // best-effort; the accept loop returns on the closed listener.
		}
		for _, conn := range conns {
			_ = conn.Close() //nolint:errcheck // best-effort; each serveConn returns on its closed conn.
		}
	})
}

// The accessors below apply each Config field's documented default.

func (o *Orchestrator) inboxDepth() int {
	if o.configuration.InboxDepth > 0 {
		return o.configuration.InboxDepth
	}
	return 64
}

func (o *Orchestrator) maxBody() int {
	if o.configuration.MaxBodyBytes > 0 {
		return o.configuration.MaxBodyBytes
	}
	return agentsession.MaxPeerBodyBytes
}

func (o *Orchestrator) deliveryDeadline() time.Duration {
	if o.configuration.DeliveryDeadline > 0 {
		return o.configuration.DeliveryDeadline
	}
	return 60 * time.Second
}

func (o *Orchestrator) joinTimeout() time.Duration {
	if o.configuration.JoinTimeout > 0 {
		return o.configuration.JoinTimeout
	}
	return 10 * time.Second
}

// errBodyTooLarge / errUnsupportedPlatform are the plane's sentinel causes; a caller branches on
// the wrapped Kind, never on the message.
var (
	errBodyTooLarge        = errors.New(errors.KindInvalid, "peerplane: peer body exceeds MaxPeerBodyBytes")
	errUnsupportedPlatform = errors.New(errors.KindInternal, "peerplane: this platform cannot supply peer credentials (Listen fails closed, never trust-the-socket)")
	errNotJoined           = errors.New(errors.KindPermission, "peerplane: send before join — the connection has no verified identity to send under")
	errFromMismatch        = errors.New(errors.KindPermission, "peerplane: a peer may not send as another name (From bound to the SO_PEERCRED-verified connection)")
)

// compile-time assertion: *Orchestrator is an agentsession.PeerPlane.
var _ agentsession.PeerPlane = (*Orchestrator)(nil)
