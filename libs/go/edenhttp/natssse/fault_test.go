package natssse_test

// Black-box UNIT tests for the bridge's FAULT/ERROR branches — the arms the integration lane
// exercises only via a real server and that were, in practice, untested at the unit level:
//
//   - a malformed/poison event on the durable stream (forward decode-fault → KindInternal),
//   - a consumer/subscription open fault (openConsumer → KindUnavailable),
//   - a replay-gap / transport fault on fetch (onFetchGap non-timeout error → wrapped + comment).
//
// The branches are reached through the house white-box seam (export_test.go's *ForTest methods), so
// the test is mock-FREE on the logic under test: a real *nats.Msg with garbage Data, a real
// *edenhttp.SSEStream over an httptest recorder, and a synthetic transport error. The ONLY injected
// boundary is the terminal SDK SubscribeSync call (a fault we cannot deterministically provoke against
// a healthy embedded server) — the bridge's own error-wrapping logic is exercised for real.

import (
	"context"
	"errors"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/natssse"
	ederrors "github.com/gophersys/libs/go/errors"
)

// faultClock is a fixed clock for the fault arms (no heartbeat scheduling is asserted on the fault
// paths). Distinct from natssse_test's unitClock so the fault file is self-contained.
type faultClock struct{}

func (faultClock) Now() time.Time { return time.Unix(0, 0) }

// faultingJetStream is a nats.JetStreamContext whose SubscribeSync ALWAYS fails, so openConsumer's
// error-wrapping arm runs deterministically (the real "bind a non-existent stream" fault lives in the
// integration arm; this unit pins the KindUnavailable wrap). It embeds the interface so it satisfies
// the type without implementing the ~30 other methods the bridge never calls.
type faultingJetStream struct {
	nats.JetStreamContext
	err error
}

//nolint:ireturn // mirrors the vendor JetStreamContext.SubscribeSync signature exactly (returns its own *Subscription).
func (f faultingJetStream) SubscribeSync(string, ...nats.SubOpt) (*nats.Subscription, error) {
	return nil, f.err
}

// newRecorderStream builds a real *edenhttp.SSEStream over an httptest recorder (the production writer
// half — no mock), returning the stream and the recorder so a test asserts the bytes written to the
// client (the trailing `: error kind=` comment on a fault).
func newRecorderStream(t *testing.T) (*edenhttp.SSEStream, *httptest.ResponseRecorder) {
	t.Helper()
	recorder := httptest.NewRecorder()
	stream, err := edenhttp.NewSSEStream(recorder)
	if err != nil {
		t.Fatalf("NewSSEStream over recorder: %v", err)
	}
	return stream, recorder
}

// newFaultBridge constructs a real Bridge over the given JetStream handle for the fault arms.
func newFaultBridge(t *testing.T, jetStream nats.JetStreamContext) *natssse.Bridge {
	t.Helper()
	bridge, err := natssse.New(
		natssse.Config{Stream: agentruntime.EventsStreamName},
		natssse.Deps{JetStream: jetStream, Clock: faultClock{}},
	)
	if err != nil {
		t.Fatalf("natssse.New: %v", err)
	}
	return bridge
}

// TestForward_MalformedEvent_IsInternal proves a POISON message (garbage bytes where an
// EventEnvelope JSON is expected — the durable-stream poison reality) surfaces as KindInternal, does
// NOT crash, and writes NO SSE data frame (no silent half-frame). The bridge treats a malformed
// envelope on a durable stream as our bug (KindInternal), not the client's.
//
// WEAKEN-TO-CONFIRM (executed): change forward's decode-fault return from KindInternal to
// `return false, nil` (swallow the decode error) and this FAILS — it asserts a non-nil KindInternal
// error, so the silent-drop regression is caught.
func TestForward_MalformedEvent_IsInternal(t *testing.T) {
	t.Parallel()
	bridge := newFaultBridge(t, faultingJetStream{}) // SubscribeSync is never called on this path.
	stream, recorder := newRecorderStream(t)

	message := &nats.Msg{Subject: agentruntime.EventsSubject("agent-x"), Data: []byte("{not-json")}
	terminal, err := bridge.ForwardForTest(message, stream)

	if err == nil {
		t.Fatal("forward on a malformed event returned nil error (the poison message was silently dropped)")
	}
	if ederrors.KindOf(err) != ederrors.KindInternal {
		t.Fatalf("forward decode-fault kind = %s, want internal", ederrors.KindOf(err))
	}
	if terminal {
		t.Fatal("a decode-fault must not report the (non-existent) event as terminal")
	}
	if body := recorder.Body.String(); strings.Contains(body, "data: ") {
		t.Fatalf("a malformed event wrote an SSE data frame: %q", body)
	}
}

