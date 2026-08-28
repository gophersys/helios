package slogadapter_test

import (
	"bytes"
	"context"
	"encoding/json"
	stderrors "errors"
	"log/slog"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/observabilitytest"
	"github.com/gophersys/libs/go/observability/slogadapter"
)

// TestSlogAdapterPassesProviderConformance drives the SHARED conformance suite
// against the real observability.Provider exporting through the real slogadapter,
// proving the Exporter seam has one real, conformance-tested adapter — not a
// test-only stub (the finding's gap).
func TestSlogAdapterPassesProviderConformance(t *testing.T) {
	t.Parallel()
	observabilitytest.RunProviderSuite(t, func(c observability.Config, d observability.Deps) (observability.Provider, error) {
		// The suite hands its own Exporter in d.Exporter (a recordingExporter, a
		// panicExporter for purity, or a FailingExporter for the Flush-error path).
		// Wrap whatever it provides so the real slog rendering runs on top of it,
		// while the suite still inspects the Records via its own Exporter. Leave a
		// nil Exporter untouched so the NewValidationErrors property (which passes
		// a nil Exporter to prove New rejects it) still reaches the validation path.
		if d.Exporter != nil {
			d.Exporter = &slogTee{inner: d.Exporter, sink: slogadapter.New(&nopWriter{})}
		}
		//nolint:wrapcheck // observability.New's *ConfigError is the contract's own typed error, surfaced as-is.
		return observability.New(c, d)
	})
}

// slogTee renders each batch through a real slogadapter sink (exercising its full
// path) and then delegates to the suite's own Exporter so every Record-level
// assertion the suite makes still observes the batch.
type slogTee struct {
	inner observability.Exporter
	sink  observability.Exporter
}

func (t *slogTee) Export(ctx context.Context, records []observability.Record) error {
	// Render through the real adapter for its rendering side effect; the suite's
	// inner Exporter owns the pass/fail (including the forced Flush error), so the
	// sink's nop-writer result is deliberately not the contract value here.
	//nolint:errcheck,gosec // G104: the sink writes to a nop-writer for its rendering side effect only; its result is deliberately not the contract value (the suite's inner Exporter owns pass/fail).
	t.sink.Export(ctx, records)
	//nolint:wrapcheck // delegating to the suite's Exporter; its error is the contract's, surfaced as-is.
	return t.inner.Export(ctx, records)
}

// nopWriter discards rendered slog output: the conformance run only needs the
// adapter's rendering path to EXECUTE on real traffic, not to be inspected here
// (TestSlogAdapterRendersRecord inspects the actual bytes).
type nopWriter struct{}

func (*nopWriter) Write(p []byte) (int, error) { return len(p), nil }

// TestSlogAdapterRendersRecord asserts the real bytes slogadapter writes: the
// leveled line, the resource attributes, the plane, the trace/span correlation,
// and every Field as its already-redacted projection — the real-substrate
// behavior a mock cannot prove.
func TestSlogAdapterRendersRecord(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	exp := slogadapter.New(&buf)

	rec := observability.Record{
		Event: observability.Event{
			Time:     time.Unix(1700000000, 0).UTC(),
			Plane:    observability.PlaneAgent,
			Severity: observability.SeverityWarn,
			Name:     "cost.ledger",
			Fields: []observability.Field{
				observability.Int64("tokens.in", 1200),
				observability.Bool("gate.passed", true),
				observability.Dur("wall.time", 5*time.Second),
				observability.Any("token", redacting{}),
			},
		},
		Resource: map[string]string{"service.name": "eden-backend", "deployment.environment.name": "test"},
		TraceID:  "trace-7",
		SpanID:   "span-7",
	}
	if err := exp.Export(context.Background(), []observability.Record{rec}); err != nil {
		t.Fatalf("Export: %v", err)
	}

	var line map[string]any
	if err := json.Unmarshal(buf.Bytes(), &line); err != nil {
		t.Fatalf("slog output is not valid JSON: %v\n%s", err, buf.String())
	}
	checks := map[string]any{
		"event.name":                  "cost.ledger",
		"plane":                       "agent",
		"trace.id":                    "trace-7",
		"span.id":                     "span-7",
		"service.name":                "eden-backend",
		"deployment.environment.name": "test",
		"level":                       "WARN",
		"tokens.in":                   float64(1200), // JSON numbers decode as float64
		"gate.passed":                 true,
		"token":                       "secrets.Secret(REDACTED)",
	}
	for k, want := range checks {
		if got := line[k]; got != want {
			t.Errorf("slog line[%q] = %#v, want %#v", k, got, want)
		}
	}
	// The redacted token must never appear raw anywhere on the line.
	if strings.Contains(buf.String(), "s3cr3t") {
		t.Errorf("raw secret leaked into the slog line: %s", buf.String())
	}
}

