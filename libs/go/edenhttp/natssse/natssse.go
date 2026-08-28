// Package natssse is the REAL JetStream→SSE bridge — the stateless half of the B5 gateway
// (ADR-0022 #3). It is the ONLY place in edenhttp that imports github.com/nats-io/nats.go (the
// 05 §1 adapter boundary): it opens an ephemeral JetStream consumer on a per-agent events subject
// from a caller-supplied start sequence, decodes each agentruntime.EventEnvelope (transported
// verbatim — the taxonomy has one home, agentsession), and frames it onto an edenhttp.SSEStream
// with the SSE id set to the event Seq, so a browser resumes gap-free by echoing Last-Event-ID.
//
// STATELESS by construction: the bridge holds no per-session state of its own. JetStream durable
// replay (the agentruntime.natsbus MsgId==Seq invariant) is the source of truth, so ANY gateway
// replica serves ANY session — a reconnect from Last-Event-ID N opens a fresh consumer starting at
// N+1 and replays exactly the missing events. The bridge reaps its consumer + subscription when the
// request context is canceled (client disconnect) or the stream reaches the agent's terminal event,
// so no NATS subscription and no goroutine outlives the request (goleak-clean).
//
// Module boundary: natssse is a SUB-package of edenhttp (same module) so it cites edenhttp.SSEStream
// and agentruntime.EventEnvelope, never redefines them (one concept, one home).
package natssse

import (
	"context"
	"encoding/json"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// fetchTimeout bounds a single JetStream fetch so the pump loop wakes periodically to emit a
// keepalive heartbeat and to observe a canceled request context, rather than blocking forever on a
// quiet stream. It is the bridge's liveness tick, independent of the SSE heartbeat cadence.
const fetchTimeout = 1 * time.Second

// Config is the bridge's immutable input. It names the JetStream stream the per-agent events subject
// belongs to (defaulted to the agentruntime stream) and the SSE heartbeat cadence. It reads NO env.
// (Idiomatic Go type name; HNS-1 rule 11 exempt.)
type Config struct {
	// Stream is the JetStream stream capturing agent.*.events; empty == agentruntime.EventsStreamName.
	Stream string
	// HeartbeatInterval is the SSE keepalive cadence; 0 == edenhttp.DefaultHeartbeatInterval.
	HeartbeatInterval time.Duration
}

// Deps injects the already-dialed JetStream handle (accept the concrete nats.JetStreamContext — the
// vendor SDK's own type, used only inside this adapter) and the spine clock. New dials nothing.
// (Idiomatic Go type name; HNS-1 rule 11 exempt.)
type Deps struct {
	// JetStream is the dialed JetStream context the composition root owns (it dials + reaps the conn).
	JetStream nats.JetStreamContext
	// Clock is the bridge's time source for heartbeat scheduling (shared with the edenhttp.Spine).
	Clock edenhttp.Clock
}

// Bridge is the concrete JetStream→SSE bridge. Construct via New; Stream(...) serves one SSE request.
// Safe for concurrent use across requests (it holds immutable configuration + the concurrency-safe
// JetStream handle); a single Stream call owns one consumer and one SSEStream (the SSE one-writer
// contract).
type Bridge struct {
	jetStream         nats.JetStreamContext
	clock             edenhttp.Clock
	stream            string
	heartbeatInterval time.Duration
}

// New constructs the bridge over a dialed JetStream handle. PURE: it dials nothing and reads no env.
// A nil JetStream or Clock is a construction error (KindInvalid).
//
//nolint:gocritic // contract: Config is the frozen, copyable bridge input; New takes it by value.
func New(configuration Config, dependencies Deps) (*Bridge, error) {
	if dependencies.JetStream == nil {
		return nil, errors.Wrap(errors.KindInvalid, "natssse: New",
			edenhttp.ConfigError{Field: "JetStream", Message: "a dialed nats.JetStreamContext is required"})
	}
	if dependencies.Clock == nil {
		return nil, errors.Wrap(errors.KindInvalid, "natssse: New",
			edenhttp.ConfigError{Field: "Clock", Message: "an injected Clock is required"})
	}
	stream := configuration.Stream
	if stream == "" {
		// The durable stream's well-known name has one home: the agentruntime protocol owner
		// (cited, never re-spelled). Citing the root protocol package — which natssse already
		// imports — does NOT pull the natsbus adapter (and its nats production import) into the
		// graph; only the stream-name wire contract is shared (one concept, one home).
		stream = agentruntime.EventsStreamName
	}
	interval := configuration.HeartbeatInterval
	if interval <= 0 {
		interval = edenhttp.DefaultHeartbeatInterval
	}
	return &Bridge{
		jetStream:         dependencies.JetStream,
		clock:             dependencies.Clock,
		stream:            stream,
		heartbeatInterval: interval,
	}, nil
}

// Stream serves one SSE request: it opens an ephemeral JetStream consumer on agent.<agentID>.events
// starting AFTER lastSeq (so a reconnect from Last-Event-ID N resumes at N+1; lastSeq==edenhttp
// .CursorAll replays the whole durable stream), then pumps each EventEnvelope to sse as one SSE
// frame (id == Seq, event == the agentsession EventKind token, data == the redaction-safe envelope
// JSON) until the agent's terminal event, a client disconnect (ctx canceled), or a fault. It emits
// a keepalive heartbeat each time a fetch window passes with no event, so a quiet stream stays open.
//
// Reaping: the consumer + subscription are unsubscribed on EVERY exit path (terminal, disconnect,
// fault) via a deferred drain, so no NATS subscription or goroutine outlives the call (goleak-clean,
// the ADR-0020 reap invariant). It returns nil on a clean terminal or a client disconnect, and a
// wrapped error on a JetStream/transport fault (after writing a trailing SSE error comment).
func (b *Bridge) Stream(ctx context.Context, agentID agentruntime.AgentID, lastSeq uint64, sse *edenhttp.SSEStream) error {
	subject := agentruntime.EventsSubject(agentID)
	subscription, err := b.openConsumer(subject, lastSeq)
	if err != nil {
		sse.Comment(errors.KindOf(err))
		return err
	}
	// Reap the ephemeral consumer + subscription on EVERY exit path (no orphan subscription).
	defer func() {
		//nolint:errcheck // best-effort reap on teardown; the request is ending regardless.
		_ = subscription.Unsubscribe()
	}()

	lastHeartbeat := b.clock.Now()
	for {
		if ctx.Err() != nil {
			return nil // client disconnected; clean teardown (the deferred Unsubscribe reaps).
		}
		message, fetchErr := fetchNext(ctx, subscription)
		if fetchErr != nil {
			done, hbErr := b.onFetchGap(ctx, sse, fetchErr, &lastHeartbeat)
			if hbErr != nil {
				return hbErr
			}
			if done {
				return nil
			}
			continue
		}
		terminal, sendErr := b.forward(message, sse)
		if sendErr != nil {
			sse.Comment(errors.KindOf(sendErr))
			return sendErr
		}
		lastHeartbeat = b.clock.Now()
		if terminal {
			return nil // the single terminal event ends the stream cleanly.
		}
	}
}

// openConsumer opens an ephemeral JetStream push consumer on subject. lastSeq==CursorAll replays the
// whole durable stream (DeliverAll); a positive lastSeq starts delivery at lastSeq+1 (StartSequence),
// so the reconnecting client gets exactly the missing events with no duplicate of lastSeq.
//
//nolint:ireturn // nats.*Subscription is the vendor SDK's own type the adapter returns as the SDK vends it.
func (b *Bridge) openConsumer(subject string, lastSeq uint64) (*nats.Subscription, error) {
	options := []nats.SubOpt{nats.AckNone(), nats.BindStream(b.stream)}
	if lastSeq == edenhttp.CursorAll {
		options = append(options, nats.DeliverAll())
	} else {
		options = append(options, nats.StartSequence(lastSeq+1))
	}
	subscription, err := b.jetStream.SubscribeSync(subject, options...)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "natssse: open jetstream consumer", err)
	}
	return subscription, nil
}

