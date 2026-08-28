package observability

import (
	"context"
	"fmt"
	"strconv"
	"sync"
)

// state is the shared, mutex-guarded core every provider node (the root and each
// With/Scope child) references: the static resource map, the filtering/stamping
// policy, the injected ports, the off-hot-path buffer, and the span-ID counter.
// Cross-cutting logic (resource stamping, severity filtering, Field inheritance,
// span timing) lives ONCE here — an adapter only implements the Exporter seam.
type state struct {
	resource     map[string]string
	defaultPlane Plane
	minSeverity  Severity
	exporter     Exporter
	clock        Clock

	mu     sync.Mutex
	buffer []Record
	spanN  uint64
}

// push appends a finished Record to the buffer. It performs NO exporter I/O — the
// blocking wire call is quarantined to Flush — so Emit stays non-blocking even
// behind a slow Exporter. The Record is taken by pointer (it is a heavy value) and
// copied into the buffer under the lock.
func (s *state) push(r *Record) {
	s.mu.Lock()
	s.buffer = append(s.buffer, *r)
	s.mu.Unlock()
}

// nextSpan mints a monotonically increasing span ordinal for trace/span IDs.
func (s *state) nextSpan() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.spanN++
	return s.spanN
}

// drain atomically takes the buffered Records, leaving the buffer empty, so a
// concurrent Emit during Flush is never lost (it lands in the fresh buffer).
func (s *state) drain() []Record {
	s.mu.Lock()
	defer s.mu.Unlock()
	batch := s.buffer
	s.buffer = nil
	return batch
}

// provider is the internal Provider impl: one node in the With/Scope tree,
// carrying inherited Fields and an active span correlation, sharing *state with
// its parent and children. It is the concrete returned behind the Provider
// interface (accept-interface, return-concrete — 10 §9).
type provider struct {
	state   *state
	inherit []Field // accumulated With-inherited fields, ahead of call-site fields
	traceID string  // active span trace ID ("" at the root)
	spanID  string  // active span span ID ("" at the root)
}

// newProvider builds the root provider node from a fully-validated policy +
// ports. It allocates the shared *state (which carries a mutex, so it is never
// copied by value).
func newProvider(resource map[string]string, defaultPlane Plane, minSeverity Severity, exporter Exporter, clock Clock) *provider {
	return &provider{state: &state{
		resource:     resource,
		defaultPlane: defaultPlane,
		minSeverity:  minSeverity,
		exporter:     exporter,
		clock:        clock,
	}}
}

// spanKey is the unexported context key carrying the active span correlation, so
// an Event emitted on a Scope's ctx picks up the same TraceID/SpanID into its
// Record.
type spanKey struct{}

type spanValue struct{ traceID, spanID string }

// emit is the single internal sink: it applies severity filtering, plane
// stamping, Field inheritance, resource stamping, and span correlation, then
// buffers the Record. It never blocks on the Exporter.
func (p *provider) emit(ctx context.Context, e Event) {
	if e.Severity < p.state.minSeverity {
		return // filtered at Emit; below MinSeverity
	}
	if e.Plane == PlaneUnset {
		e.Plane = p.state.defaultPlane
	}
	if len(p.inherit) > 0 {
		// Inherited Fields precede call-site Fields, order-preserving, without
		// mutating the caller's slice.
		merged := make([]Field, 0, len(p.inherit)+len(e.Fields))
		merged = append(merged, p.inherit...)
		merged = append(merged, e.Fields...)
		e.Fields = merged
	}

	trace, span := p.traceID, p.spanID
	if sv, ok := ctx.Value(spanKey{}).(spanValue); ok {
		// A span on ctx (from Scope) wins over this node's static correlation, so
		// an Event emitted inside a Scope shares that span's IDs.
		trace, span = sv.traceID, sv.spanID
	}

	// The resource map is SHARED BY REFERENCE on the Record (read-only by contract —
	// see Record.Resource): it is built once in New and never mutated after, so the
	// hot path stamps the pointer rather than deep-copying the map per Emit. Dropping
	// the per-event allocation keeps Emit off the heap on the system's hottest path.
	p.state.push(&Record{Event: e, Resource: p.state.resource, TraceID: trace, SpanID: span})
}

