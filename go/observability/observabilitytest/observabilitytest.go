// Package observabilitytest is the canonical public fake for the observability
// port (the testing pattern, 10 §4 / 08 §2). The conformance suite that ships
// alongside (Run) proves adapter ≡ fake substitutability against the same
// properties (08 §2). Kernel tests inject *Provider directly and assert that a
// phase emitted "phase.start" / "cost.ledger" / "gate.decision" with the right
// Plane/Fields — without an OTel backend.
package observabilitytest

import (
	"context"
	"strconv"
	"sync"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// Compile-time proof the fake implements the production Provider port and that
// FailingExporter implements the Exporter port.
var (
	_ observability.Provider = (*Provider)(nil)
	_ observability.Exporter = FailingExporter{}
)

// fakeState is the shared, mutex-guarded core every *Provider node (the root and
// each With/Scope child) references. It carries BOTH the in-memory event log (the
// kernel-injection inspection surface: Events/Find/Ledgers/AssertNoSecrets) AND —
// when the fake is built Exporter-backed from a Config/Deps — the resource map,
// severity policy, off-hot-path buffer, span counter, and Exporter that make the
// SAME public *Provider the subject the conformance suite (Run) drives. There is
// no separate conformance double: the fake the kernel injects is the fake proven
// substitutable (closing the fakes-drift-from-reality gap, 08 §2 / ADR-0017 §1b).
type fakeState struct {
	mu     sync.Mutex
	events []observability.Event // every Event, in emission order (Events/Find/Ledgers)

	// Exporter-backed fields — populated only when the fake is built from a
	// Config/Deps (newFakeFromDeps); zero/nil on a New(clock) kernel fake.
	exporter    observability.Exporter
	resource    map[string]string
	minSeverity observability.Severity
	buffer      []observability.Record // resource-stamped Records awaiting Flush
	spanN       uint64
}

// appendEvent records a finished Event into the in-memory log (always) and, when
// the fake is Exporter-backed, also buffers the resource-stamped, correlation-
// stamped Record off the hot path. No Exporter I/O happens here — that is
// quarantined to Flush, mirroring the real impl's non-blocking Emit.
func (s *fakeState) appendEvent(e observability.Event, traceID, spanID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.events = append(s.events, e)
	if s.exporter == nil {
		return // in-memory-only kernel fake: nothing to ship on Flush
	}
	res := make(map[string]string, len(s.resource))
	for k, v := range s.resource {
		res[k] = v
	}
	s.buffer = append(s.buffer, observability.Record{Event: e, Resource: res, TraceID: traceID, SpanID: spanID})
}

func (s *fakeState) snapshotEvents() []observability.Event {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]observability.Event, len(s.events))
	copy(out, s.events)
	return out
}

// drain atomically takes the buffered Records, leaving the buffer empty, so a
// concurrent Emit during Flush is never lost (it lands in the fresh buffer).
func (s *fakeState) drain() []observability.Record {
	s.mu.Lock()
	defer s.mu.Unlock()
	batch := s.buffer
	s.buffer = nil
	return batch
}

func (s *fakeState) nextSpan() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.spanN++
	return s.spanN
}

// Provider is an in-memory, inspectable, concurrency-safe observability.Provider.
// It records every Event (honoring With-inheritance, Scope timing, and Log) so
// tests exercise the real semantics, not a degenerate stub. The zero value is
// NOT usable; obtain one from New.
type Provider struct {
	state    *fakeState
	clock    func() time.Time
	inherit  []observability.Field // accumulated With-inherited fields (ahead of call-site fields)
	defPlane observability.Plane   // plane stamped on a PlaneUnset Event
	traceID  string                // active span trace ID ("" at the root)
	spanID   string                // active span span ID ("" at the root)
}

// New returns a fake bound to a deterministic clock (defaults to a fixed instant
// if clock is nil), so Scope-duration assertions never flake. The fake defaults
// its DefaultPlane to PlaneSelf so an unstamped Event lands on plane (a)
// explicitly rather than on PlaneUnset. This in-memory fake has no Exporter:
// Flush is a no-op and the recorded stream is read back via Events/Find/Ledgers
// — the shape kernel tests (engine, codingharness, testharness, evidence) inject.
func New(clock func() time.Time) *Provider {
	if clock == nil {
		fixed := time.Unix(0, 0).UTC()
		clock = func() time.Time { return fixed }
	}
	return &Provider{
		state:    &fakeState{},
		clock:    clock,
		defPlane: observability.PlaneSelf,
	}
}

// fakeSpanKey carries the active span correlation on the ctx so an Event emitted
// inside a Scope inherits that span's IDs into its buffered Record.
type fakeSpanKey struct{}

type fakeSpan struct{ traceID, spanID string }