// TestSlogAdapterSeverityToLevel pins the Severity→slog.Level mapping the adapter
// owns.
func TestSlogAdapterSeverityToLevel(t *testing.T) {
	t.Parallel()
	cases := []struct {
		sev  observability.Severity
		want string
	}{
		{observability.SeverityDebug, "DEBUG"},
		{observability.SeverityInfo, "INFO"},
		{observability.SeverityWarn, "WARN"},
		{observability.SeverityError, "ERROR"},
	}
	for _, c := range cases {
		var buf bytes.Buffer
		exp := slogadapter.New(&buf)
		err := exp.Export(context.Background(), []observability.Record{
			{Event: observability.Event{Name: "e", Severity: c.sev}},
		})
		if err != nil {
			t.Fatalf("Export: %v", err)
		}
		var line map[string]any
		if uerr := json.Unmarshal(buf.Bytes(), &line); uerr != nil {
			t.Fatalf("invalid JSON: %v", uerr)
		}
		if line["level"] != c.want {
			t.Errorf("Severity %v rendered level %v, want %v", c.sev, line["level"], c.want)
		}
	}
}

// TestSlogAdapterHonorsContextCancellation proves Export unwinds on a canceled
// ctx (the one failure a batch write observes here) rather than shipping the rest.
func TestSlogAdapterHonorsContextCancellation(t *testing.T) {
	t.Parallel()
	exp := slogadapter.New(&nopWriter{})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err := exp.Export(ctx, []observability.Record{{Event: observability.Event{Name: "e"}}})
	if !stderrors.Is(err, context.Canceled) {
		t.Errorf("Export on a canceled ctx = %v, want context.Canceled", err)
	}
}

// TestSlogAdapterNilWriterDiscards proves a nil writer is treated as io.Discard so
// a mis-wired root drops telemetry rather than panicking.
func TestSlogAdapterNilWriterDiscards(t *testing.T) {
	t.Parallel()
	exp := slogadapter.New(nil)
	if err := exp.Export(context.Background(), []observability.Record{{Event: observability.Event{Name: "e"}}}); err != nil {
		t.Errorf("Export with nil writer errored: %v", err)
	}
}

// TestSlogAdapterNilValuerFieldDoesNotPanic proves a Field that carries a nil
// Valuer (a raw Field literal bypassing the Any guard) renders empty rather than
// nil-derefing in the adapter's serialization loop.
func TestSlogAdapterNilValuerFieldDoesNotPanic(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	exp := slogadapter.New(&buf)
	err := exp.Export(context.Background(), []observability.Record{
		{Event: observability.Event{Name: "e", Fields: []observability.Field{{Key: "poison", Value: nil}}}},
	})
	if err != nil {
		t.Fatalf("Export: %v", err)
	}
	var line map[string]any
	if uerr := json.Unmarshal(buf.Bytes(), &line); uerr != nil {
		t.Fatalf("invalid JSON: %v", uerr)
	}
	if line["poison"] != "" {
		t.Errorf("nil-Valuer Field rendered %#v, want \"\"", line["poison"])
	}
}

// TestSlogAdapterEndToEndThroughRealProvider wires the real observability.Provider
// to the real slogadapter and runs an engine-shaped phase (With + Scope + ledger),
// proving the full library→adapter path ships correct, redacted JSON lines — the
// real-substrate integration the Exporter seam previously lacked.
func TestSlogAdapterEndToEndThroughRealProvider(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	clock := &stepClock{now: time.Unix(1700000000, 0).UTC()}
	obs, err := observability.New(
		observability.Config{
			ServiceName: "eden-backend", ServiceVersion: "v0.1.0",
			Environment: "test", DefaultPlane: observability.PlaneSelf, MinSeverity: observability.SeverityInfo,
		},
		observability.Deps{Exporter: slogadapter.NewWithLogger(slog.New(slog.NewJSONHandler(&buf, nil))), Clock: clock},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	ctx := context.Background()
	runObs := obs.With(observability.String("run.id", "run-1"))
	ctx, end := runObs.Scope(ctx, "phase.start", observability.String("phase", "implement"))
	runObs.Emit(ctx, observability.LedgerEvent(clock.Now(), observability.Ledger{
		RunID: "run-1", PhaseID: "implement", Model: "claude", TokensIn: 10,
	}))
	clock.advance(2 * time.Second)
	end(observability.Outcome{})
	if ferr := obs.Flush(ctx); ferr != nil {
		t.Fatalf("Flush: %v", ferr)
	}

	lines := nonEmptyLines(buf.String())
	if len(lines) < 2 {
		t.Fatalf("expected at least the ledger + span lines, got %d:\n%s", len(lines), buf.String())
	}
	// Every shipped line must carry the inherited run.id and the resource service.name.
	for _, l := range lines {
		var m map[string]any
		if uerr := json.Unmarshal([]byte(l), &m); uerr != nil {
			t.Fatalf("line is not JSON: %v\n%s", uerr, l)
		}
		if m["run.id"] != "run-1" {
			t.Errorf("line missing inherited run.id: %s", l)
		}
		if m["service.name"] != "eden-backend" {
			t.Errorf("line missing resource service.name: %s", l)
		}
	}
}

func nonEmptyLines(s string) []string {
	var out []string
	for _, l := range strings.Split(strings.TrimSpace(s), "\n") {
		if strings.TrimSpace(l) != "" {
			out = append(out, l)
		}
	}
	return out
}

// redacting models a secrets.Secret-shaped Valuer: its projection is the redacted
// sentinel, never the raw material.
type redacting struct{}

func (redacting) TelemetryValue() any { return "secrets.Secret(REDACTED)" }

// stepClock is a manually-advanced clock so Scope durations are deterministic.
type stepClock struct {
	mu  sync.Mutex
	now time.Time
}

func (c *stepClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

func (c *stepClock) advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
}