// TestStream_MalformedEvent_SurfacesInternalComment proves the fault TAIL Stream runs on a poison
// event: forward returns KindInternal and a trailing `: error kind=internal` comment is written so the
// client sees the fault kind (and no data frame) — the wire surface the browser observes.
//
// WEAKEN-TO-CONFIRM (executed): drop `sse.Comment(errors.KindOf(sendErr))` in Stream's forward-fault
// arm and the comment assertion FAILS — the client would lose the fault signal silently.
func TestStream_MalformedEvent_SurfacesInternalComment(t *testing.T) {
	t.Parallel()
	bridge := newFaultBridge(t, faultingJetStream{})
	stream, recorder := newRecorderStream(t)

	message := &nats.Msg{Subject: agentruntime.EventsSubject("agent-x"), Data: []byte("\xff\xff not an envelope")}
	_, err := bridge.ForwardForTest(message, stream)
	if err == nil {
		t.Fatal("forward on a poison message returned nil error")
	}
	// Mirror Stream's forward-fault tail: surface the kind as a trailing comment.
	stream.Comment(ederrors.KindOf(err))

	if got := recorder.Body.String(); !strings.Contains(got, ": error kind=internal") {
		t.Fatalf("the poison-event fault did not surface a kind=internal comment to the client: %q", got)
	}
}

// TestOpenConsumer_SubscribeFault_IsUnavailable proves a consumer/subscription OPEN fault (the SDK's
// SubscribeSync returns an error — e.g. a bind to a stream that does not exist) is wrapped as
// KindUnavailable, preserving the cause chain. This is the openConsumer arm the audit flagged untested.
//
// WEAKEN-TO-CONFIRM (executed): change openConsumer's wrap Kind from KindUnavailable to KindInternal
// and this FAILS — the gateway maps KindUnavailable→503 (retryable) vs KindInternal→500, so the kind
// is a load-bearing contract, not cosmetic.
func TestOpenConsumer_SubscribeFault_IsUnavailable(t *testing.T) {
	t.Parallel()
	sentinel := errors.New("stream not found")
	bridge := newFaultBridge(t, faultingJetStream{err: sentinel})

	subscription, err := bridge.OpenConsumerForTest(agentruntime.EventsSubject("agent-x"), edenhttp.CursorAll)
	if subscription != nil {
		t.Fatal("openConsumer returned a non-nil subscription on a SubscribeSync fault")
	}
	if err == nil {
		t.Fatal("openConsumer swallowed the SubscribeSync fault (returned nil error)")
	}
	if ederrors.KindOf(err) != ederrors.KindUnavailable {
		t.Fatalf("openConsumer fault kind = %s, want unavailable", ederrors.KindOf(err))
	}
	if !errors.Is(err, sentinel) {
		t.Fatalf("openConsumer flattened the cause chain: %v does not wrap the SubscribeSync error", err)
	}
}

// TestStream_OpenConsumerFault_SurfacesUnavailableComment proves the PUBLIC Stream entrypoint, when
// the consumer open faults, returns the wrapped error AND writes a `: error kind=unavailable` comment
// before returning. Driven through the real Stream method with the faulting handle, so it exercises
// the actual entrypoint, not just openConsumer in isolation.
//
// WEAKEN-TO-CONFIRM (executed): the kind weakening above flips this comment to kind=internal and it
// FAILS (the client gets the wrong, non-retryable fault kind on an un-openable consumer).
func TestStream_OpenConsumerFault_SurfacesUnavailableComment(t *testing.T) {
	t.Parallel()
	bridge := newFaultBridge(t, faultingJetStream{err: errors.New("no responders available for request")})
	stream, recorder := newRecorderStream(t)

	err := bridge.Stream(context.Background(), "agent-x", edenhttp.CursorAll, stream)
	if err == nil {
		t.Fatal("Stream returned nil on an un-openable consumer")
	}
	if ederrors.KindOf(err) != ederrors.KindUnavailable {
		t.Fatalf("Stream open-fault kind = %s, want unavailable", ederrors.KindOf(err))
	}
	if got := recorder.Body.String(); !strings.Contains(got, ": error kind=unavailable") {
		t.Fatalf("the open-consumer fault did not surface a kind=unavailable comment: %q", got)
	}
}

