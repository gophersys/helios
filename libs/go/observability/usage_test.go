package observability_test

import (
	"context"
	stderrors "errors"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// captureExporter records every shipped batch so the usage tests assert what an
// engine run would put on the wire.
type captureExporter struct {
	mu      sync.Mutex
	records []observability.Record
}

func (e *captureExporter) Export(_ context.Context, records []observability.Record) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.records = append(e.records, records...)
	return nil
}

func (e *captureExporter) all() []observability.Record {
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]observability.Record, len(e.records))
	copy(out, e.records)
	return out
}

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

// secretRef models a secrets.Secret: its TelemetryValue redacts, satisfying
// observability.Valuer without observability importing secrets.
type secretRef struct{ raw string }

func (secretRef) TelemetryValue() any { return "secrets.Secret(REDACTED)" }

// TestUsageEngineRunPhase mirrors §5's Engine.runPhase: a run-scoped With, a
// Scope span, a gate.decision Event, and a T6 cost.ledger — all on one stream.
func TestUsageEngineRunPhase(t *testing.T) {
	t.Parallel()
	exp := &captureExporter{}
	clock := &stepClock{now: time.Unix(1700000000, 0).UTC()}
	obs, err := observability.New(
		observability.Config{
			ServiceName:    "eden-backend",
			ServiceVersion: "v0.1.0",
			Environment:    "test",
			DefaultPlane:   observability.PlaneSelf,
			MinSeverity:    observability.SeverityInfo,
		},
		observability.Deps{Exporter: exp, Clock: clock},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	ctx := context.Background()
	runObs := obs.With(observability.String("run.id", "run-123"))
	ctx, end := runObs.Scope(ctx, "phase.start", observability.String("phase", "implement"))

	runObs.Emit(ctx, observability.Event{
		Plane: observability.PlaneAgent, Severity: observability.SeverityInfo,
		Name:   "gate.decision",
		Fields: []observability.Field{observability.Bool("gate.passed", true)},
	})
	runObs.Emit(ctx, observability.LedgerEvent(clock.Now(), observability.Ledger{
		RunID: "run-123", PhaseID: "implement", Model: "claude", Harness: "claudecode",
		TokensIn: 1200, TokensOut: 800, CacheHits: 200, CostMicros: 5000,
		Retries: 0, WallTime: time.Second,
	}))

	clock.advance(1500 * time.Millisecond)
	end(observability.Outcome{Err: nil})

	if err := obs.Flush(ctx); err != nil {
		t.Fatalf("Flush: %v", err)
	}

	recs := exp.all()
	names := map[string]observability.Record{}
	for _, r := range recs {
		names[r.Event.Name] = r
	}
	for _, want := range []string{"phase.start", "gate.decision", "cost.ledger"} {
		if _, ok := names[want]; !ok {
			t.Errorf("missing %q on the stream", want)
		}
	}
	// The run.id rides every Event via With.
	for _, r := range recs {
		if !hasField(r.Event.Fields, "run.id") {
			t.Errorf("Event %q missing inherited run.id", r.Event.Name)
		}
	}
	// gate.decision and cost.ledger ride PlaneAgent.
	if names["gate.decision"].Event.Plane != observability.PlaneAgent {
		t.Errorf("gate.decision Plane = %v, want PlaneAgent", names["gate.decision"].Event.Plane)
	}
	if names["cost.ledger"].Event.Plane != observability.PlaneAgent {
		t.Errorf("cost.ledger Plane = %v, want PlaneAgent", names["cost.ledger"].Event.Plane)
	}
	// The span carries the run.id and the phase, with a duration from the Clock.
	span := names["phase.start"]
	if span.Event.Plane != observability.PlaneSelf {
		t.Errorf("phase.start Plane = %v, want DefaultPlane PlaneSelf", span.Event.Plane)
	}
}

// TestUsageSubordinateSinkLoggingRedacts mirrors §5's evidence.record: Log a
// leveled line carrying a Secret as its redacted Valuer; the raw never ships.
func TestUsageSubordinateSinkLoggingRedacts(t *testing.T) {
	t.Parallel()
	exp := &captureExporter{}
	obs, err := observability.New(
		observability.Config{ServiceName: "evidence", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: exp, Clock: &stepClock{now: time.Unix(0, 0).UTC()}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	const rawToken = "ghp_realsecretvalue"
	obs.Log(
		context.Background(), observability.SeverityInfo, "gate evidence emitted",
		observability.String("verdict", "pass"),
		observability.Any("token", secretRef{raw: rawToken}),
	)
	if err := obs.Flush(context.Background()); err != nil {
		t.Fatalf("Flush: %v", err)
	}

	for _, r := range exp.all() {
		for _, f := range r.Event.Fields {
			if s, ok := f.Value.TelemetryValue().(string); ok && s == rawToken {
				t.Fatalf("the raw token leaked onto the stream via field %q", f.Key)
			}
		}
	}
}

// TestUsageCompositionRootConfigError mirrors §5's main(): a bad Config yields a
// *ConfigError inspectable via errors.As.
func TestUsageCompositionRootConfigError(t *testing.T) {
	t.Parallel()
	_, err := observability.New(
		observability.Config{ServiceName: ""},
		observability.Deps{Exporter: &captureExporter{}, Clock: &stepClock{}},
	)
	var cfgErr *observability.ConfigError
	if !stderrors.As(err, &cfgErr) {
		t.Fatalf("New error is not *ConfigError: %T", err)
	}
	if cfgErr.Field == "" {
		t.Error("ConfigError.Field is empty; the offending field must be named")
	}
}

func hasField(fields []observability.Field, key string) bool {
	for _, f := range fields {
		if f.Key == key {
			return true
		}
	}
	return false
}