// record finalizes an Event with this fake's inherited fields (ahead of the
// call-site fields, order-preserving), the resolved plane, severity filtering,
// and span correlation, then hands it to the shared state. It never mutates the
// caller's Fields slice.
func (p *Provider) record(ctx context.Context, e observability.Event) {
	if e.Severity < p.state.minSeverity {
		return // filtered at Emit; below MinSeverity (zero == emit everything)
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
	if e.Time.IsZero() {
		e.Time = p.clock()
	}
	trace, span := p.traceID, p.spanID
	if sv, ok := ctx.Value(fakeSpanKey{}).(fakeSpan); ok {
		trace, span = sv.traceID, sv.spanID
	}
	p.state.appendEvent(e, trace, span)
}

// Emit records one Event on the fake stream.
func (p *Provider) Emit(ctx context.Context, e observability.Event) { p.record(ctx, e) }

// With returns a child Provider carrying inherited Fields, sharing the same
// underlying state/clock but with an independent inherited-field slice. The
// parent is unaffected.
//
// It returns the observability.Provider port because this fake implements that
// interface and the frozen contract §2 declares With(...) Provider.
//
//nolint:ireturn // contract §2: With implements the Provider port; surface is frozen.
func (p *Provider) With(fields ...observability.Field) observability.Provider {
	child := *p
	child.inherit = make([]observability.Field, 0, len(p.inherit)+len(fields))
	child.inherit = append(child.inherit, p.inherit...)
	child.inherit = append(child.inherit, fields...)
	return &child
}

// Scope opens a correlated span. The returned ctx carries the span correlation so
// an Event emitted on it shares the span's TraceID/SpanID; the close func stamps a
// duration from the bound clock plus the Outcome and emits the span Event under
// this Provider's inherited scope.
func (p *Provider) Scope(ctx context.Context, name string, fields ...observability.Field) (scoped context.Context, end func(observability.Outcome)) {
	id := p.state.nextSpan()
	trace := "trace-" + strconv.FormatUint(id, 10)
	span := "span-" + strconv.FormatUint(id, 10)

	child := *p
	child.traceID = trace
	child.spanID = span

	start := p.clock()
	spanFields := append([]observability.Field(nil), fields...)
	scoped = context.WithValue(ctx, fakeSpanKey{}, fakeSpan{traceID: trace, spanID: span})

	end = func(outcome observability.Outcome) {
		elapsed := p.clock().Sub(start)
		all := append([]observability.Field(nil), spanFields...)
		all = append(all, observability.Dur("duration", elapsed))
		if outcome.Err != nil {
			all = append(all, observability.Err(outcome.Err), observability.Bool("ok", false))
		} else {
			all = append(all, observability.Bool("ok", true))
		}
		child.record(scoped, observability.Event{Severity: observability.SeverityInfo, Name: name, Fields: all})
	}
	return scoped, end
}

// Log emits an operator-facing leveled line as a Severity-N Event on the same
// stream — logging is a VIEW over this Provider.
func (p *Provider) Log(ctx context.Context, sev observability.Severity, message string, fields ...observability.Field) {
	f := append([]observability.Field{observability.String("message", message)}, fields...)
	p.record(ctx, observability.Event{Severity: sev, Name: "log", Fields: f})
}

// Flush drains the buffered Records to the bound Exporter and surfaces an
// Exporter failure wrapped via %w. On the in-memory kernel fake (built via New,
// no Exporter) it is a no-op and never errors; on the Exporter-backed conformance
// fake it mirrors the real impl's Flush contract exactly.
func (p *Provider) Flush(ctx context.Context) error {
	if p.state.exporter == nil {
		return nil
	}
	batch := p.state.drain()
	if len(batch) == 0 {
		return nil
	}
	if err := p.state.exporter.Export(ctx, batch); err != nil {
		return &flushError{cause: err}
	}
	return nil
}

// Events returns a snapshot copy of everything emitted, in order (With-inherited
// Fields already merged), for assertion.
func (p *Provider) Events() []observability.Event { return p.state.snapshotEvents() }

// Find returns the Events whose Name == name (e.g. "cost.ledger") for assertions.
func (p *Provider) Find(name string) []observability.Event {
	var out []observability.Event
	for _, e := range p.state.snapshotEvents() {
		if e.Name == name {
			out = append(out, e)
		}
	}
	return out
}

// Ledgers decodes the T6 "cost.ledger" Events back into typed Ledgers so a budget
// test asserts tokens/retries/cost directly.
func (p *Provider) Ledgers() []observability.Ledger {
	var out []observability.Ledger
	for _, e := range p.Find("cost.ledger") {
		out = append(out, decodeLedger(e))
	}
	return out
}

// AssertNoSecrets returns an error if any recorded Field's TelemetryValue()
// contains canary — the type-level leak guard, exercised by the conformance
// suite. A nil error means no Field rendered the canary.
func (p *Provider) AssertNoSecrets(canary string) error {
	if canary == "" {
		return nil
	}
	for _, e := range p.state.snapshotEvents() {
		for _, f := range e.Fields {
			if containsCanary(f.Value, canary) {
				return &leakError{Field: f.Key, Canary: canary}
			}
		}
	}
	return nil
}

// FailingExporter is an observability.Exporter that errors on Export, for testing
// the Flush error path (the only error path on the Provider besides New).
type FailingExporter struct{ Err error }

// Export always returns f.Err, so a Provider built on this Exporter surfaces the
// failure on Flush.
func (f FailingExporter) Export(context.Context, []observability.Record) error { return f.Err }