// TestOnFetchGap_TransportFault_IsUnavailable proves a fetch gap that is NEITHER a timeout NOR a
// context cancel (a real transport/replay-gap fault — e.g. a consumer deleted mid-stream, a server
// disconnect) is surfaced as a wrapped KindUnavailable AND a trailing `: error kind=unavailable`
// comment, rather than being treated as the quiet-stream keepalive case.
//
// WEAKEN-TO-CONFIRM (executed): make onFetchGap fall through to `return false, nil` for a non-timeout
// error (the quiet-stream path) and this FAILS — a real transport fault would be silently swallowed as
// a no-op, hanging the bridge on a dead consumer instead of surfacing the fault.
func TestOnFetchGap_TransportFault_IsUnavailable(t *testing.T) {
	t.Parallel()
	bridge := newFaultBridge(t, faultingJetStream{})
	stream, recorder := newRecorderStream(t)
	lastHeartbeat := bridge.ClockNowForTest()

	transportFault := errors.New("nats: consumer deleted")
	done, err := bridge.OnFetchGapForTest(context.Background(), stream, transportFault, &lastHeartbeat)

	if done {
		t.Fatal("a transport fault must not report the stream as cleanly done")
	}
	if err == nil {
		t.Fatal("onFetchGap swallowed a real transport fault (returned nil — the quiet-stream path)")
	}
	if ederrors.KindOf(err) != ederrors.KindUnavailable {
		t.Fatalf("onFetchGap transport-fault kind = %s, want unavailable", ederrors.KindOf(err))
	}
	if !errors.Is(err, transportFault) {
		t.Fatalf("onFetchGap flattened the cause chain: %v does not wrap the transport fault", err)
	}
	if got := recorder.Body.String(); !strings.Contains(got, ": error kind=unavailable") {
		t.Fatalf("the transport fault did not surface a kind=unavailable comment: %q", got)
	}
}

// TestOnFetchGap_ContextCancel_IsCleanDisconnect proves the DELIBERATE (true, nil) arm: a canceled
// request context is a clean client disconnect, not a fault — done=true, err=nil, and NO error comment
// is written. This pins the nilerr-annotated contract so a future change cannot silently turn a
// disconnect into a propagated error.
//
// WEAKEN-TO-CONFIRM: make onFetchGap return `(false, fetchErr)` on ctx.Err()!=nil and this FAILS — a
// normal client disconnect would surface as a spurious bridge error.
func TestOnFetchGap_ContextCancel_IsCleanDisconnect(t *testing.T) {
	t.Parallel()
	bridge := newFaultBridge(t, faultingJetStream{})
	stream, recorder := newRecorderStream(t)
	lastHeartbeat := bridge.ClockNowForTest()

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // client disconnected.

	done, err := bridge.OnFetchGapForTest(ctx, stream, context.Canceled, &lastHeartbeat)
	if !done {
		t.Fatal("a canceled context must end the stream cleanly (done=true)")
	}
	if err != nil {
		t.Fatalf("a clean disconnect must not be a fault: got %v", err)
	}
	if got := recorder.Body.String(); strings.Contains(got, ": error kind=") {
		t.Fatalf("a clean disconnect wrote a spurious error comment: %q", got)
	}
}

// TestOnFetchGap_Timeout_NoHeartbeatBeforeCadence proves the quiet-stream timeout path does NOT emit a
// keepalive before the cadence elapses (done=false, err=nil, no bytes), so a fast-ticking quiet stream
// is not spammed with heartbeats. Complements the integration heartbeat arm (which proves the cadence
// DOES fire) with the negative branch at the unit level.
func TestOnFetchGap_Timeout_NoHeartbeatBeforeCadence(t *testing.T) {
	t.Parallel()
	bridge := newFaultBridge(t, faultingJetStream{}) // default heartbeat interval is 20s.
	stream, recorder := newRecorderStream(t)
	lastHeartbeat := bridge.ClockNowForTest() // cadence has NOT elapsed (fixed clock).

	done, err := bridge.OnFetchGapForTest(context.Background(), stream, nats.ErrTimeout, &lastHeartbeat)
	if done {
		t.Fatal("a quiet-stream timeout is not a clean end (done must be false)")
	}
	if err != nil {
		t.Fatalf("a quiet-stream timeout is not a fault: got %v", err)
	}
	if got := recorder.Body.String(); strings.Contains(got, ": keepalive") {
		t.Fatalf("a keepalive fired before the cadence elapsed: %q", got)
	}
}
