package observabilitytest

import (
	"context"
	stderrors "errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// errExporterWireDown is the sentinel the Flush-error property uses to prove the
// Exporter failure is reachable through the Provider's Flush via %w. Declared as a
// package-level sentinel (not minted inline) so the suite matches it with
// errors.Is and stays clear of the no-dynamic-errors rule (err113).
var errExporterWireDown = stderrors.New("exporter wire down")

// providerFactory is the contract §4 conformance harness signature: a function
// that builds an observability.Provider from a Config/Deps. The real New and the
// public fake's newFakeFromDeps both satisfy it, so Run validates the real adapter
// and the fake consumers inject identically.
type providerFactory = func(observability.Config, observability.Deps) (observability.Provider, error)

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
			// %w via fmt.Errorf IS the wrap; wrapcheck fires only because the shared
			// config's custom ignore-sigs omits fmt.Errorf (same as impl.go Flush).
			//nolint:wrapcheck // %w via fmt.Errorf IS the wrap (stdlib-only leaf).
			return fmt.Errorf("recordingExporter: %w", ctx.Err())
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

// baseConfig is the shared valid Config the property helpers start from.
func baseConfig() observability.Config {
	return observability.Config{
		ServiceName:    "conformance-svc",
		ServiceVersion: "v1.2.3",
		Environment:    "test",
		DefaultPlane:   observability.PlaneSelf,
		ResourceAttrs:  map[string]string{"team": "kernel"},
	}
}

// RunFakeConformance runs the shared conformance suite (Run) against the PUBLIC
// fake (*Provider), built Exporter-backed from a Config/Deps via newFakeFromDeps.
// It is the fake side of the adapter≡fake proof (08 §2): the real adapter's test
// calls Run with observability.New, this calls Run with the same public *Provider
// kernel tests inject — both must pass identically. There is no private double;
// the subject the contract names (observabilitytest.Provider) is the subject
// proven substitutable (closing the fakes-drift gap, ADR-0017 §1b).
func RunFakeConformance(t *testing.T) {
	t.Helper()
	Run(t, newFakeFromDeps)
}

// Run drives any observability.Provider produced by newProvider through the
// substitutability properties (contract §4). The real adapter and
// observabilitytest.Provider must both pass identically. Each property lives in
// its own helper so this dispatcher stays flat and every property is named and
// independently runnable.
func Run(t *testing.T, newProvider providerFactory) {
	t.Helper()
	if newProvider == nil {
		t.Fatal("Run: newProvider must not be nil")
	}
	properties := []struct {
		name string
		run  func(*testing.T, providerFactory)
	}{
		{"PurityOfNew", confPurityOfNew},
		{"NewValidationErrors", confNewValidationErrors},
		{"EmitNonBlocking", confEmitNonBlocking},
		{"SeverityFiltering", confSeverityFiltering},
		{"SeverityZeroEmitsEverything", confSeverityZeroEmitsEverything},
		{"PlaneStamping", confPlaneStamping},
		{"ResourceStamping", confResourceStamping},
		{"WithInheritance", confWithInheritance},
		{"ScopeTimingAndCorrelation", confScopeTimingAndCorrelation},
		{"SecretSafetyByType", confSecretSafetyByType},
		{"FlushIsSoleBlockingErrorCall", confFlushIsSoleBlockingErrorCall},
		{"LedgerRidesTheStream", confLedgerRidesTheStream},
		{"ZeroValueSafety", confZeroValueSafety},
		{"ConcurrentUse", confConcurrentUse},
	}
	for _, prop := range properties {
		t.Run(prop.name, func(t *testing.T) {
			t.Parallel()
			prop.run(t, newProvider)
		})
	}
}

// confPurityOfNew: a panicking Clock/Exporter does not panic until first
// emit/flush — New touches no port.
func confPurityOfNew(t *testing.T, newProvider providerFactory) {
	t.Helper()
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
}

// confNewValidationErrors: empty ServiceName and nil Exporter are *ConfigError.
func confNewValidationErrors(t *testing.T, newProvider providerFactory) {
	t.Helper()
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

	_, err = newProvider(baseConfig(), observability.Deps{Exporter: nil, Clock: newStepClock()})
	if err == nil {
		t.Fatal("nil Exporter produced no error")
	}
	if !stderrors.As(err, &cfgErr) {
		t.Fatalf("nil Exporter error is not *ConfigError: %T", err)
	}
}

// confEmitNonBlocking: a slow Exporter must not stall the caller on
// Emit/With/Scope/Log.
func confEmitNonBlocking(t *testing.T, newProvider providerFactory) {
	t.Helper()
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
}

// confSeverityFiltering: an Event below MinSeverity is dropped at Emit.
func confSeverityFiltering(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	configuration := baseConfig()
	configuration.MinSeverity = observability.SeverityWarn
	p := mustNew(t, newProvider, configuration, observability.Deps{Exporter: exp, Clock: newStepClock()})
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
}

// confSeverityZeroEmitsEverything: zero MinSeverity (SeverityDebug) emits all.
func confSeverityZeroEmitsEverything(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
	ctx := context.Background()
	p.Emit(ctx, observability.Event{Name: "debug", Severity: observability.SeverityDebug})
	flush(t, p)
	if !has(recordNames(exp.snapshot()), "debug") {
		t.Error("zero MinSeverity dropped a Debug Event; it must emit everything")
	}
}

// confPlaneStamping: PlaneUnset inherits DefaultPlane; an explicit Plane is kept.
func confPlaneStamping(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	configuration := baseConfig()
	configuration.DefaultPlane = observability.PlaneSelf
	p := mustNew(t, newProvider, configuration, observability.Deps{Exporter: exp, Clock: newStepClock()})
	ctx := context.Background()

	p.Emit(ctx, observability.Event{Name: "unset", Severity: observability.SeverityInfo, Plane: observability.PlaneUnset})
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
}

// confResourceStamping: every shipped Record carries the resource attributes and
// not the deprecated deployment.environment key.
func confResourceStamping(t *testing.T, newProvider providerFactory) {
	t.Helper()
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
	if _, ok := r.Resource["deployment.environment"]; ok {
		t.Error("Record carries the deprecated deployment.environment key")
	}
}

// confWithInheritance: With-inherited Fields precede call-site Fields and the
// parent is unaffected.
func confWithInheritance(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
	ctx := context.Background()

	child := p.With(observability.String("run.id", "r-42"))
	child.Emit(ctx, observability.Event{
		Name:     "child",
		Severity: observability.SeverityInfo,
		Fields:   []observability.Field{observability.String("phase", "implement")},
	})
	p.Emit(ctx, observability.Event{Name: "parent", Severity: observability.SeverityInfo})
	flush(t, p)

	recs := exp.snapshot()
	childRec := findRecord(recs, "child")
	parentRec := findRecord(recs, "parent")
	if childRec == nil || parentRec == nil {
		t.Fatalf("missing records: %v", recordNames(recs))
	}
	if len(childRec.Event.Fields) < 2 {
		t.Fatalf("child Event missing inherited fields: %#v", fieldKeys(childRec.Event.Fields))
	}
	if childRec.Event.Fields[0].Key != "run.id" {
		t.Errorf("inherited field is not first: %v", fieldKeys(childRec.Event.Fields))
	}
	if childRec.Event.Fields[len(childRec.Event.Fields)-1].Key != "phase" {
		t.Errorf("call-site field is not last: %v", fieldKeys(childRec.Event.Fields))
	}
	if hasFieldKey(parentRec.Event.Fields, "run.id") {
		t.Error("With mutated the parent: parent Event carries the child's inherited run.id")
	}
}

// confScopeTimingAndCorrelation: Scope stamps a duration from the injected Clock
// and the span Event shares TraceID/SpanID with the enclosed Event.
func confScopeTimingAndCorrelation(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	clock := newStepClock()
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: clock})

	ctx := context.Background()
	ctx, end := p.Scope(ctx, "phase.start", observability.String("phase", "implement"))
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
	if d := durField(span.Event); d != 750*time.Millisecond {
		t.Errorf("span duration = %v, want 750ms (from injected Clock)", d)
	}
	if span.TraceID == "" || span.SpanID == "" {
		t.Errorf("span Record missing TraceID/SpanID: trace=%q span=%q", span.TraceID, span.SpanID)
	}
	if inner != nil && (inner.TraceID != span.TraceID || inner.SpanID != span.SpanID) {
		t.Errorf("enclosed Event correlation (%q/%q) != span (%q/%q)",
			inner.TraceID, inner.SpanID, span.TraceID, span.SpanID)
	}
}

