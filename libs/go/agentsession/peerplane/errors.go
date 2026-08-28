package peerplane

import (
	"strconv"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// JoinError reports a REFUSED join: a name or parent that violates the peer field grammar, a
// duplicate name, an unknown parent, a cycle, or a liveness handshake that did not complete. The
// handshake case is the attach-time tripwire against the silent-hold class; the reconciler is the
// steady-state one. It carries only names, so it is redaction-safe.
type JoinError struct {
	Name   string
	Parent string
	Reason string // invalid-name | invalid-parent | duplicate | unknown-parent | cycle | handshake
}

// Error renders the operator-safe message (names only, never a body).
func (e JoinError) Error() string {
	return "peerplane: join refused for " + e.Name + " under parent " + quoteParent(e.Parent) + ": " + e.Reason
}

// Kind classifies a refused join as a conflict (a duplicate/cycle) — the caller retries with a
// corrected registration.
func (e JoinError) Kind() errors.Kind { return errors.KindConflict }

// UndeliveredError is the root's record of an accepted message with no receipt inside
// DeliveryDeadline. It is recorded AND bounced in band to the sender, so the sending model
// learns its message vanished. Events are immutable, so the bounce IS the record — there is no
// mutable Delivered flag anywhere. It carries only a name + msg id, so it is redaction-safe.
type UndeliveredError struct {
	Name   string
	MsgID  string
	Waited time.Duration
}

// Error renders the operator-safe message (a name + msg id, never a body).
func (e UndeliveredError) Error() string {
	return "peerplane: message " + e.MsgID + " to " + e.Name + " undelivered after " + e.Waited.String()
}

// Kind classifies an undelivered message as a deadline failure (the delivery window elapsed
// with no receipt).
func (e UndeliveredError) Kind() errors.Kind { return errors.KindDeadline }

// quoteParent renders a parent name for a message, marking the root explicitly.
func quoteParent(parent string) string {
	if parent == "" {
		return "<root>"
	}
	return strconv.Quote(parent)
}

// compile-time assertions: both typed errors satisfy error with a stable Kind.
var (
	_ error = JoinError{}
	_ error = UndeliveredError{}
)
