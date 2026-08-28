// Package otelobserver is the agentruntime.Observer adapter over the frozen observability.Provider —
// the ONLY place agentruntime depends on observability (the consumer-defined Observer port keeps the
// agentruntime root free of an observability import; this adapter binds them at the composition
// root). It bridges the sidecar's four telemetry needs onto the Provider:
//
//   - Logf  → Provider.Log at SeverityInfo (an operator-facing lifecycle line).
//   - Flush → Provider.Flush (the OTel-flush step of the shutdown state machine).
//   - Inject/Extract → the W3C trace-context carrier transform so OTel context rides every bus
//     message. The Provider's Scope already stamps trace/span ids into ctx; Inject reads the active
//     ids into an OTelContext map and Extract re-parents a ctx to a carried trace — a pure,
//     fakeable propagation seam that needs no real OTLP collector to test.
//
// Module boundary: a SUB-package of agentruntime (same module), citing the agentruntime port types,
// never redefining them (one concept, one home).
package otelobserver

import (
	"context"
	"fmt"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/observability"
)

// traceKeys are the W3C trace-context carrier keys the adapter injects/extracts. Keeping the carrier
// to the standard `traceparent`/`tracestate` pair makes an Eden message interoperate with any
// W3C-compliant collector that later consumes the bus.
const (
	keyTraceParent = "traceparent"
	keyTraceState  = "tracestate"
)

// carrierContextKey is the private context key under which Extract stores a carried trace so a
// downstream Inject round-trips it (the in-process propagation the sidecar needs between a consumed
// control message and the spans its handler emits).
type carrierContextKey struct{}

// Adapter is the concrete agentruntime.Observer over an observability.Provider. Construct via New; it
// is the value the composition root wires into agentruntime.Deps.Observer.
type Adapter struct {
	provider observability.Provider
}

// New constructs the adapter over a Provider. PURE: it stores the port and reads nothing. A nil
// Provider yields an adapter whose methods are safe no-ops on the telemetry side (the sidecar still
// runs without telemetry), but the composition root SHOULD wire a real Provider — agentruntime.New
// requires a non-nil Observer, so a nil here is a wiring smell the caller controls.
func New(provider observability.Provider) *Adapter {
	return &Adapter{provider: provider}
}

// Logf records one operator-facing lifecycle line at SeverityInfo. It never blocks the run loop (the
// Provider's Emit/Log is non-blocking and best-effort) and carries no secret.
func (a *Adapter) Logf(ctx context.Context, format string, args ...any) {
	if a.provider == nil {
		return
	}
	a.provider.Log(ctx, observability.SeverityInfo, fmt.Sprintf(format, args...))
}

// Inject reads the active trace context from ctx into a fresh OTelContext carrier. It draws from the
// carrier Extract stored (the in-process propagation chain) so a consumed→handled→published hop
// preserves the orchestrator's trace. A ctx with no carrier yields an empty (un-traced) map.
func (a *Adapter) Inject(ctx context.Context) agentruntime.OTelContext {
	if carried, ok := ctx.Value(carrierContextKey{}).(agentruntime.OTelContext); ok && len(carried) > 0 {
		out := make(agentruntime.OTelContext, len(carried))
		for key, value := range carried {
			out[key] = value
		}
		return out
	}
	return agentruntime.OTelContext{}
}

// Extract re-parents ctx to the trace carried on a consumed bus message, so the verb handler's
// telemetry is one edge under the publisher's span. The carrier is stored under the private key so a
// later Inject round-trips it. An empty carrier returns ctx unchanged.
func (a *Adapter) Extract(ctx context.Context, carrier agentruntime.OTelContext) context.Context {
	if len(carrier) == 0 {
		return ctx
	}
	copied := make(agentruntime.OTelContext, len(carrier))
	for key, value := range carrier {
		if key == keyTraceParent || key == keyTraceState {
			copied[key] = value
		}
	}
	if len(copied) == 0 {
		return ctx
	}
	return context.WithValue(ctx, carrierContextKey{}, copied)
}

// Flush drains buffered telemetry to the exporter (the shutdown OTel-flush). It honors ctx and
// returns the drain error.
func (a *Adapter) Flush(ctx context.Context) error {
	if a.provider == nil {
		return nil
	}
	if err := a.provider.Flush(ctx); err != nil {
		return err //nolint:wrapcheck // the observability.Provider.Flush error is already an Eden-model error; re-wrapping would double the chain.
	}
	return nil
}

// compile-time assertion: *Adapter is an agentruntime.Observer.
var _ agentruntime.Observer = (*Adapter)(nil)
