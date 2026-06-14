// Package natscontrol is the REAL stateless.ControlPublisher adapter over core NATS: it publishes a
// typed agentruntime.ControlMessage to agent.<id>.control (the SOFT control subject the in-pod PID-1
// sidecar subscribes — agentruntime §4.2). It is the gateway's one place github.com/nats-io/nats.go
// is imported for the control path; the events path is the natssse bridge over JetStream.
//
// The control subject is CORE NATS (not JetStream): a control verb is a fire-and-forget soft signal
// the live sidecar acts on, not a durable replay (the agentruntime contract: control is the soft
// signal, the docker/k8s API is the hard lifecycle). The subject grammar's home is agentruntime
// (ControlSubject); this adapter cites it, never re-spells it (one concept, one home, 10 §9).
package natscontrol

import (
	"context"
	"encoding/json"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/stateless"
)

// flushTimeout bounds the post-publish flush when the caller's context carries no deadline (nats'
// FlushWithContext requires a deadline). A control publish is a fast core-NATS round trip; this is
// the upper bound before a dead server fails the request.
const flushTimeout = 5 * time.Second

// Adapter is the concrete stateless.ControlPublisher over a dialed *nats.Conn. Safe for concurrent
// use (the underlying *nats.Conn is). Construct via New; it is the value the composition root wires
// into stateless.Deps.Control.
type Adapter struct {
	conn *nats.Conn
}

// New constructs the adapter over a dialed connection. PURE: it dials nothing and reads no env. A
// nil Conn is a construction error (KindInvalid).
func New(conn *nats.Conn) (*Adapter, error) {
	if conn == nil {
		return nil, errors.New(errors.KindInvalid, "natscontrol: a dialed *nats.Conn is required")
	}
	return &Adapter{conn: conn}, nil
}

// PublishControl marshals message to JSON and publishes it to agent.<message.AgentID>.control over
// core NATS, then flushes bounded by ctx so a dead server fails fast. A marshal/publish/flush fault
// is wrapped on the Eden errors seam so the gateway pipeline branches by Kind (→ HTTP status).
func (a *Adapter) PublishControl(ctx context.Context, message agentruntime.ControlMessage) error {
	payload, err := json.Marshal(message)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "natscontrol: marshal control message", err)
	}
	subject := agentruntime.ControlSubject(message.AgentID)
	if err := a.conn.Publish(subject, payload); err != nil {
		return errors.Wrap(errors.KindUnavailable, "natscontrol: publish control", err)
	}
	// nats' FlushWithContext REQUIRES a deadline; if the caller's context has none, bound it so a
	// dead server still fails fast rather than panicking the SDK's deadline check.
	flushCtx := ctx
	if _, hasDeadline := ctx.Deadline(); !hasDeadline {
		var cancel context.CancelFunc
		flushCtx, cancel = context.WithTimeout(ctx, flushTimeout)
		defer cancel()
	}
	if err := a.conn.FlushWithContext(flushCtx); err != nil {
		return errors.Wrap(errors.KindUnavailable, "natscontrol: flush control publish", err)
	}
	return nil
}

// compile-time assertion: *Adapter is a stateless.ControlPublisher.
var _ stateless.ControlPublisher = (*Adapter)(nil)
