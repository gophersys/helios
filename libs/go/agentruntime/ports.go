package agentruntime

import (
	"context"
	"time"
)

// Bus is the consumer-defined reactive-bus port the sidecar depends on (accept this interface; the
// natsbus adapter is the concrete impl, a fake binds it in tests). It is the SHAPE OF THE NEED, not
// a mirror of NATS: exactly 3 methods (well under the 10 §9 ceiling). The sidecar PUBLISHES events +
// heartbeats and SUBSCRIBES control through it; JetStream durability/sequencing is the adapter's
// concern behind PublishEvent (the consumer asks only for "publish this Seq-stamped event durably").
type Bus interface {
	// PublishEvent durably appends one event envelope to the agent's event subject (JetStream), so a
	// gateway replica replays the Seq-ordered stream later. The envelope carries the Seq the consumer
	// MUST replay by; the adapter sets the JetStream message id to the Seq for exactly-once de-dup.
	PublishEvent(ctx context.Context, envelope EventEnvelope) error

	// PublishHealth publishes one heartbeat to the agent's health subject. Best-effort liveness (a
	// core NATS publish is sufficient; durability is not required for a heartbeat) — the orchestrator
	// Probes the latest, not a replay.
	PublishHealth(ctx context.Context, heartbeat Heartbeat) error

	// SubscribeControl subscribes to the agent's control subject and delivers each decoded
	// ControlMessage to handle until ctx is canceled, then unsubscribes and returns. handle is
	// invoked from the bus's own goroutine; the sidecar serializes the verb onto the session. A
	// decode fault on one message is delivered as a non-nil error to the sidecar's logger, never
	// dropped silently, and never stalls later messages.
	SubscribeControl(ctx context.Context, agentID AgentID, handle func(ControlMessage)) error
}

// Clock is the minimal injected time port (mirrors agentsession.Clock / observability.Clock). It is
// the sidecar's ONLY time source — New never reads the wall clock — so the heartbeat cadence and the
// envelope EmitTime stamps are deterministic under a fake clock in tests.
type Clock interface{ Now() time.Time }

// Observer is the consumer-defined telemetry port the sidecar drives (accept this interface; an
// observability.Provider-backed adapter is the concrete impl, a fake binds it in tests). It is the
// SHAPE OF THE NEED — exactly 4 methods (under the 10 §9 ceiling) — not a mirror of the full
// observability.Provider: the sidecar logs lifecycle lines, flushes at shutdown (the OTel-flush step
// of the state machine), and injects/extracts the W3C trace carrier so OTel context rides EVERY bus
// message (ADR-0022 invariant). Inject/Extract are pure map transforms over OTelContext so they are
// trivially fakeable and the propagation is testable without a real collector.
type Observer interface {
	// Logf records one operator-facing lifecycle line (spawn, verb received, drain, exit). It never
	// blocks the run loop on I/O and never carries a secret value.
	Logf(ctx context.Context, format string, args ...any)

	// Inject writes the active trace context from ctx into a fresh OTelContext carrier to ride a
	// published bus message. A nil/empty result is valid (an un-traced message).
	Inject(ctx context.Context) OTelContext

	// Extract returns a child ctx parented to the trace carried on a consumed bus message, so a
	// control-verb handler runs as one distributed-trace edge under the orchestrator's publish span.
	Extract(ctx context.Context, carrier OTelContext) context.Context

	// Flush drains buffered telemetry to the exporter at shutdown (and at run boundaries). It is the
	// one blocking method; it honors ctx and returns the drain error.
	Flush(ctx context.Context) error
}
