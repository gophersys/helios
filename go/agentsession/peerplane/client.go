package peerplane

import (
	"context"
	"net"
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// DialConfig is the immutable input for a MEMBER process's client over the root's socket.
type DialConfig struct {
	SocketPath  string
	Name        string
	Parent      string
	Harness     string
	JoinTimeout time.Duration
}

// receiptBuffer bounds the queue of delivery receipts waiting to go out on the wire. It is
// generous because a receipt is one msg id and dropping one costs a reconciler bounce.
const receiptBuffer = 64

// Client is a member process's attachment to the root over the unix socket. It implements
// agentsession.PeerPlane identically to *Orchestrator, so a session cannot tell them apart.
type Client struct {
	configuration DialConfig
	conn          net.Conn

	writeMu   sync.Mutex // serializes frame writes onto the conn
	requestMu sync.Mutex // one request/response in flight at a time

	response  chan frame
	inbound   chan agentsession.PeerMessage
	receipts  chan string   // delivery receipts queued OFF the caller; drained by forwardReceipts
	closed    chan struct{} // closed by Close to reap forwardReceipts
	closeOnce sync.Once
}

// Dial opens a member's connection to the root's socket. It is pure of I/O beyond the connect; the
// Join handshake completes the attach.
func Dial(configuration DialConfig, _ Deps) (*Client, error) {
	if configuration.SocketPath == "" {
		return nil, errors.Wrap(errors.KindInvalid, "peerplane: dial",
			agentsession.ConfigError{Field: "SocketPath", Message: "a socket path is required to dial the root"})
	}
	conn, err := net.Dial("unix", configuration.SocketPath)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "peerplane: dial", err)
	}
	client := &Client{
		configuration: configuration,
		conn:          conn,
		response:      make(chan frame, 1),
		inbound:       make(chan agentsession.PeerMessage, 64),
		receipts:      make(chan string, receiptBuffer),
		closed:        make(chan struct{}),
	}
	go client.read()
	go client.forwardReceipts()
	return client, nil
}

// read is the client's single reader goroutine: it routes an inbound deliver frame to the inbound
// queue and every response frame to the pending-request channel. It exits on a dropped connection.
func (c *Client) read() {
	for {
		f, err := readFrame(c.conn)
		if err != nil {
			close(c.inbound)
			return
		}
		if f.Type == frameDeliver && f.Message != nil {
			c.inbound <- *f.Message
			continue
		}
		select {
		case c.response <- f:
		default:
		}
	}
}

// Join registers name under parent over the socket and returns the member's link. It sends the
// join frame and waits for the join-ack, bounded by JoinTimeout — the attach-time tripwire against
// the silent-hold class.
//
//nolint:ireturn // returns the agentsession.PeerLink port (the contract surface).
func (c *Client) Join(_ context.Context, name, parent string) (agentsession.PeerLink, error) {
	joinName, joinParent := c.resolveIdentity(name, parent)
	ack, err := c.request(&frame{Type: frameJoin, Name: joinName, Parent: joinParent})
	if err != nil {
		return nil, err
	}
	if !ack.OK {
		return nil, errors.Wrap(errors.KindConflict, "peerplane: join",
			JoinError{Name: joinName, Parent: joinParent, Reason: ack.Reason})
	}
	return &clientLink{client: c, name: joinName}, nil
}

// Roster requests the roster from the root.
func (c *Client) Roster(_ context.Context, _ string) ([]agentsession.Peer, error) {
	resp, err := c.request(&frame{Type: frameRoster})
	if err != nil {
		return nil, err
	}
	return resp.Peers, nil
}

// forwardReceipts is the client's receipt writer. It exists so Received can be a queue push and
// nothing else: the library calls Received from the PUMP goroutine, which owns Seq, and a
// synchronous socket write there takes writeMu behind any in-flight request — one slow root
// wedges the whole session. The port contract says Received MUST NOT block, and this is what
// makes that true over a socket. It exits on Close.
func (c *Client) forwardReceipts() {
	for {
		select {
		case <-c.closed:
			return
		case msgID := <-c.receipts:
			_ = c.writeFrame(&frame{Type: frameReceived, MsgID: msgID}) //nolint:errcheck // best-effort receipt; the root's reconciler bounces a row that never gets one.
		}
	}
}