// confSecretSafetyByType: a redacting Valuer never renders its raw material onto a
// shipped Record, through Emit and Log alike.
func confSecretSafetyByType(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
	const canary = "s3cr3t-token-value"
	sec := canaryValuer{raw: canary, redacted: "secrets.Secret(REDACTED)"}

	ctx := context.Background()
	p.Emit(ctx, observability.Event{
		Name:     "e",
		Severity: observability.SeverityInfo,
		Fields:   []observability.Field{observability.Any("token", sec)},
	})
	p.Log(ctx, observability.SeverityInfo, "evidence", observability.Any("token", sec))
	flush(t, p)

	for _, r := range exp.snapshot() {
		for _, f := range r.Event.Fields {
			if containsCanary(f.Value, canary) {
				t.Errorf("Field %q leaked the canary onto a shipped Record", f.Key)
			}
		}
	}
}

// confFlushIsSoleBlockingErrorCall: Emit never errors even behind a failing
// Exporter; Flush surfaces the failure wrapped via %w.
func confFlushIsSoleBlockingErrorCall(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{err: errExporterWireDown}
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})

	p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo})

	err := p.Flush(context.Background())
	if err == nil {
		t.Fatal("Flush did not surface the Exporter failure")
	}
	if !stderrors.Is(err, errExporterWireDown) {
		t.Errorf("Flush error does not wrap the Exporter cause: %v", err)
	}
}

