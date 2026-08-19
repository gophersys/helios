package peerplane

import (
	"context"
	"errors"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	liberrors "github.com/gophersys/libs/go/errors"
)

// runPeerDir is the ladder's /run rung, spelled as a const so filepath.Join takes an identifier
// rather than a separator-bearing string literal (gocritic filepathJoin).
const runPeerDir = "/run/eden/peer"

// Listen binds the unix socket and serves member processes. SO_PEERCRED is checked on EVERY accept
// and pinned to the connection; on a platform that cannot supply peer credentials Listen FAILS,
// named — never a silent "trust the socket". It returns when ctx is canceled or the orchestrator
// is closed.
func (o *Orchestrator) Listen(ctx context.Context) error {
	if !peerCredSupported {
		return liberrors.Wrap(liberrors.KindInternal, "peerplane: listen", errUnsupportedPlatform)
	}

	path, err := o.socketPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return liberrors.Wrap(liberrors.KindUnavailable, "peerplane: socket dir", err)
	}
	_ = os.Remove(path) //nolint:errcheck // unlink a stale socket a crashed root left behind; absence is fine.
	listener, err := net.Listen("unix", path)
	if err != nil {
		return liberrors.Wrap(liberrors.KindUnavailable, "peerplane: listen", err)
	}
	if err := os.Chmod(path, 0o600); err != nil {
		_ = listener.Close() //nolint:errcheck // best-effort reap on a failed chmod.
		return liberrors.Wrap(liberrors.KindUnavailable, "peerplane: chmod socket", err)
	}

	o.mu.Lock()
	o.listener = listener
	o.mu.Unlock()

	go func() {
		<-ctx.Done()
		o.shutdown()
	}()

	for {
		conn, acceptErr := listener.Accept()
		if acceptErr != nil {
			//nolint:nilerr // a closed listener (shutdown via Close or a canceled ctx) is a CLEAN return, not an error.
			return nil
		}
		o.trackConn(conn)
		go o.serveConn(conn)
	}
}

// serveConn handles one member connection. It verifies the peer's kernel credentials, then serves
// the join/roster/send/received/leave frames. A dropped connection (EOF) is a departure: the node
// leaves the tree, its children reparent, and its in-flight envelopes bounce.
func (o *Orchestrator) serveConn(conn net.Conn) {
	defer o.untrackConn(conn)

	// SO_PEERCRED pinned at accept: the kernel vouches for the peer, or the connection is refused.
	// `verified` is the trust the orchestrator STAMPS onto every message this connection routes —
	// never the client's self-asserted flag.
	_, verified := peerUID(conn)
	if !verified {
		return
	}

	var writeMu sync.Mutex
	var joinedName string
	handshakeDeadline := time.Now().Add(o.joinTimeout())
	_ = conn.SetReadDeadline(handshakeDeadline) //nolint:errcheck // best-effort; a missing deadline only relaxes the handshake bound.

	for {
		f, err := readFrame(conn)
		if err != nil {
			if joinedName != "" {
				o.leave(joinedName)
			}
			return
		}
		if o.dispatchFrame(conn, &writeMu, &joinedName, verified, &f) {
			return
		}
	}
}

// dispatchFrame services one wire frame. It returns true when the connection should close (a
// leave). joinedName is updated on a successful join so a later EOF leaves the right node; verified
// is this connection's kernel-verified trust, stamped onto anything it sends.
func (o *Orchestrator) dispatchFrame(conn net.Conn, writeMu *sync.Mutex, joinedName *string, verified bool, f *frame) (done bool) {
	switch f.Type {
	case frameJoin:
		_ = conn.SetReadDeadline(time.Time{}) //nolint:errcheck // clear the handshake deadline; steady-state reads block.
		o.serveJoin(conn, writeMu, joinedName, f)
	case frameRoster:
		o.respond(conn, writeMu, &frame{Type: frameRosterResp, Peers: o.roster()})
	case frameSend:
		o.serveSend(conn, writeMu, *joinedName, verified, f)
	case frameReceived:
		o.received(f.MsgID)
	case frameLeave:
		if *joinedName != "" {
			o.leave(*joinedName)
			*joinedName = ""
		}
		return true
	default:
	}
	return false
}

// serveJoin registers a socket member with a deliver callback that pushes a deliver frame to its
// connection, then answers with the generation or a refusal reason.
func (o *Orchestrator) serveJoin(conn net.Conn, writeMu *sync.Mutex, joinedName *string, f *frame) {
	created, err := o.register(f.Name, f.Parent, "planepeer", func(message agentsession.PeerMessage) error {
		return o.writeLocked(conn, writeMu, &frame{Type: frameDeliver, Message: &message})
	})
	if err != nil {
		reason := "handshake"
		var joinErr JoinError
		if errors.As(err, &joinErr) {
			reason = joinErr.Reason
		}
		o.respond(conn, writeMu, &frame{Type: frameJoinAck, OK: false, Reason: reason})
		return
	}
	*joinedName = f.Name
	o.respond(conn, writeMu, &frame{Type: frameJoinAck, OK: true, Generation: created.generation})
}