// forward decodes one JetStream message into an EventEnvelope and writes it as one SSE frame (id ==
// Seq). It returns whether the event is the session terminal. A decode fault is a wrapped
// KindInternal (a malformed envelope on a durable stream is our bug); a send fault is wrapped by Send.
func (b *Bridge) forward(message *nats.Msg, sse *edenhttp.SSEStream) (terminal bool, err error) {
	var envelope agentruntime.EventEnvelope
	if decodeErr := json.Unmarshal(message.Data, &envelope); decodeErr != nil {
		return false, errors.Wrap(errors.KindInternal, "natssse: decode event envelope", decodeErr)
	}
	if sendErr := sse.Send(edenhttp.SSEFrame{
		ID:    envelope.Seq,
		Event: envelope.Event.Kind.String(),
		Data:  message.Data,
	}); sendErr != nil {
		return false, errors.Wrap(errors.KindOf(sendErr), "natssse: forward event frame", sendErr)
	}
	return envelope.Event.IsTerminal(), nil
}

// onFetchGap handles a fetch that returned no message: a canceled request context is a clean client
// disconnect (done, no error); a timeout is the quiet-stream case (emit a keepalive if the cadence
// elapsed, then keep pumping); any other error is a real transport fault surfaced after a trailing
// comment. The ctx-cancel path returns (true, nil) DELIBERATELY — a client disconnect is a clean end
// of a long-lived stream, not a fault to propagate (ctx.Err() is the disconnect signal, not the
// error being suppressed).
//
//nolint:nilerr // a canceled request context is a clean client disconnect; returning nil is the contract, not a swallowed fetch error.
func (b *Bridge) onFetchGap(ctx context.Context, sse *edenhttp.SSEStream, fetchErr error, lastHeartbeat *time.Time) (done bool, err error) {
	if ctx.Err() != nil {
		return true, nil // client disconnected — clean end of stream.
	}
	if errors.Is(fetchErr, nats.ErrTimeout) || errors.Is(fetchErr, context.DeadlineExceeded) {
		if b.clock.Now().Sub(*lastHeartbeat) >= b.heartbeatInterval {
			if hbErr := sse.Heartbeat(); hbErr != nil {
				return false, errors.Wrap(errors.KindOf(hbErr), "natssse: keepalive", hbErr)
			}
			*lastHeartbeat = b.clock.Now()
		}
		return false, nil // quiet stream; keep pumping.
	}
	wrapped := errors.Wrap(errors.KindUnavailable, "natssse: jetstream fetch", fetchErr)
	sse.Comment(errors.KindOf(wrapped))
	return false, wrapped
}

// fetchNext performs one bounded JetStream fetch: it derives a fetchTimeout-bounded child of the
// request context, calls NextMsgWithContext, and ALWAYS cancels the child before returning (no timer
// leak — the cancel runs after the fetch completes, so the in-flight call is never raced). A
// deadline elapse surfaces as nats.ErrTimeout/context.DeadlineExceeded the caller treats as a quiet
// stream; a parent cancel surfaces as context.Canceled the caller treats as a client disconnect.
func fetchNext(parent context.Context, subscription *nats.Subscription) (*nats.Msg, error) {
	ctx, cancel := context.WithTimeout(parent, fetchTimeout)
	defer cancel()
	message, err := subscription.NextMsgWithContext(ctx)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "natssse: fetch next message", err)
	}
	return message, nil
}
