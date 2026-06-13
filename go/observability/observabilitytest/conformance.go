package observabilitytest

import (
	"context"
	stderrors "errors"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// recordingExporter captures every batch shipped through Export, so the
// conformance suite inspects resource-stamped, correlation-stamped Records — the
// adapter's observation point. Safe for concurrent Export.
type recordingExporter struct {
	mu      sync.Mutex
	records []observability.Record
	delay   time.Duration // optional artificial latency to prove Emit never blocks on it
	err     error         // returned by Export when non-nil (Flush error path)
}

func (e *recordingExporter) Export(ctx context.Context, records []observability.Record) error {
	if e.delay > 0 {
		select {
		case <-time.After(e.delay):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	if e.err != nil {
		return e.err
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	e.records = append(e.records, records...)
	return nil
}

func (e *recordingExporter) snapshot() []observability.Record {
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]observability.Record, len(e.records))
	copy(out, e.records)
	return out
}

// stepClock is a manually-advanced clock the suite uses to make Scope-duration
// deterministic. Safe for concurrent use.
type stepClock struct {
	mu  sync.Mutex
	now time.Time
}

func newStepClock() *stepClock { return &stepClock{now: time.Unix(1700000000, 0).UTC()} }

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

// panicClock panics on Now — used to prove New reads no clock (purity).
type panicClock struct{}

func (panicClock) Now() time.Time { panic("clock read in New (purity violated)") }

// panicExporter panics on Export — used to prove New performs no I/O (purity).
type panicExporter struct{}

func (panicExporter) Export(context.Context, []observability.Record) error {
	panic("exporter called in New (purity violated)")
}

// canaryValuer is a Valuer whose raw material is a secret but whose
// TelemetryValue redacts — the secrets.Secret shape, locally modeled so the suite
// stays a leaf and never imports secrets.
type canaryValuer struct {
	raw      string
	redacted string
}

func (c canaryValuer) TelemetryValue() any { return c.redacted }

// RunFakeConformance runs the shared conformance suite (Run) against this
// package's own Deps-aware double (newConformanceProvider). It is the fake side
// of the adapter≡fake proof (08 §2): the real adapter's test calls Run with
// observability.New, this calls Run with the fake — both must pass identically.
func RunFakeConformance(t *testing.T) {
	t.Helper()
	Run(t, newConformanceProvider)
}

// Run drives any observability.Provider produced by newProvider through the
// substitutability properties (contract §4). The real adapter and
// observabilitytest.Provider must both pass identically.
func Run(t *testing.T, newProvider func(observability.Config, observability.Deps) (observability.Provider, error)) {
	t.Helper()
	if newProvider == nil {
		t.Fatal("Run: newProvider must not be nil")
	}

	baseConfig := func() observability.Config {
		return observability.Config{
			ServiceName:    "conformance-svc",
			ServiceVersion: "v1.2.3",
			Environment:    "test",
			DefaultPlane:   observability.PlaneSelf,
			ResourceAttrs:  map[string]string{"team": "kernel"},
		}
	}

	t.Run("PurityOfNew", func(t *testing.T) {
		// A panicking Clock/Exporter does not panic until first emit/flush.
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("New touched a port (panic): %v", r)
			}
		}()
		p, err := newProvider(baseConfig(), observability.Deps{
			Exporter: panicExporter{},
			Clock:    panicClock{},
		})
		if err != nil {
			t.Fatalf("New(valid) error: %v", err)
		}
		if p == nil {
			t.Fatal("New(valid) returned nil Provider")
		}
	})

	t.Run("NewValidationErrors", func(t *testing.T) {
		// Empty ServiceName is a *ConfigError.
		_, err := newProvider(observability.Config{ServiceName: ""}, observability.Deps{
			Exporter: &recordingExporter{}, Clock: newStepClock(),
		})
		if err == nil {
			t.Fatal("empty ServiceName produced no error")
		}
		var cfgErr *observability.ConfigError
		if !stderrors.As(err, &cfgErr) {
			t.Fatalf("empty ServiceName error is not *ConfigError: %T", err)
		}

		// Nil Exporter is a *ConfigError.
		_, err = newProvider(baseConfig(), observability.Deps{Exporter: nil, Clock: newStepClock()})
		if err == nil {
			t.Fatal("nil Exporter produced no error")
		}
		if !stderrors.As(err, &cfgErr) {
			t.Fatalf("nil Exporter error is not *ConfigError: %T", err)
		}
	})

	t.Run("EmitNonBlocking", func(t *testing.T) {
		// A slow Exporter must not stall the caller on Emit/With/Scope/Log.
		exp := &recordingExporter{delay: 24 * time.Hour}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})

		done := make(chan struct{})
		go func() {
			ctx := context.Background()
			p.Emit(ctx, observability.Event{Name: "x", Severity: observability.SeverityInfo})
			child := p.With(observability.String("run.id", "r1"))
			child.Log(ctx, observability.SeverityInfo, "hello")
			_, end := child.Scope(ctx, "phase.start")
			end(observability.Outcome{})
			close(done)
		}()
		select {
		case <-done:
		case <-time.After(2 * time.Second):
			t.Fatal("Emit/With/Scope/Log blocked on slow Exporter; the hot path must never stall")
		}
	})

	t.Run("SeverityFiltering", func(t *testing.T) {
		exp := &recordingExporter{}
		cfg := baseConfig()
		cfg.MinSeverity = observability.SeverityWarn
		p := mustNew(t, newProvider, cfg, observability.Deps{Exporter: exp, Clock: newStepClock()})
		ctx := context.Background()

		p.Emit(ctx, observability.Event{Name: "below", Severity: observability.SeverityInfo})
		p.Emit(ctx, observability.Event{Name: "at", Severity: observability.SeverityWarn})
		p.Emit(ctx, observability.Event{Name: "above", Severity: observability.SeverityError})
		flush(t, p)

		names := recordNames(exp.snapshot())
		if has(names, "below") {
			t.Errorf("Event below MinSeverity was not dropped: %v", names)
		}
		if !has(names, "at") || !has(names, "above") {
			t.Errorf("Events at/above MinSeverity were dropped: %v", names)
		}
	})

	t.Run("SeverityZeroEmitsEverything", func(t *testing.T) {
		exp := &recordingExporter{}
		// Zero MinSeverity (SeverityDebug) == emit everything.
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
		ctx := context.Background()
		p.Emit(ctx, observability.Event{Name: "debug", Severity: observability.SeverityDebug})
		flush(t, p)
		if !has(recordNames(exp.snapshot()), "debug") {
			t.Error("zero MinSeverity dropped a Debug Event; it must emit everything")
		}
	})

	t.Run("PlaneStamping", func(t *testing.T) {
		exp := &recordingExporter{}
		cfg := baseConfig()
		cfg.DefaultPlane = observability.PlaneSelf
		p := mustNew(t, newProvider, cfg, observability.Deps{Exporter: exp, Clock: newStepClock()})
		ctx := context.Background()

		// PlaneUnset inherits DefaultPlane.
		p.Emit(ctx, observability.Event{Name: "unset", Severity: observability.SeverityInfo, Plane: observability.PlaneUnset})
		// An explicit Plane is preserved unchanged.
		p.Emit(ctx, observability.Event{Name: "explicit", Severity: observability.SeverityInfo, Plane: observability.PlaneAgent})
		flush(t, p)

		recs := exp.snapshot()
		unset := findRecord(recs, "unset")
		explicit := findRecord(recs, "explicit")
		if unset == nil || explicit == nil {
			t.Fatalf("missing records: %v", recordNames(recs))
		}
		if unset.Event.Plane != observability.PlaneSelf {
			t.Errorf("PlaneUnset Event landed on %v, want DefaultPlane PlaneSelf", unset.Event.Plane)
		}
		if explicit.Event.Plane != observability.PlaneAgent {
			t.Errorf("explicit Plane changed to %v, want PlaneAgent (preserved)", explicit.Event.Plane)
		}
	})

	t.Run("ResourceStamping", func(t *testing.T) {
		exp := &recordingExporter{}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
		p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo})
		flush(t, p)

		recs := exp.snapshot()
		if len(recs) == 0 {
			t.Fatal("no Records shipped")
		}
		r := recs[0]
		want := map[string]string{
			"service.name":                "conformance-svc",
			"service.version":             "v1.2.3",
			"deployment.environment.name": "test",
			"team":                        "kernel",
		}
		for k, v := range want {
			if got := r.Resource[k]; got != v {
				t.Errorf("Resource[%q] = %q, want %q", k, got, v)
			}
		}
		// The deprecated key must NOT be present (10 §2).
		if _, ok := r.Resource["deployment.environment"]; ok {
			t.Error("Record carries the deprecated deployment.environment key")
		}
	})

	t.Run("WithInheritance", func(t *testing.T) {
		exp := &recordingExporter{}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
		ctx := context.Background()

		child := p.With(observability.String("run.id", "r-42"))
		child.Emit(ctx, observability.Event{Name: "child", Severity: observability.SeverityInfo,
			Fields: []observability.Field{observability.String("phase", "implement")}})
		// The parent is unaffected.
		p.Emit(ctx, observability.Event{Name: "parent", Severity: observability.SeverityInfo})
		flush(t, p)

		recs := exp.snapshot()
		childRec := findRecord(recs, "child")
		parentRec := findRecord(recs, "parent")
		if childRec == nil || parentRec == nil {
			t.Fatalf("missing records: %v", recordNames(recs))
		}
		// Inherited Fields precede call-site Fields, order-preserving.
		if len(childRec.Event.Fields) < 2 {
			t.Fatalf("child Event missing inherited fields: %#v", fieldKeys(childRec.Event.Fields))
		}
		if childRec.Event.Fields[0].Key != "run.id" {
			t.Errorf("inherited field is not first: %v", fieldKeys(childRec.Event.Fields))
		}
		if childRec.Event.Fields[len(childRec.Event.Fields)-1].Key != "phase" {
			t.Errorf("call-site field is not last: %v", fieldKeys(childRec.Event.Fields))
		}
		// Parent carries no inherited run.id.
		if hasFieldKey(parentRec.Event.Fields, "run.id") {
			t.Error("With mutated the parent: parent Event carries the child's inherited run.id")
		}
	})

	t.Run("ScopeTimingAndCorrelation", func(t *testing.T) {
		exp := &recordingExporter{}
		clock := newStepClock()
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: clock})

		ctx := context.Background()
		ctx, end := p.Scope(ctx, "phase.start", observability.String("phase", "implement"))
		// An Event emitted inside the scope shares the span correlation.
		p.Emit(ctx, observability.Event{Name: "inner", Severity: observability.SeverityInfo})
		clock.advance(750 * time.Millisecond)
		end(observability.Outcome{})
		flush(t, p)

		recs := exp.snapshot()
		span := findRecord(recs, "phase.start")
		inner := findRecord(recs, "inner")
		if span == nil {
			t.Fatal("no span Event emitted by Scope close")
		}
		// The span Event carries a duration computed from the injected Clock.
		if d := durField(span.Event); d != 750*time.Millisecond {
			t.Errorf("span duration = %v, want 750ms (from injected Clock)", d)
		}
		// Span correlation: trace/span IDs are non-empty and shared with the
		// enclosed Event.
		if span.TraceID == "" || span.SpanID == "" {
			t.Errorf("span Record missing TraceID/SpanID: trace=%q span=%q", span.TraceID, span.SpanID)
		}
		if inner != nil {
			if inner.TraceID != span.TraceID || inner.SpanID != span.SpanID {
				t.Errorf("enclosed Event correlation (%q/%q) != span (%q/%q)",
					inner.TraceID, inner.SpanID, span.TraceID, span.SpanID)
			}
		}
	})

	t.Run("SecretSafetyByType", func(t *testing.T) {
		exp := &recordingExporter{}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
		const canary = "s3cr3t-token-value"
		sec := canaryValuer{raw: canary, redacted: "secrets.Secret(REDACTED)"}

		ctx := context.Background()
		p.Emit(ctx, observability.Event{Name: "e", Severity: observability.SeverityInfo,
			Fields: []observability.Field{observability.Any("token", sec)}})
		p.Log(ctx, observability.SeverityInfo, "evidence", observability.Any("token", sec))
		flush(t, p)

		// The raw material never reaches any shipped Record.
		for _, r := range exp.snapshot() {
			for _, f := range r.Event.Fields {
				if containsCanary(f.Value, canary) {
					t.Errorf("Field %q leaked the canary onto a shipped Record", f.Key)
				}
			}
		}
	})

	t.Run("FlushIsSoleBlockingErrorCall", func(t *testing.T) {
		wantErr := stderrors.New("exporter wire down")
		exp := &recordingExporter{err: wantErr}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})

		// Emit returns no error even though the Exporter is failing.
		p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo})

		err := p.Flush(context.Background())
		if err == nil {
			t.Fatal("Flush did not surface the Exporter failure")
		}
		// The cause is reachable via %w (Unwrap / errors.Is).
		if !stderrors.Is(err, wantErr) {
			t.Errorf("Flush error does not wrap the Exporter cause: %v", err)
		}
	})

	t.Run("LedgerRidesTheStream", func(t *testing.T) {
		exp := &recordingExporter{}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
		ctx := context.Background()

		now := time.Unix(1700000000, 0).UTC()
		led := observability.Ledger{
			RunID: "run-9", PhaseID: "implement", Model: "claude", Harness: "claudecode",
			TokensIn: 1000, TokensOut: 500, CacheHits: 250, CostMicros: 9999,
			Retries: 1, WallTime: 5 * time.Second,
		}
		// Order: a phase Event, then the ledger Event — they must ship in order.
		p.Emit(ctx, observability.Event{Plane: observability.PlaneAgent, Name: "phase.start", Severity: observability.SeverityInfo})
		p.Emit(ctx, observability.LedgerEvent(now, led))
		flush(t, p)

		recs := exp.snapshot()
		ledRec := findRecord(recs, "cost.ledger")
		if ledRec == nil {
			t.Fatal("no cost.ledger Record shipped")
		}
		if ledRec.Event.Plane != observability.PlaneAgent {
			t.Errorf("cost.ledger Plane = %v, want PlaneAgent", ledRec.Event.Plane)
		}
		if ledRec.Event.Severity != observability.SeverityInfo {
			t.Errorf("cost.ledger Severity = %v, want SeverityInfo", ledRec.Event.Severity)
		}
		// Ordering: cost.ledger ships after phase.start.
		if idx(recs, "cost.ledger") < idx(recs, "phase.start") {
			t.Error("cost.ledger shipped before phase.start; ordering lost")
		}
	})

	t.Run("ZeroValueSafety", func(t *testing.T) {
		exp := &recordingExporter{}
		p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
		// A zero Event renders, never panics, never is rejected.
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("a zero Event panicked: %v", r)
			}
		}()
		p.Emit(context.Background(), observability.Event{})
		flush(t, p)
		recs := exp.snapshot()
		if len(recs) != 1 {
			t.Fatalf("zero Event produced %d Records, want 1 (rendered, not rejected)", len(recs))
		}
		// Zero Event is Debug on DefaultPlane.
		if recs[0].Event.Severity != observability.SeverityDebug {
			t.Errorf("zero Event Severity = %v, want SeverityDebug", recs[0].Event.Severity)
		}
		if recs[0].Event.Plane != observability.PlaneSelf {
			t.Errorf("zero Event Plane = %v, want DefaultPlane PlaneSelf", recs[0].Event.Plane)
		}
	})
}

