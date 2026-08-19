package peerplane

import (
	"encoding/binary"
	"encoding/json"
	"io"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// The socket protocol is length-prefixed JSON: a 4-byte big-endian frame length followed by the
// JSON body. It carries the same operations the in-process path calls directly, so a member
// process cannot tell its plane from an in-process one.
const (
	frameJoin       = "join"       // client -> root: register name under parent
	frameJoinAck    = "join-ack"   // root -> client: ok + generation, or a refusal reason
	frameRoster     = "roster"     // client -> root: request the roster
	frameRosterResp = "roster-res" // root -> client: the roster rows
	frameSend       = "send"       // client -> root: route a message
	frameSendAck    = "send-ack"   // root -> client: minted msg id, or a typed error
	frameReceived   = "received"   // client -> root: corroborate delivery (no response)
	frameDeliver    = "deliver"    // root -> client: an inbound message pushed to the member
	frameLeave      = "leave"      // client -> root: leave the tree
)

// maxFrameBytes bounds a single frame so a malformed length never triggers a huge allocation. It
// comfortably exceeds MaxPeerBodyBytes plus the JSON envelope.
const maxFrameBytes = 1 << 20

// frame is the wire union. Exactly the fields a given Type needs are populated; the rest omit.
type frame struct {
	Type       string                    `json:"t"`
	Name       string                    `json:"name,omitempty"`
	Parent     string                    `json:"parent,omitempty"`
	OK         bool                      `json:"ok,omitempty"`
	Generation int                       `json:"gen,omitempty"`
	Reason     string                    `json:"reason,omitempty"`
	MsgID      string                    `json:"msgID,omitempty"`
	ErrKind    uint8                     `json:"errKind,omitempty"`
	ErrMsg     string                    `json:"errMsg,omitempty"`
	Message    *agentsession.PeerMessage `json:"message,omitempty"`
	Peers      []agentsession.Peer       `json:"peers,omitempty"`
}

// writeFrame marshals f and writes it length-prefixed. It is called under a per-conn write mutex
// so concurrent routes never interleave bytes. f is a pointer only to avoid copying the 150-byte
// wire union per write.
func writeFrame(conn io.Writer, f *frame) error {
	payload, err := json.Marshal(f)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "peerplane: marshal frame", err)
	}
	if len(payload) > maxFrameBytes {
		return errors.Wrap(errors.KindInvalid, "peerplane: frame too large", errFrameTooLarge)
	}
	var header [4]byte
	// #nosec G115 -- len(payload) is bounded by maxFrameBytes (1<<20, checked above), far within uint32. Honored by both the standalone gosec sast lane and golangci's gosec.
	binary.BigEndian.PutUint32(header[:], uint32(len(payload)))
	if _, err := conn.Write(header[:]); err != nil {
		return errors.Wrap(errors.KindUnavailable, "peerplane: write frame header", err)
	}
	if _, err := conn.Write(payload); err != nil {
		return errors.Wrap(errors.KindUnavailable, "peerplane: write frame body", err)
	}
	return nil
}

// readFrame reads one length-prefixed frame. A dropped connection surfaces as a wrapped transport
// error; the caller treats any read error as a departure (it inspects err != nil, never the Kind).
func readFrame(conn io.Reader) (frame, error) {
	var header [4]byte
	if _, err := io.ReadFull(conn, header[:]); err != nil {
		return frame{}, errors.Wrap(errors.KindUnavailable, "peerplane: read frame header", err)
	}
	size := binary.BigEndian.Uint32(header[:])
	if size == 0 || size > maxFrameBytes {
		return frame{}, errors.Wrap(errors.KindInvalid, "peerplane: read frame", errFrameTooLarge)
	}
	payload := make([]byte, size)
	if _, err := io.ReadFull(conn, payload); err != nil {
		return frame{}, errors.Wrap(errors.KindUnavailable, "peerplane: read frame body", err)
	}
	var f frame
	if err := json.Unmarshal(payload, &f); err != nil {
		return frame{}, errors.Wrap(errors.KindInvalid, "peerplane: unmarshal frame", err)
	}
	return f, nil
}

// errFrameTooLarge is the sentinel for a frame beyond maxFrameBytes.
var errFrameTooLarge = errors.New(errors.KindInvalid, "peerplane: frame exceeds the maximum size")
