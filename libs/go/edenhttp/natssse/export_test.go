package natssse

import (
	"context"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/edenhttp"
)

// This file exposes the bridge's unexported FAULT branches (forward / openConsumer / onFetchGap) to
// the black-box fault_test.go, the house white-box seam (mirrors agentsession/<harness>adapter's
// export_test.go). Compiled ONLY under test, so none of this is part of the public surface
// (.apibaseline is untouched). The branches are pure given their inputs, so the black-box test drives
// the REAL bridge logic with a synthetic *nats.Msg / error and a real httptest-backed SSEStream — no
// mock of the logic under test; only the terminal SubscribeSync SDK call is fault-injected.

// ForwardForTest exposes b.forward: decode one JetStream message into an SSE frame, returning whether
// the event is terminal and any (typed) decode/send fault.
func (b *Bridge) ForwardForTest(message *nats.Msg, sse *edenhttp.SSEStream) (terminal bool, err error) {
	return b.forward(message, sse)
}

// OpenConsumerForTest exposes b.openConsumer: open the ephemeral JetStream consumer, returning the
// subscription or a typed open fault (the SubscribeSync error-wrap arm).
//
//nolint:ireturn // mirrors the unexported openConsumer: nats.*Subscription is the vendor SDK's own type.
func (b *Bridge) OpenConsumerForTest(subject string, lastSeq uint64) (*nats.Subscription, error) {
	return b.openConsumer(subject, lastSeq)
}

// OnFetchGapForTest exposes b.onFetchGap: classify a fetch that returned no message (clean disconnect
// / quiet-stream timeout / real transport fault), returning whether the stream is cleanly done and any
// surfaced fault.
func (b *Bridge) OnFetchGapForTest(ctx context.Context, sse *edenhttp.SSEStream, fetchErr error, lastHeartbeat *time.Time) (done bool, err error) {
	return b.onFetchGap(ctx, sse, fetchErr, lastHeartbeat)
}

// ClockNowForTest reports the bridge's injected clock instant, so a fault test seeds lastHeartbeat
// from the SAME clock the bridge schedules against (the heartbeat-cadence branch).
func (b *Bridge) ClockNowForTest() time.Time { return b.clock.Now() }
