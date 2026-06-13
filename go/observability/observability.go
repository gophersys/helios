// Package observability is the Eden universal structured-Event port (10 §4, P9):
// one OTel-aligned stream carries all three planes — (a) Eden's own telemetry,
// (b) agent telemetry (runs, transcripts, tokens, gates), (c) generated-system
// telemetry — secret-safe by construction. Components EMIT Events into the
// outbound Provider; adapters (oteladapter, slogadapter) carry them to a backend
// behind the Exporter seam. The library owns the Event vocabulary and the
// emission contract; it does NOT own the backend and does NOT track the OTel SDK
// shape (Event is the stable contract; OTel is one adapter).
//
// Module: github.com/gophersys/libs/go/observability  (go 1.26)
//
// Concurrency: a Provider is safe for concurrent use from many goroutines; Emit,
// With, Scope, and Log may be called concurrently. With/Scope return values that
// share the underlying Exporter but carry independent inherited Fields/span
// state. Flush is the sole blocking call and is called at shutdown / run
// boundaries, never on the hot path.
//
// Zero value: a zero Event is a Debug Event on the Config.DefaultPlane with no
// fields and a zero Time (the adapter stamps "now"); an adapter renders it, never
// rejects it. Zero Config.MinSeverity == SeverityDebug == emit everything
// (fail-open on visibility, never silently dark). The zero Provider is NOT usable
// — obtain one from New.
//
// Errors: only New and Flush return errors. New returns a *ConfigError
// (inspectable via errors.AsType). Flush wraps the Exporter's I/O cause with %w.
// Emit/With/Scope/Log NEVER return an error — telemetry failure must not enter
// business logic (a dropped Event can never fail a phase).
package observability

import (
	"context"
	"time"
)

// ── The constructor spine (10 §4) — PURE ────────────────────────────────────

// Config is the immutable, fully-resolved input (the configuration pattern):
// parsed at the edge and frozen. It holds NO ports and NO live handles.
// ServiceName/ServiceVersion/Environment/ResourceAttrs become the OTel Resource;
// Environment is stamped as deployment.environment.name — the Stable attribute,
// not the deprecated deployment.environment (10 §2). The library reads NO env;
// the stage value arrives only HERE, from the environment library at the
// composition root. Idiomatic Go type name, exempt from the HNS-1 slug rule.
type Config struct {
	ServiceName    string            // OTel service.name; required, validated by New
	ServiceVersion string            // OTel service.version
	Environment    string            // development|test|staging|production -> deployment.environment.name (10 §2)
	DefaultPlane   Plane             // plane stamped on Events emitted as PlaneUnset
	ResourceAttrs  map[string]string // extra static OTel resource attributes (no secrets)
	MinSeverity    Severity          // drop Events below this at Emit; zero == SeverityDebug == emit everything
}

// Deps is the injected record of ports (the hexagon). New consumes ports; it
// constructs none. logging is a CONSUMER of Provider (via Provider.Log), not a
// Dep here — it is subordinate, riding the stream, not wiring it. Idiomatic Go
// type name, exempt from the HNS-1 slug rule.
type Deps struct {
	Exporter Exporter // the outbound wire/stdout boundary; non-nil required
	Clock    Clock    // injected time source so New stays pure and Scope is deterministic
}

// Exporter is the single outbound boundary an adapter package implements
// (oteladapter -> OTLP, slogadapter -> stdout). The library owns batching,
// scoping, resource stamping, and severity filtering; the adapter owns ONLY the
// wire. Blocking I/O lives HERE, behind the Provider's non-blocking Emit, so the
// hot path never stalls on exporter I/O. Accept-interface seam.
type Exporter interface {
	// Export ships a batch of fully-formed, resource-stamped, already-redacted
	// Records. It may block; it is driven off the hot path by the internal buffer
	// and by Flush.
	Export(ctx context.Context, records []Record) error
}

// Record is the resource-stamped, correlation-stamped Event the Exporter ships.
// The library produces it; adapters translate it to OTLP or stdout. It is a plain
// value, safe to copy.
type Record struct {
	Event    Event
	Resource map[string]string // ServiceName, ServiceVersion, deployment.environment.name, ResourceAttrs
	TraceID  string            // "" when no active span
	SpanID   string            // "" when no active span
}

// Clock is the minimal injected time port (mirrors dependencies.Clock). It is the
// ONLY reason Scope can stamp duration without the library reading time.Now —
// keeping New pure (10 §4) and the fake deterministic.
type Clock interface{ Now() time.Time }

// New is the pure constructor spine: no I/O, no clock read, no env read. It
// validates Config (ServiceName required; returns *ConfigError otherwise),
// captures Deps, and returns the internal Provider impl (resource stamping +
// severity filtering + Field inheritance + span timing), concrete behind the
// Provider interface. The first Export happens only when the engine/composition
// root later calls Emit/Scope/Flush.
func New(configuration Config, dependencies Deps) (Provider, error) {
	if configuration.ServiceName == "" {
		return nil, &ConfigError{Field: "ServiceName", Message: "required"}
	}
	if dependencies.Exporter == nil {
		return nil, &ConfigError{Field: "Exporter", Message: "required (non-nil)"}
	}
	if dependencies.Clock == nil {
		return nil, &ConfigError{Field: "Clock", Message: "required (non-nil): Scope cannot stamp duration without a clock"}
	}

	resource := map[string]string{
		"service.name":                configuration.ServiceName,
		"service.version":             configuration.ServiceVersion,
		"deployment.environment.name": configuration.Environment,
	}
	for k, v := range configuration.ResourceAttrs {
		// ResourceAttrs never override the reserved OTel keys above.
		if _, reserved := resource[k]; reserved {
			continue
		}
		resource[k] = v
	}

	defaultPlane := configuration.DefaultPlane
	if defaultPlane == PlaneUnset {
		// A composition root that leaves DefaultPlane unset still lands Events on a
		// concrete plane (a) rather than the sentinel PlaneUnset.
		defaultPlane = PlaneSelf
	}

	return newProvider(
		resource,
		defaultPlane,
		configuration.MinSeverity,
		dependencies.Exporter,
		dependencies.Clock,
	), nil
}

// ConfigError reports an invalid Config (e.g. empty ServiceName, nil Exporter).
// Inspectable via errors.AsType[*ConfigError]; wraps any cause with %w.
type ConfigError struct {
	Field   string // the offending Config/Deps field
	Message string
	cause   error // optional wrapped cause; surfaced via Unwrap (%w)
}

// Error renders "<field>: <message>".
func (e *ConfigError) Error() string {
	return e.Field + ": " + e.Message
}

// Unwrap exposes the wrapped cause (nil when the error carries none), so a
// ConfigError participates in errors.Is / errors.AsType chains.
func (e *ConfigError) Unwrap() error { return e.cause }
