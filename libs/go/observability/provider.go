package observability

import "context"

// ── Provider: the outbound port the hexagon depends on ─────────────────────.

// Provider is the single port a consumer holds in its Deps (accept this
// interface; New returns the concrete impl). Exactly 5 methods — the negotiated
// ceiling (10 §9). Cross-cutting logic (resource stamping, severity filtering,
// Field inheritance, span timing) lives ONCE in the internal impl; an adapter
// implements only the Exporter seam.
type Provider interface {
	// Emit records one Event on the stream. Non-blocking and best-effort: an
	// adapter buffers or drops, it never blocks the caller's goroutine on I/O, and
	// it returns no error. ctx carries the active span (trace/span correlation)
	// and cancellation. An Event below Config.MinSeverity is filtered here.
	Emit(ctx context.Context, event Event)

	// With returns a child Provider carrying inherited Fields (request/run scope —
	// e.g. run.id). It allocates and inherits; it does not emit and does not open a
	// span. Cheap; use it for static scope a library stamps onto every Event.
	With(fields ...Field) Provider

	// Scope opens a correlated span for a unit of work (a phase, a model call). The
	// returned ctx carries the span; call the returned func when the unit completes
	// — it stamps duration (from the injected Clock) and outcome and emits the span
	// Event. Use it where duration/outcome matter; use With for plain inheritance.
	Scope(ctx context.Context, name string, fields ...Field) (context.Context, func(outcome Outcome))

	// Log emits an operator-facing leveled line as a SeverityN Event on the same
	// stream — logging (10 §4) is a VIEW over this Provider, not a parallel pipe.
	// This is the subordinate-Sink seam: logging depends on observability, never
	// the reverse, and one backend renders both leveled lines and structured Events.
	Log(ctx context.Context, sev Severity, message string, fields ...Field)

	// Flush drains buffered Events to the Exporter. It is the ONLY blocking method
	// and the ONLY one (besides New) that returns an error; honors ctx deadline and
	// is called at shutdown and at run/phase boundaries by the engine.
	Flush(ctx context.Context) error
}

// Outcome closes a Scope: success or a wrapped error, recorded on the span Event
// (never logged raw). Err == nil is success.
type Outcome struct {
	Err error // nil == success; wrapped via %w upstream, inspected via errors.AsType
}