// queueReceipt hands one receipt to the writer goroutine WITHOUT blocking the caller. A full
// queue does not stall it either: the receipt is not sent, and the root's reconciler bounces the
// uncorroborated row in band at DeliveryDeadline. That is the plane's OWN loudness path — a
// missing receipt is the exact thing the reconciler exists to observe — not a silent loss.
func (c *Client) queueReceipt(msgID string) {
	select {
	case c.receipts <- msgID:
	default:
	}
}

// Close leaves the tree, reaps the receipt writer, and drops the connection. Idempotent.
func (c *Client) Close(_ context.Context) error {
	c.closeOnce.Do(func() {
		close(c.closed)
		_ = c.writeFrame(&frame{Type: frameLeave}) //nolint:errcheck // best-effort leave; the conn close is the reap.
		_ = c.conn.Close()                         //nolint:errcheck // best-effort reap; the reader goroutine exits on the closed conn.
	})
	return nil
}

// resolveIdentity prefers the caller's name/parent, falling back to the DialConfig identity a
// single-member client was constructed with.
func (c *Client) resolveIdentity(name, parent string) (joinName, joinParent string) {
	if name == "" {
		name = c.configuration.Name
	}
	if parent == "" {
		parent = c.configuration.Parent
	}
	return name, parent
}

// request sends one frame and waits for its response, bounded by JoinTimeout, under the
// one-request-in-flight lock so a concurrent deliver frame never masquerades as the response.
func (c *Client) request(f *frame) (frame, error) {
	c.requestMu.Lock()
	defer c.requestMu.Unlock()
	if err := c.writeFrame(f); err != nil {
		return frame{}, err
	}
	select {
	case resp := <-c.response:
		return resp, nil
	case <-time.After(c.handshakeTimeout()):
		return frame{}, errors.Wrap(errors.KindDeadline, "peerplane: request",
			JoinError{Name: c.configuration.Name, Parent: c.configuration.Parent, Reason: "handshake"})
	}
}

// writeFrame serializes a frame write onto the connection.
func (c *Client) writeFrame(f *frame) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	return writeFrame(c.conn, f)
}

// handshakeTimeout is the DialConfig bound (default 10s).
func (c *Client) handshakeTimeout() time.Duration {
	if c.configuration.JoinTimeout > 0 {
		return c.configuration.JoinTimeout
	}
	return 10 * time.Second
}

// clientLink is a socket member's PeerLink: Inbound is fed by the reader goroutine, Send/Received
// are frames to the root.
type clientLink struct {
	client *Client
	name   string
}

// Inbound returns the member's inbound queue (fed by deliver frames).
func (l *clientLink) Inbound() <-chan agentsession.PeerMessage { return l.client.inbound }

// Send routes a message through the root and returns the minted MsgID, or the root's typed error.
//
//nolint:gocritic // PeerMessage is the contract's copyable value record.
func (l *clientLink) Send(_ context.Context, message agentsession.PeerMessage) (string, error) {
	message.From = l.name
	ack, err := l.client.request(&frame{Type: frameSend, Name: l.name, Message: &message})
	if err != nil {
		return "", err
	}
	if ack.ErrMsg != "" {
		return "", errors.Wrap(errors.Kind(ack.ErrKind), "peerplane: send",
			agentsession.UnreachableError{Name: message.To, Reason: ack.ErrMsg})
	}
	return ack.MsgID, nil
}

// Received corroborates delivery to the root. It QUEUES the receipt and returns — it does not
// write the socket — because the port contract forbids it to block and the caller is the pump
// goroutine (agentsession/peer.go: "It MUST NOT block ... the plane buffers"). This is the plane
// buffering.
func (l *clientLink) Received(msgID string) { l.client.queueReceipt(msgID) }

// Close leaves the tree by closing the client connection. Idempotent.
func (l *clientLink) Close(ctx context.Context) error { return l.client.Close(ctx) }

// compile-time assertions: *Client is a PeerPlane and *clientLink a PeerLink.
var (
	_ agentsession.PeerPlane = (*Client)(nil)
	_ agentsession.PeerLink  = (*clientLink)(nil)
)