// ── conformance helpers ──────────────────────────────────────────────────────

func mustNew(t *testing.T, newProvider func(observability.Config, observability.Deps) (observability.Provider, error), cfg observability.Config, deps observability.Deps) observability.Provider {
	t.Helper()
	p, err := newProvider(cfg, deps)
	if err != nil {
		t.Fatalf("New error: %v", err)
	}
	if p == nil {
		t.Fatal("New returned nil Provider")
	}
	return p
}

func flush(t *testing.T, p observability.Provider) {
	t.Helper()
	if err := p.Flush(context.Background()); err != nil {
		t.Fatalf("Flush error: %v", err)
	}
}

func recordNames(recs []observability.Record) []string {
	out := make([]string, len(recs))
	for i, r := range recs {
		out[i] = r.Event.Name
	}
	return out
}

func findRecord(recs []observability.Record, name string) *observability.Record {
	for i := range recs {
		if recs[i].Event.Name == name {
			return &recs[i]
		}
	}
	return nil
}

func idx(recs []observability.Record, name string) int {
	for i := range recs {
		if recs[i].Event.Name == name {
			return i
		}
	}
	return -1
}

func has(names []string, want string) bool {
	for _, n := range names {
		if n == want {
			return true
		}
	}
	return false
}

func fieldKeys(fields []observability.Field) []string {
	out := make([]string, len(fields))
	for i, f := range fields {
		out[i] = f.Key
	}
	return out
}

func hasFieldKey(fields []observability.Field, key string) bool {
	for _, f := range fields {
		if f.Key == key {
			return true
		}
	}
	return false
}

func durField(e observability.Event) time.Duration {
	for _, f := range e.Fields {
		if f.Key == "duration" {
			if d, ok := f.Value.TelemetryValue().(time.Duration); ok {
				return d
			}
		}
	}
	return -1
}
