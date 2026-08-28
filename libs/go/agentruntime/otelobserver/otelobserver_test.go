package otelobserver_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/otelobserver"
	"github.com/gophersys/libs/go/observability"
)

// recordingExporter captures the Records the observability.Provider exports, so the otelobserver test
// proves Logf actually reaches the wire and Flush actually drains. It is the observability.Exporter
// seam (the outbound boundary), recorded under a mutex.
type recordingExporter struct {
	mu      sync.Mutex
	records []observability.Record
	flushed bool
}

func (e *recordingExporter) Export(_ context.Context, records []observability.Record) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.records = append(e.records, records...)
	e.flushed = true
	return nil
}

func (e *recordingExporter) count() int {
	e.mu.Lock()
	defer e.mu.Unlock()
	return len(e.records)
}

// fixedClock is a deterministic observability.Clock.
type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 14, 12, 0, 0, 0, time.UTC) }

// newObserver builds the otelobserver adapter over a REAL observability.Provider wired to a recording
// exporter, returning both so a test asserts the records reached the wire.
func newObserver(t *testing.T) (*otelobserver.Adapter, *recordingExporter) {
	t.Helper()
	exporter := &recordingExporter{}
	provider, err := observability.New(
		observability.Config{ServiceName: "agentruntime-test"},
		observability.Deps{Exporter: exporter, Clock: fixedClock{}},
	)
	if err != nil {
		t.Fatalf("construct observability.Provider: %v", err)
	}
	return otelobserver.New(provider), exporter
}

// TestLogfReachesProviderAndFlushDrains proves Logf emits onto the real Provider and Flush drains the
// buffered records to the exporter — the log + the OTel-flush shutdown step over a real backend.
func TestLogfReachesProviderAndFlushDrains(t *testing.T) {
	t.Parallel()
	observer, exporter := newObserver(t)
	ctx := context.Background()

	observer.Logf(ctx, "agent %q starting", "agent-1")
	observer.Logf(ctx, "agent %q stopped (%s)", "agent-1", "control-stop")
	if err := observer.Flush(ctx); err != nil {
		t.Fatalf("Flush: %v", err)
	}
	if exporter.count() == 0 {
		t.Errorf("Logf + Flush produced no exported records (the log did not reach the wire)")
	}
	if !exporter.flushed {
		t.Errorf("Flush did not drain to the exporter")
	}
}

// TestExtractInjectRoundTrip proves the W3C trace carrier round-trips: Extract a carried trace onto a
// ctx, then Inject reads it back — the OTel-on-every-message propagation the sidecar relies on. A
// carrier with non-trace keys is filtered to the W3C pair.
func TestExtractInjectRoundTrip(t *testing.T) {
	t.Parallel()
	observer, _ := newObserver(t)
	const traceParent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
	carrier := agentruntime.OTelContext{"traceparent": traceParent, "tracestate": "eden=1", "noise": "drop-me"}

	ctx := observer.Extract(context.Background(), carrier)
	got := observer.Inject(ctx)
	if got["traceparent"] != traceParent {
		t.Errorf("traceparent did not round-trip: got %q", got["traceparent"])
	}
	if got["tracestate"] != "eden=1" {
		t.Errorf("tracestate did not round-trip: got %q", got["tracestate"])
	}
	if _, present := got["noise"]; present {
		t.Errorf("non-W3C carrier key leaked through Extract: %v", got)
	}
}

// TestInjectEmptyOnNoTrace proves Inject on a ctx with no carried trace returns an empty carrier (an
// un-traced message is valid) — it never panics and never invents a trace.
func TestInjectEmptyOnNoTrace(t *testing.T) {
	t.Parallel()
	observer, _ := newObserver(t)
	got := observer.Inject(context.Background())
	if len(got) != 0 {
		t.Errorf("Inject on an un-traced ctx should be empty, got %v", got)
	}
}

// TestExtractEmptyCarrierIsIdentity proves Extract with an empty carrier returns the ctx unchanged
// (no spurious child ctx), so an un-traced control message does not corrupt the propagation chain.
func TestExtractEmptyCarrierIsIdentity(t *testing.T) {
	t.Parallel()
	observer, _ := newObserver(t)
	ctx := context.Background()
	if got := observer.Extract(ctx, nil); got != ctx {
		t.Errorf("Extract with a nil carrier should return the ctx unchanged")
	}
	if got := observer.Extract(ctx, agentruntime.OTelContext{}); got != ctx {
		t.Errorf("Extract with an empty carrier should return the ctx unchanged")
	}
}

// TestNilProviderIsSafe proves the adapter over a nil Provider is a safe no-op on the telemetry side
// (Logf/Flush do not panic) — the composition root still gets a usable Observer if it wires nil.
func TestNilProviderIsSafe(t *testing.T) {
	t.Parallel()
	observer := otelobserver.New(nil)
	observer.Logf(context.Background(), "no provider")
	if err := observer.Flush(context.Background()); err != nil {
		t.Errorf("Flush over a nil provider should be a no-op, got %v", err)
	}
}
