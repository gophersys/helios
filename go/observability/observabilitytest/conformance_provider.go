package observabilitytest

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/observability"
)

// newConformanceProvider builds an in-memory Provider that honors a full
// Config/Deps (DefaultPlane, MinSeverity, Resource stamping, Scope correlation)
// and ships resource-stamped Records to Deps.Exporter on Flush. It is the fake
// package's own Deps-aware double, so the SAME conformance suite (Run) that
// validates the real adapter also validates this fake — proving adapter ≡ fake
// substitutability (08 §2) from the fake side.
//
// It returns a *ConfigError on the same validation failures the real New rejects
// (empty ServiceName, nil Exporter, nil Clock), so the NewValidationErrors
// property holds for the fake too.
func newConformanceProvider(cfg observability.Config, deps observability.Deps) (observability.Provider, error) {
	if cfg.ServiceName == "" {
		return nil, &observability.ConfigError{Field: "ServiceName", Message: "required"}
	}
	if deps.Exporter == nil {
		return nil, &observability.ConfigError{Field: "Exporter", Message: "required (non-nil)"}
	}
	if deps.Clock == nil {
		return nil, &observability.ConfigError{Field: "Clock", Message: "required (non-nil)"}
	}
	resource := map[string]string{
		"service.name":                cfg.ServiceName,
		"service.version":             cfg.ServiceVersion,
		"deployment.environment.name": cfg.Environment,
	}
	for k, v := range cfg.ResourceAttrs {
		resource[k] = v
	}
	shared := &confState{
		exporter:    deps.Exporter,
		clock:       deps.Clock,
		minSeverity: cfg.MinSeverity,
		resource:    resource,
	}
	defPlane := cfg.DefaultPlane
	if defPlane == observability.PlaneUnset {
		defPlane = observability.PlaneSelf
	}
	return &confProvider{shared: shared, defPlane: defPlane}, nil
}

// confState is shared by a conformance Provider and all its With/Scope children:
// the buffer, the injected ports, and the static resource map.
type confState struct {
	mu          sync.Mutex
	exporter    observability.Exporter
	clock       observability.Clock
	minSeverity observability.Severity
	resource    map[string]string
	buffer      []observability.Record
	spans       uint64
}

func (s *confState) nextSpan() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.spans++
	return s.spans
}

// buffer appends a finished Record off the hot path (no exporter I/O here — that
// is quarantined to Flush, mirroring the real impl's non-blocking Emit).
func (s *confState) push(r observability.Record) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.buffer = append(s.buffer, r)
}

// confProvider is one node in the With/Scope tree: it carries inherited Fields and
// the active span correlation, sharing confState with its parent and children.
type confProvider struct {
	shared   *confState
	inherit  []observability.Field
	defPlane observability.Plane
	traceID  string
	spanID   string
}

type confCtxKey struct{}

type confSpan struct{ traceID, spanID string }

func (p *confProvider) finish(ctx context.Context, e observability.Event) {
	// Severity filtering at Emit.
	if e.Severity < p.shared.minSeverity {
		return
	}
	if e.Plane == observability.PlaneUnset {
		e.Plane = p.defPlane
	}
	if len(p.inherit) > 0 {
		merged := make([]observability.Field, 0, len(p.inherit)+len(e.Fields))
		merged = append(merged, p.inherit...)
		merged = append(merged, e.Fields...)
		e.Fields = merged
	}
	trace, span := p.traceID, p.spanID
	if s, ok := ctx.Value(confCtxKey{}).(confSpan); ok {
		trace, span = s.traceID, s.spanID
	}
	res := make(map[string]string, len(p.shared.resource))
	for k, v := range p.shared.resource {
		res[k] = v
	}
	p.shared.push(observability.Record{Event: e, Resource: res, TraceID: trace, SpanID: span})
}

func (p *confProvider) Emit(ctx context.Context, e observability.Event) { p.finish(ctx, e) }

func (p *confProvider) With(fields ...observability.Field) observability.Provider {
	child := *p
	child.inherit = make([]observability.Field, 0, len(p.inherit)+len(fields))
	child.inherit = append(child.inherit, p.inherit...)
	child.inherit = append(child.inherit, fields...)
	return &child
}

func (p *confProvider) Scope(ctx context.Context, name string, fields ...observability.Field) (context.Context, func(observability.Outcome)) {
	id := p.shared.nextSpan()
	trace := "trace-" + itoa(id)
	span := "span-" + itoa(id)

	child := *p
	child.traceID = trace
	child.spanID = span

	start := p.shared.clock.Now()
	spanFields := append([]observability.Field(nil), fields...)
	ctx = context.WithValue(ctx, confCtxKey{}, confSpan{traceID: trace, spanID: span})

	close := func(outcome observability.Outcome) {
		elapsed := p.shared.clock.Now().Sub(start)
		all := append([]observability.Field(nil), spanFields...)
		all = append(all, observability.Dur("duration", elapsed))
		if outcome.Err != nil {
			all = append(all, observability.Err(outcome.Err), observability.Bool("ok", false))
		} else {
			all = append(all, observability.Bool("ok", true))
		}
		child.finish(ctx, observability.Event{Severity: observability.SeverityInfo, Name: name, Fields: all})
	}
	return ctx, close
}

func (p *confProvider) Log(ctx context.Context, sev observability.Severity, message string, fields ...observability.Field) {
	f := append([]observability.Field{observability.String("message", message)}, fields...)
	p.finish(ctx, observability.Event{Severity: sev, Name: "log", Fields: f})
}

func (p *confProvider) Flush(ctx context.Context) error {
	p.shared.mu.Lock()
	batch := p.shared.buffer
	p.shared.buffer = nil
	p.shared.mu.Unlock()
	if len(batch) == 0 {
		return nil
	}
	if err := p.shared.exporter.Export(ctx, batch); err != nil {
		return &flushError{cause: err}
	}
	return nil
}

// flushError wraps the Exporter cause with %w (Unwrap), mirroring the real impl's
// Flush contract so the conformance FlushIsSoleBlockingErrorCall property holds.
type flushError struct{ cause error }

func (e *flushError) Error() string { return "observabilitytest: flush: " + e.cause.Error() }
func (e *flushError) Unwrap() error { return e.cause }