// Emit records one Event on the stream. Non-blocking, best-effort, no error.
func (p *provider) Emit(ctx context.Context, event Event) { p.emit(ctx, event) }

// With returns a child Provider carrying inherited Fields. It allocates an
// independent inherited-field slice and shares *state; the parent is unaffected.
//
// The frozen contract (contracts/observability.md §2) declares Provider.With(...)
// Provider: this method implements the port interface, so it must return the
// Provider type (a child node is itself a *provider behind it). The ireturn
// "return concrete" rule is declined because the surface is frozen.
//
//nolint:ireturn // contract §2: With implements the Provider port; surface is frozen.
func (p *provider) With(fields ...Field) Provider {
	child := *p
	child.inherit = make([]Field, 0, len(p.inherit)+len(fields))
	child.inherit = append(child.inherit, p.inherit...)
	child.inherit = append(child.inherit, fields...)
	return &child
}

// Scope opens a correlated span. The returned ctx carries the span correlation;
// the close func stamps a duration computed from the injected Clock and the
// Outcome, then emits the span Event. The span Event and Events emitted on the
// returned ctx share TraceID/SpanID.
func (p *provider) Scope(ctx context.Context, name string, fields ...Field) (scoped context.Context, end func(Outcome)) {
	id := p.state.nextSpan()
	trace := "trace-" + strconv.FormatUint(id, 10)
	span := "span-" + strconv.FormatUint(id, 10)

	child := *p
	child.traceID = trace
	child.spanID = span

	start := p.state.clock.Now()
	spanFields := append([]Field(nil), fields...)
	scoped = context.WithValue(ctx, spanKey{}, spanValue{traceID: trace, spanID: span})

	end = func(outcome Outcome) {
		elapsed := child.state.clock.Now().Sub(start)
		all := append([]Field(nil), spanFields...)
		all = append(all, Dur("duration", elapsed))
		if outcome.Err != nil {
			all = append(all, Err(outcome.Err), Bool("ok", false))
		} else {
			all = append(all, Bool("ok", true))
		}
		child.emit(scoped, Event{Severity: SeverityInfo, Name: name, Fields: all})
	}
	return scoped, end
}

// Log emits an operator-facing leveled line as a Severity-N Event on the same
// stream — logging is a VIEW over this Provider, not a parallel pipe.
func (p *provider) Log(ctx context.Context, sev Severity, message string, fields ...Field) {
	f := make([]Field, 0, len(fields)+1)
	f = append(f, String("message", message))
	f = append(f, fields...)
	p.emit(ctx, Event{Severity: sev, Name: "log", Fields: f})
}

// Flush drains the buffered Records and ships them through the Exporter. It is
// the sole blocking method and the sole Provider error path: it wraps the
// Exporter's I/O cause with %w (reachable via errors.Is / errors.AsType) and
// honors ctx.
func (p *provider) Flush(ctx context.Context) error {
	batch := p.state.drain()
	if len(batch) == 0 {
		return nil
	}
	if err := p.state.exporter.Export(ctx, batch); err != nil {
		// fmt.Errorf with %w is the correct, contract-mandated wrap (contract §2:
		// "Flush wraps the Exporter's I/O cause with %w"). observability is a
		// stdlib-only leaf (depguard) and cannot import the Eden errors model, so
		// %w is the wrapping boundary here and the cause stays reachable via
		// errors.Is/Unwrap. wrapcheck fires only because the shared config's custom
		// ignore-sigs omits fmt.Errorf — there is no missing wrap to add.
		//nolint:wrapcheck // %w via fmt.Errorf IS the wrap (contract §2 leaf lib).
		return fmt.Errorf("observability: flush: %w", err)
	}
	return nil
}
