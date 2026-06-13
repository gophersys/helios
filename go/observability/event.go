package observability

import "time"

// ── Event: the one structured record every plane emits ──────────────────────

// Plane is the P9 telemetry plane an Event belongs to. It is STAMPED, never
// inferred, so a single backend partitions Eden's own signal from agent and
// generated-system signal without parsing payloads. Zero value is PlaneUnset so
// an unstamped Event visibly inherits Config.DefaultPlane rather than silently
// landing on plane (a).
type Plane uint8

const (
	PlaneUnset     Plane = iota // zero: inherit Config.DefaultPlane at Emit
	PlaneSelf                   // (a) Eden's own runtime
	PlaneAgent                  // (b) agent runs, transcripts, tokens, gate/validation events
	PlaneGenerated              // (c) the system Eden builds for the user
)

// Severity is the operator-facing level carried on an Event. The subordinate
// logging Sink (10 §4) rides this same stream rather than opening a second
// channel; logging is exactly the projection of Events at/above a level. Values
// map mechanically onto OTel SeverityNumber ranges in oteladapter. The zero
// value is SeverityDebug so an unstamped Event is never silently dropped.
type Severity uint8

const (
	SeverityDebug Severity = iota
	SeverityInfo
	SeverityWarn
	SeverityError
)

// Event is the single, immutable unit of the stream — a plain value: copyable and
// safe to construct from its zero value. Never mutate a delivered Event. Time is
// supplied by the injected Clock at the emit site (Scope) or left zero for the
// adapter to stamp; the library itself reads no clock (spine purity, 10 §4).
//
// Event carries NO secrets by construction: Fields holds only Valuer, whose
// redacted projection is the only thing that reaches the wire (see Field). The
// Name is the stable, low-cardinality OTel span/log name.
type Event struct {
	Time     time.Time // emission time; zero == "adapter stamps now"
	Plane    Plane     // P9 plane; PlaneUnset inherits Config.DefaultPlane at Emit
	Severity Severity
	Name     string  // stable, dotted, low-cardinality: "model.call", "phase.start", "cost.ledger", "gate.decision"
	Fields   []Field // structured attributes; order-preserving, append-only at the call site
}

// Field is one structured, redaction-safe attribute. Keys are OTel-attribute-
// shaped (dotted.lower.case). Value is a Valuer, never a bare any, so a
// secret-bearing type can enter ONLY as its already-redacted projection — the
// type system, not a runtime filter list, keeps secrets off telemetry (P9, 07 §2).
type Field struct {
	Key   string
	Value Valuer
}

// Valuer yields a telemetry-safe representation of an attribute. The secrets
// library's Secret satisfies it by returning secrets.Redacted; primitives are
// wrapped by the String/Int64/Float64/Bool/Dur/Err constructors below. This is
// the ONLY door onto the stream for a field value — there is no any-typed field
// and no String(key, secret.Reveal()) shortcut, by design.
type Valuer interface {
	// TelemetryValue returns a value safe to serialize to any backend. It MUST NOT
	// expose secret material; redaction is the implementer's contract.
	TelemetryValue() any
}

// ── Field constructors: the only doors onto the stream ──────────────────────

// stringValue, int64Value, float64Value, boolValue, and durValue are the minimal
// concrete Valuers wrapping a primitive. They are unexported so a Field value can
// be obtained ONLY through the constructors below — there is no any-typed door.
type (
	stringValue  string
	int64Value   int64
	float64Value float64
	boolValue    bool
	durValue     time.Duration
)

func (v stringValue) TelemetryValue() any  { return string(v) }
func (v int64Value) TelemetryValue() any   { return int64(v) }
func (v float64Value) TelemetryValue() any { return float64(v) }
func (v boolValue) TelemetryValue() any    { return bool(v) }
func (v durValue) TelemetryValue() any     { return time.Duration(v) }

// String wraps a string value as a Field.
func String(key, value string) Field { return Field{Key: key, Value: stringValue(value)} }

// Int64 wraps an int64 value as a Field.
func Int64(key string, value int64) Field { return Field{Key: key, Value: int64Value(value)} }

// Float64 wraps a float64 value as a Field.
func Float64(key string, value float64) Field { return Field{Key: key, Value: float64Value(value)} }

// Bool wraps a bool value as a Field.
func Bool(key string, value bool) Field { return Field{Key: key, Value: boolValue(value)} }

// Dur wraps a time.Duration value as a Field.
func Dur(key string, value time.Duration) Field { return Field{Key: key, Value: durValue(value)} }

// Err wraps an error as the "error" Field. The value is the error's redaction-safe
// string (or "" when err is nil); Err never panics on a nil error.
func Err(err error) Field {
	if err == nil {
		return Field{Key: "error", Value: stringValue("")}
	}
	return Field{Key: "error", Value: stringValue(err.Error())}
}

// Any is the door for a Secret and any other Valuer-satisfying type: it carries
// the value's already-redacted projection onto the stream and nothing raw.
func Any(key string, v Valuer) Field { return Field{Key: key, Value: v} }

// ── T6: the token/cost ledger rides the stream as a typed Event ─────────────

// Ledger is the token/cost accounting payload for a Run/phase (T6, 04 §6). It is
// rendered to an ordinary "cost.ledger" Event on PlaneAgent by LedgerEvent, so
// FinOps (S9) and budget machinery read structured attributes off the SAME plane-
// (b) stream — no second pipe, no parallel meter, ordered with the phase/gate
// Events it belongs to. Centralizing the schema here makes it the library's
// responsibility, not each call site's. CostMicros is an integer (micro-units of
// account currency) to avoid float drift across millions of calls.
type Ledger struct {
	RunID      string
	PhaseID    string
	Model      string
	Harness    string
	TokensIn   int64
	TokensOut  int64
	CacheHits  int64 // cache-hit input tokens, metered separately for cost models
	CostMicros int64 // provider spend in micro-units of account currency
	Retries    int32
	WallTime   time.Duration
}

// LedgerEvent builds the canonical PlaneAgent "cost.ledger" Event at
// SeverityInfo. now is supplied by the caller's injected Clock (the library reads
// no clock); pass the zero time to let the adapter stamp.
func LedgerEvent(now time.Time, l Ledger) Event {
	return Event{
		Time:     now,
		Plane:    PlaneAgent,
		Severity: SeverityInfo,
		Name:     "cost.ledger",
		Fields: []Field{
			String("run.id", l.RunID),
			String("phase.id", l.PhaseID),
			String("model", l.Model),
			String("harness", l.Harness),
			Int64("tokens.in", l.TokensIn),
			Int64("tokens.out", l.TokensOut),
			Int64("cache.hits", l.CacheHits),
			Int64("cost.micros", l.CostMicros),
			Int64("retries", int64(l.Retries)),
			Dur("wall.time", l.WallTime),
		},
	}
}