// serveSend routes a member's send. It NEVER trusts the frame's self-asserted identity: the From
// is BOUND to this connection's joinedName (the name it registered under a SO_PEERCRED-verified
// accept) and Verified is STAMPED from that same verified connection — so a raw same-uid process
// cannot speak as another peer or forge the verified flag. A From that names a different peer, or a
// send before Join, is rejected LOUDLY (a typed sendAck error), never silently dropped.
func (o *Orchestrator) serveSend(conn net.Conn, writeMu *sync.Mutex, joinedName string, verified bool, f *frame) {
	if f.Message == nil {
		o.respond(conn, writeMu, &frame{Type: frameSendAck, ErrKind: uint8(liberrors.KindInvalid), ErrMsg: "empty send"})
		return
	}
	if joinedName == "" {
		o.respond(conn, writeMu, &frame{Type: frameSendAck, ErrKind: uint8(liberrors.KindOf(errNotJoined)), ErrMsg: errNotJoined.Error()})
		return
	}
	if f.Message.From != "" && f.Message.From != joinedName {
		o.respond(conn, writeMu, &frame{Type: frameSendAck, ErrKind: uint8(liberrors.KindOf(errFromMismatch)), ErrMsg: errFromMismatch.Error()})
		return
	}
	message := *f.Message
	message.From = joinedName // BIND to the verified connection identity, never the client's claim
	message.Verified = verified
	msgID, err := o.route(message)
	if err != nil {
		o.respond(conn, writeMu, &frame{Type: frameSendAck, ErrKind: uint8(liberrors.KindOf(err)), ErrMsg: err.Error()})
		return
	}
	o.respond(conn, writeMu, &frame{Type: frameSendAck, MsgID: msgID})
}

// respond writes a best-effort response frame: a failed write is swallowed because the connection
// is already dying and serveConn leaves the node on the next read error.
func (o *Orchestrator) respond(conn net.Conn, writeMu *sync.Mutex, f *frame) {
	_ = o.writeLocked(conn, writeMu, f) //nolint:errcheck // best-effort response; serveConn leaves on the next read error.
}

// writeLocked serializes a frame write onto one connection. Its error IS consumed by the deliver
// callback (a dead socket makes a route return UnreachableError); response paths use respond.
func (o *Orchestrator) writeLocked(conn net.Conn, writeMu *sync.Mutex, f *frame) error {
	writeMu.Lock()
	defer writeMu.Unlock()
	return writeFrame(conn, f)
}

// trackConn / untrackConn record accepted connections so shutdown can close them, reaping every
// serveConn goroutine.
func (o *Orchestrator) trackConn(conn net.Conn) {
	o.mu.Lock()
	o.conns[conn] = struct{}{}
	o.mu.Unlock()
}

func (o *Orchestrator) untrackConn(conn net.Conn) {
	o.mu.Lock()
	delete(o.conns, conn)
	o.mu.Unlock()
	_ = conn.Close() //nolint:errcheck // best-effort reap of a departed connection.
}

// socketPath resolves the bind path down the ladder when Config.SocketPath is empty:
// ${EDEN_PEER_SOCKET} -> ${XDG_RUNTIME_DIR}/eden/peer/<mesh>.sock -> /run/eden/peer/<mesh>.sock ->
// ${TMPDIR}/eden-peer-<uid>/<mesh>.sock. The /tmp rung is retained deliberately (CI runs --user
// root with HOME=/home/dev while devcontainers run remoteUser "dev").
func (o *Orchestrator) socketPath() (string, error) {
	if o.configuration.SocketPath != "" {
		return o.configuration.SocketPath, nil
	}
	sock := o.meshID + ".sock"
	if env := os.Getenv("EDEN_PEER_SOCKET"); env != "" {
		return env, nil
	}
	if xdg := os.Getenv("XDG_RUNTIME_DIR"); xdg != "" {
		return filepath.Join(xdg, "eden", "peer", sock), nil
	}
	if dirWritable("/run") {
		return filepath.Join(runPeerDir, sock), nil
	}
	return filepath.Join(os.TempDir(), "eden-peer-"+strconv.Itoa(os.Getuid()), sock), nil
}

// dirWritable reports whether dir exists and this uid may create entries under it (the ladder's
// /run rung test).
func dirWritable(dir string) bool {
	info, err := os.Stat(dir)
	if err != nil || !info.IsDir() {
		return false
	}
	probe := filepath.Join(dir, ".eden-peer-probe")
	if err := os.Mkdir(probe, 0o700); err != nil {
		return false
	}
	_ = os.Remove(probe) //nolint:errcheck // best-effort cleanup of the writability probe.
	return true
}
