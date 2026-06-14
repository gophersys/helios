// Package natsbus is the REAL agentruntime.Bus adapter over NATS/JetStream — the ONLY place
// github.com/nats-io/nats.go is imported (05 §1 adapter boundary). It realizes the three-subject
// reactive protocol on a real nats-server:
//
//   - PublishEvent  → a JetStream publish to agent.<id>.events with the message id set to the event
//     Seq (exactly-once de-dup) on a durable, replay-by-sequence stream — the gateway (B5) replays
//     the ordered stream from any Seq.
//   - PublishHealth → a core NATS publish to agent.<id>.health (best-effort liveness; no durability).
//   - SubscribeControl → a core NATS subscription to agent.<id>.control decoding each ControlMessage.
//
// JSON is the wire codec (the message protocol is small, evolvable, and human-debuggable with the
// `nats` CLI; the agentsession.Event it carries marshals cleanly). New is PURE over an already-dialed
// *nats.Conn + JetStreamContext (the composition root dials; the adapter never reads env), so the
// connection lifecycle is the caller's — the sidecar owns its conn and reaps it on shutdown.
//
// Module boundary: natsbus is a SUB-package of agentruntime (same module) so the contract types
// (EventEnvelope/Heartbeat/ControlMessage) are cited, never redefined (one concept, one home).
package natsbus

import (
	"context"
	"encoding/json"
	"strconv"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/errors"
)

// StreamName is the JetStream stream that captures every agent's event subject (agent.*.events). One
// stream, subject-filtered per agent, so a gateway consumer binds a durable per-agent.
const StreamName = "EDEN_AGENT_EVENTS"

// eventSubjectWildcard is the stream's captured subject set (every agent's events).
const eventSubjectWildcard = "agent.*.events"

// Config is the adapter's immutable input. It names the JetStream stream (defaulted) and whether the
// adapter should ensure the stream exists at construction. It reads NO env. (Idiomatic Go type name;
// HNS-1 rule 11 exempt.)
type Config struct {
	// Stream is the JetStream stream name; empty == StreamName.
	Stream string

	// EnsureStream, when true, creates-or-updates the events stream at New (idempotent). The sidecar
	// sets this so a fresh nats-server is usable without an out-of-band provisioning step; a
	// deployment that provisions the stream out-of-band (ADR-0022 #2 supporting-stack) leaves it false.
	EnsureStream bool
}

// Deps injects the already-dialed NATS handles (accept the concrete *nats.Conn / JetStreamContext —
// they are the vendor SDK's own types, used only inside this adapter). New performs at most one
// synchronous AddStream when EnsureStream is set; it dials nothing. (Idiomatic Go type name; HNS-1
// rule 11 exempt.)
type Deps struct {
	Conn      *nats.Conn
	JetStream nats.JetStreamContext
}

// Adapter is the concrete agentruntime.Bus over NATS/JetStream. Safe for concurrent use (the
// underlying *nats.Conn is). Construct via New; it is the value the composition root wires into
// agentruntime.Deps.Bus.
type Adapter struct {
	conn      *nats.Conn
	jetStream nats.JetStreamContext
	stream    string
}

// New constructs the adapter over dialed handles. PURE except an optional idempotent AddStream when
// Config.EnsureStream is set (the one sanctioned provisioning call). A nil Conn/JetStream is a
// construction error (KindInvalid).
func New(configuration Config, dependencies Deps) (*Adapter, error) {
	if dependencies.Conn == nil {
		return nil, errors.New(errors.KindInvalid, "natsbus: Deps.Conn is required")
	}
	if dependencies.JetStream == nil {
		return nil, errors.New(errors.KindInvalid, "natsbus: Deps.JetStream is required")
	}
	stream := configuration.Stream
	if stream == "" {
		stream = StreamName
	}
	adapter := &Adapter{conn: dependencies.Conn, jetStream: dependencies.JetStream, stream: stream}
	if configuration.EnsureStream {
		if err := adapter.ensureStream(); err != nil {
			return nil, err
		}
	}
	return adapter, nil
}

