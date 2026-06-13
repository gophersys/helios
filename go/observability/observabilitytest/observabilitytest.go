// Package observabilitytest is the canonical public fake for the observability
// port (the testing pattern, 10 §4 / 08 §2). The conformance suite that ships
// alongside (Run) proves adapter ≡ fake substitutability against the same
// properties (08 §2). Kernel tests inject *Provider directly and assert that a
// phase emitted "phase.start" / "cost.ledger" / "gate.decision" with the right
// Plane/Fields — without an OTel backend.
package observabilitytest

import (
	"context"
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

// eventLog is the shared, mutex-guarded record of everything emitted across a
// fake Provider and every child it spawns via With/Scope, so Events() returns the
// whole tree's stream in emission order regardless of which child emitted it.
type eventLog struct {
	mu     sync.Mutex
	events []observability.Event
}

func (l *eventLog) append(e observability.Event) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.events = append(l.events, e)
}

func (l *eventLog) snapshot() []observability.Event {
	l.mu.Lock()
	defer l.mu.Unlock()
	out := make([]observability.Event, len(l.events))
	copy(out, l.events)
	return out
}

// Provider is an in-memory, inspectable, concurrency-safe observability.Provider.
// It records every Event (honoring With-inheritance, Scope timing, and Log) so
// tests exercise the real semantics, not a degenerate stub. The zero value is
// NOT usable; obtain one from New.
type Provider struct {
	log      *eventLog
	clock    func() time.Time
	inherit  []observability.Field // accumulated With-inherited fields (ahead of call-site fields)
	defPlane observability.Plane   // plane stamped on a PlaneUnset Event
}

// New returns a fake bound to a deterministic clock (defaults to a fixed instant
// if clock is nil), so Scope-duration assertions never flake. The fake defaults
// its DefaultPlane to PlaneSelf so an unstamped Event lands on plane (a)
// explicitly rather than on PlaneUnset.
func New(clock func() time.Time) *Provider {
	if clock == nil {
		fixed := time.Unix(0, 0).UTC()
		clock = func() time.Time { return fixed }
	}
	return &Provider{
		log:      &eventLog{},
		clock:    clock,
		defPlane: observability.PlaneSelf,
	}
}

// record finalizes an Event with this fake's inherited fields (ahead of the
// call-site fields, order-preserving) and the resolved plane, then appends it to
// the shared log. It never mutates the caller's Fields slice.
func (p *Provider) record(e observability.Event) {
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
	p.log.append(e)
}

// Emit records one Event on the fake stream.
func (p *Provider) Emit(ctx context.Context, e observability.Event) { p.record(e) }

// With returns a child Provider carrying inherited Fields, sharing the same
// underlying log/clock but with an independent inherited-field slice. The parent
// is unaffected.
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

// Scope opens a correlated span. The returned ctx is unchanged-shape (the fake
// tracks no trace IDs on Events); the close func stamps a duration from the bound
// clock plus the Outcome and emits the span Event under this Provider's inherited
// scope.
func (p *Provider) Scope(ctx context.Context, name string, fields ...observability.Field) (scoped context.Context, end func(observability.Outcome)) {
	start := p.clock()
	spanFields := append([]observability.Field(nil), fields...)
	end = func(outcome observability.Outcome) {
		elapsed := p.clock().Sub(start)
		all := append([]observability.Field(nil), spanFields...)
		all = append(all, observability.Dur("duration", elapsed))
		if outcome.Err != nil {
			all = append(all, observability.Err(outcome.Err), observability.Bool("ok", false))
		} else {
			all = append(all, observability.Bool("ok", true))
		}
		p.record(observability.Event{Severity: observability.SeverityInfo, Name: name, Fields: all})
	}
	return ctx, end
}

// Log emits an operator-facing leveled line as a Severity-N Event on the same
// stream — logging is a VIEW over this Provider.
func (p *Provider) Log(ctx context.Context, sev observability.Severity, message string, fields ...observability.Field) {
	f := append([]observability.Field{observability.String("message", message)}, fields...)
	p.record(observability.Event{Severity: sev, Name: "log", Fields: f})
}

// Flush is a no-op on the fake (nothing is buffered) and never errors.
func (p *Provider) Flush(ctx context.Context) error { return nil }

// Events returns a snapshot copy of everything emitted, in order (With-inherited
// Fields already merged), for assertion.
func (p *Provider) Events() []observability.Event { return p.log.snapshot() }

// Find returns the Events whose Name == name (e.g. "cost.ledger") for assertions.
func (p *Provider) Find(name string) []observability.Event {
	var out []observability.Event
	for _, e := range p.log.snapshot() {
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
	for _, e := range p.log.snapshot() {
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