// confLedgerRidesTheStream: the T6 cost.ledger Event ships on PlaneAgent at
// SeverityInfo, ordered after the phase Event it follows.
func confLedgerRidesTheStream(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
	ctx := context.Background()

	now := time.Unix(1700000000, 0).UTC()
	led := observability.Ledger{
		RunID: "run-9", PhaseID: "implement", Model: "claude", Harness: "claudecode",
		TokensIn: 1000, TokensOut: 500, CacheHits: 250, CostMicros: 9999,
		Retries: 1, WallTime: 5 * time.Second,
	}
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
	if idx(recs, "cost.ledger") < idx(recs, "phase.start") {
		t.Error("cost.ledger shipped before phase.start; ordering lost")
	}
}

// confZeroValueSafety: a zero Event renders as a Debug Event on DefaultPlane,
// never panics, and is never rejected.
func confZeroValueSafety(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})
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
	if recs[0].Event.Severity != observability.SeverityDebug {
		t.Errorf("zero Event Severity = %v, want SeverityDebug", recs[0].Event.Severity)
	}
	if recs[0].Event.Plane != observability.PlaneSelf {
		t.Errorf("zero Event Plane = %v, want DefaultPlane PlaneSelf", recs[0].Event.Plane)
	}
}

// confConcurrentUse: the package doc / contract §2 Concurrency clause promises a
// Provider is safe for concurrent use from many goroutines — Emit, With, Scope,
// and Log may be called concurrently. This property fans all four across N
// goroutines on ONE Provider (under `go test -race`) and asserts that after Flush
// every emitted Event landed exactly once — no Record lost to a data race and none
// duplicated. It is the only property exercising the load-bearing telemetry path's
// goroutine-safety guarantee, and it runs against BOTH the real adapter and the
// fake (08 §2), so a locking bug in either is caught here rather than slipping past
// a single-goroutine suite.
func confConcurrentUse(t *testing.T, newProvider providerFactory) {
	t.Helper()
	exp := &recordingExporter{}
	// A concurrency-safe clock keeps Scope's duration stamp race-free; the property
	// under test is the Provider's own locking, not the clock's.
	p := mustNew(t, newProvider, baseConfig(), observability.Deps{Exporter: exp, Clock: newStepClock()})

	const (
		workers          = 64
		emitsPerWorker   = 8 // plain Emit
		logsPerWorker    = 4 // Log (one Event each)
		withEmitsPerWkr  = 4 // Emit through a With child
		scopesPerWorker  = 2 // Scope open+close (one span Event each)
		perWorkerRecords = emitsPerWorker + logsPerWorker + withEmitsPerWkr + scopesPerWorker
	)
	wantRecords := workers * perWorkerRecords

	var wg sync.WaitGroup
	wg.Add(workers)
	for w := range workers {
		go func(worker int) {
			defer wg.Done()
			ctx := context.Background()
			tag := observability.Int64("worker", int64(worker))
			for i := range emitsPerWorker {
				p.Emit(ctx, observability.Event{
					Name: "emit", Severity: observability.SeverityInfo,
					Fields: []observability.Field{tag, observability.Int64("i", int64(i))},
				})
			}
			for range logsPerWorker {
				p.Log(ctx, observability.SeverityInfo, "log", tag)
			}
			child := p.With(tag)
			for range withEmitsPerWkr {
				child.Emit(ctx, observability.Event{Name: "with.emit", Severity: observability.SeverityInfo})
			}
			for range scopesPerWorker {
				_, end := child.Scope(ctx, "span", tag)
				end(observability.Outcome{})
			}
		}(w)
	}
	wg.Wait()

	flush(t, p)

	recs := exp.snapshot()
	if len(recs) != wantRecords {
		// A lost Record => a race dropped an append; a duplicated Record => double
		// buffering. Either breaks the no-lost/no-duplicated guarantee.
		t.Fatalf("after concurrent use Flush shipped %d Records, want %d (lost or duplicated under concurrency)", len(recs), wantRecords)
	}

	// Every (worker, name) contribution must be present the exact expected number of
	// times — proves no Event was silently dropped AND none double-counted.
	counts := map[string]int{}
	for _, r := range recs {
		counts[r.Event.Name]++
	}
	wantByName := map[string]int{
		"emit":      workers * emitsPerWorker,
		"log":       workers * logsPerWorker,
		"with.emit": workers * withEmitsPerWkr,
		"span":      workers * scopesPerWorker,
	}
	for name, want := range wantByName {
		if got := counts[name]; got != want {
			t.Errorf("Record %q count = %d, want %d (concurrency lost or duplicated Events of this kind)", name, got, want)
		}
	}
}

// ── conformance helpers ─────────────────────────────────────────────────────.

// mustNew builds a Provider through the factory and fails the test on error or a
// nil result. It returns the observability.Provider port because the contract §4
// harness factory does; the suite exercises the port, never a concrete type.
//
//nolint:ireturn // contract §4 conformance harness yields the Provider port.
func mustNew(t *testing.T, newProvider providerFactory, configuration observability.Config, dependencies observability.Deps) observability.Provider {
	t.Helper()
	p, err := newProvider(configuration, dependencies)
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