// ensureStream creates-or-updates the durable events stream capturing agent.*.events. Idempotent: an
// already-existing stream with the same subject set is a no-op (AddStream returns the existing one or
// a name-in-use error the adapter tolerates).
func (a *Adapter) ensureStream() error {
	_, err := a.jetStream.AddStream(&nats.StreamConfig{
		Name:      a.stream,
		Subjects:  []string{eventSubjectWildcard},
		Storage:   nats.FileStorage,
		Retention: nats.LimitsPolicy,
		Discard:   nats.DiscardOld,
	})
	if err != nil && !errors.Is(err, nats.ErrStreamNameAlreadyInUse) {
		// A re-create with the same subjects on an existing stream surfaces as name-in-use; tolerate
		// it (idempotent provisioning). Any other error is a real provisioning fault.
		if _, infoErr := a.jetStream.StreamInfo(a.stream); infoErr != nil {
			return errors.Wrap(errors.KindUnavailable, "natsbus: ensure events stream", err)
		}
	}
	return nil
}

// PublishEvent durably appends the envelope to agent.<id>.events with the JetStream message id set to
// the event Seq (exactly-once de-dup + the replay key). A marshal/publish error is wrapped on the
// Eden errors seam so the sidecar branches by Kind.
//
//nolint:gocritic // contract: EventEnvelope is the frozen, copyable message value (the protocol pattern); the Bus port takes it by value.
func (a *Adapter) PublishEvent(ctx context.Context, envelope agentruntime.EventEnvelope) error {
	payload, err := json.Marshal(envelope)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "natsbus: marshal event envelope", err)
	}
	subject := agentruntime.EventsSubject(envelope.AgentID)
	_, err = a.jetStream.Publish(
		subject, payload,
		nats.MsgId(strconv.FormatUint(envelope.Seq, 10)),
		nats.Context(ctx),
	)
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "natsbus: jetstream publish event", err)
	}
	return nil
}

// PublishHealth publishes the heartbeat to agent.<id>.health (core NATS, best-effort liveness). A
// marshal/publish error is wrapped; a flush bounds delivery to the ctx so a dead server fails fast.
func (a *Adapter) PublishHealth(ctx context.Context, heartbeat agentruntime.Heartbeat) error {
	payload, err := json.Marshal(heartbeat)
	if err != nil {
		return errors.Wrap(errors.KindInternal, "natsbus: marshal heartbeat", err)
	}
	subject := agentruntime.HealthSubject(heartbeat.AgentID)
	if err := a.conn.Publish(subject, payload); err != nil {
		return errors.Wrap(errors.KindUnavailable, "natsbus: publish heartbeat", err)
	}
	if err := a.conn.FlushWithContext(ctx); err != nil {
		return errors.Wrap(errors.KindUnavailable, "natsbus: flush heartbeat", err)
	}
	return nil
}

// SubscribeControl subscribes to agent.<id>.control and delivers each decoded ControlMessage to
// handle until ctx is canceled, then unsubscribes and returns. A decode fault on one message is NOT
// delivered to handle (it cannot be decoded) but is logged via the error channel pattern: the
// adapter skips the malformed message and continues, never stalling later control. The blocking wait
// on ctx.Done keeps the subscription alive for the agent's whole life.
func (a *Adapter) SubscribeControl(ctx context.Context, agentID agentruntime.AgentID, handle func(agentruntime.ControlMessage)) error {
	subject := agentruntime.ControlSubject(agentID)
	subscription, err := a.conn.Subscribe(subject, func(message *nats.Msg) {
		var control agentruntime.ControlMessage
		if decodeErr := json.Unmarshal(message.Data, &control); decodeErr != nil {
			return // a malformed control frame is skipped, never panics the delivery goroutine
		}
		handle(control)
	})
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "natsbus: subscribe control", err)
	}
	<-ctx.Done()
	if drainErr := subscription.Unsubscribe(); drainErr != nil {
		return errors.Wrap(errors.KindUnavailable, "natsbus: unsubscribe control", drainErr)
	}
	return nil
}

// compile-time assertion: *Adapter is an agentruntime.Bus.
var _ agentruntime.Bus = (*Adapter)(nil)
