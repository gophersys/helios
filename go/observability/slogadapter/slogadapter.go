// Package slogadapter is the collector-less stdlib-slog Exporter for the
// observability library (10 §6.1): it carries fully-formed, resource-stamped,
// already-redacted Records to a *slog.Logger — stdout/stderr by default — with no
// external dependency and no OTLP collector. It is the real lower-seam adapter the
// composition root binds locally (oteladapter is bound in staging/production); the
// library owns batching, scoping, resource stamping, and severity filtering, so
// this adapter owns ONLY the wire (the Exporter seam, contract §2 / rationale 2).
//
// Module: github.com/gophersys/libs/go/observability/slogadapter (go 1.26)
//
// Substitutability: New returns an observability.Exporter that the conformance
// suite (observabilitytest.Run) drives exactly as it drives the in-memory fake, so
// the Exporter seam has one REAL, conformance-tested adapter (ADR-0017 §1b / §4 —
// no mock-only coverage of the real-substrate feature).
package slogadapter

import (
	"context"
	"io"
	"log/slog"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// Compile-time proof the adapter implements the outbound Exporter port.
var _ observability.Exporter = (*Exporter)(nil)

// Exporter ships each observability.Record as one slog Record on the bound
// *slog.Logger. It holds no mutable state of its own — slog.Handler owns the
// write synchronization — so it is safe for concurrent Export.
type Exporter struct {
	logger *slog.Logger
}

// New returns a collector-less Exporter writing JSON lines to w (typically
// os.Stdout at the composition root). A nil w is treated as io.Discard so a
// mis-wired root drops telemetry rather than panicking — telemetry failure must
// never enter business logic (contract §2 Errors).
func New(w io.Writer) *Exporter {
	if w == nil {
		w = io.Discard
	}
	return &Exporter{logger: slog.New(slog.NewJSONHandler(w, &slog.HandlerOptions{
		// The library already filtered below Config.MinSeverity at Emit; the adapter
		// must not re-drop, so it admits every level it is handed.
		Level: slog.LevelDebug,
	}))}
}

// NewWithLogger returns an Exporter that ships onto an existing *slog.Logger, for
// a root that already owns a configured handler. A nil logger falls back to the
// default text logger so Export never nil-derefs.
func NewWithLogger(logger *slog.Logger) *Exporter {
	if logger == nil {
		logger = slog.Default()
	}
	return &Exporter{logger: logger}
}

// Export ships a batch of resource-stamped, already-redacted Records. It is driven
// off the hot path by the library's buffer and by Flush; it honors ctx so a
// shutdown deadline unwinds the write loop. It returns no error in normal
// operation — a *slog.Logger does not surface a per-record write error — but
// respects ctx cancellation, the one failure a batch write can observe here.
func (e *Exporter) Export(ctx context.Context, records []observability.Record) error {
	for i := range records {
		if err := ctx.Err(); err != nil {
			//nolint:wrapcheck // %w via fmt is unavailable in this stdlib-only leaf; ctx.Err is already typed and inspectable via errors.Is.
			return err
		}
		e.ship(ctx, &records[i])
	}
	return nil
}

// ship renders one Record as a single slog line: the leveled message, then the
// resource attributes, the trace/span correlation, the P9 plane, and every Event
// Field carried as its already-redacted TelemetryValue projection.
func (e *Exporter) ship(ctx context.Context, r *observability.Record) {
	attrs := make([]slog.Attr, 0, len(r.Resource)+len(r.Event.Fields)+4)

	attrs = append(
		attrs,
		slog.String("event.name", r.Event.Name),
		slog.String("plane", planeString(r.Event.Plane)),
	)
	if r.TraceID != "" {
		attrs = append(attrs, slog.String("trace.id", r.TraceID))
	}
	if r.SpanID != "" {
		attrs = append(attrs, slog.String("span.id", r.SpanID))
	}
	for k, v := range r.Resource {
		attrs = append(attrs, slog.String(k, v))
	}
	for _, f := range r.Event.Fields {
		attrs = append(attrs, fieldAttr(f))
	}

	// The Event carries the emission time when set; zero means "stamp now", which
	// the handler does. slog.Logger.LogAttrs takes the message as the leveled line;
	// the Name is also carried as event.name for low-cardinality querying.
	e.logger.LogAttrs(ctx, slogLevel(r.Event.Severity), r.Event.Name, attrs...)
}

// fieldAttr projects one observability.Field onto a typed slog.Attr via its
// already-redacted TelemetryValue — never any raw material. A nil Valuer (which
// the Any constructor now prevents, but a raw Field literal could still carry)
// renders as an empty value rather than nil-derefing.
func fieldAttr(f observability.Field) slog.Attr {
	if f.Value == nil {
		return slog.String(f.Key, "")
	}
	switch v := f.Value.TelemetryValue().(type) {
	case string:
		return slog.String(f.Key, v)
	case int64:
		return slog.Int64(f.Key, v)
	case float64:
		return slog.Float64(f.Key, v)
	case bool:
		return slog.Bool(f.Key, v)
	case time.Duration:
		return slog.Duration(f.Key, v)
	case time.Time:
		return slog.Time(f.Key, v)
	default:
		return slog.Any(f.Key, v)
	}
}

// slogLevel maps the observability Severity onto a slog.Level. The mapping is the
// adapter's job (the library owns the Severity enum; the wire owns the rendering),
// mirroring how oteladapter maps Severity onto OTel SeverityNumber.
func slogLevel(s observability.Severity) slog.Level {
	switch s {
	case observability.SeverityDebug:
		return slog.LevelDebug
	case observability.SeverityInfo:
		return slog.LevelInfo
	case observability.SeverityWarn:
		return slog.LevelWarn
	case observability.SeverityError:
		return slog.LevelError
	default:
		// An unknown future Severity renders at Info rather than being dropped —
		// fail-open on visibility (contract §2 Zero value), never silently dark.
		return slog.LevelInfo
	}
}

// planeString renders the P9 plane as a stable, low-cardinality string so a
// collector-less stdout stream can still be partitioned by plane (a)/(b)/(c).
func planeString(p observability.Plane) string {
	switch p {
	case observability.PlaneUnset:
		return "unset"
	case observability.PlaneSelf:
		return "self"
	case observability.PlaneAgent:
		return "agent"
	case observability.PlaneGenerated:
		return "generated"
	default:
		return "unknown"
	}
}
