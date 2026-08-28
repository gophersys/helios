package observability

import (
	"math"
	"time"
)

// ── Event: the one structured record every plane emits ──────────────────────.

// Plane is the P9 telemetry plane an Event belongs to. It is STAMPED, never
// inferred, so a single backend partitions Eden's own signal from agent and
// generated-system signal without parsing payloads. Zero value is PlaneUnset so
// an unstamped Event visibly inherits Config.DefaultPlane rather than silently
// landing on plane (a).
type Plane uint8

// The P9 telemetry planes, append-only and ordered (the wire/telemetry contract);
// PlaneUnset is the zero so an unstamped Event inherits Config.DefaultPlane.
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

// The operator-facing severity levels, append-only and totally ordered so
// MinSeverity filtering is a simple comparison; SeverityDebug is the zero.
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

// ── Field constructors: the only doors onto the stream ─────────────────────.

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

// nilValue is the substitute Valuer Any installs when handed a nil Valuer, so a
// Field's Value is never a nil interface: every inspection path (LedgerFrom, an
// adapter's serialization loop) can call TelemetryValue without a nil deref. Its
// projection is the empty string — a no-value attribute, never raw material.
type nilValue struct{}

func (nilValue) TelemetryValue() any { return "" }

// Any is the door for a Secret and any other Valuer-satisfying type: it carries
// the value's already-redacted projection onto the stream and nothing raw. A nil
// Valuer is substituted with an empty no-value projection (misuse-resistance):
// Any never lands a Field whose Value is a nil interface, so no downstream
// inspector (LedgerFrom, an Exporter walking Fields) can nil-deref it.
func Any(key string, v Valuer) Field {
	if v == nil {
		return Field{Key: key, Value: nilValue{}}
	}
	return Field{Key: key, Value: v}
}

// ── T6: the token/cost ledger rides the stream as a typed Event ────────────.

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

// LedgerName is the stable, low-cardinality Event.Name of the T6 token/cost
// ledger Event — the single name LedgerEvent stamps and LedgerFrom matches on, so
// the encoder and its inverse agree on the record's identity in one place.
const LedgerName = "cost.ledger"

// The cost.ledger field keys, declared ONCE so LedgerEvent (encoder) and
// LedgerFrom (decoder) project the same Ledger schema without two key lists
// drifting apart. They are the wire/telemetry contract for the T6 record.
const (
	ledgerKeyRunID      = "run.id"
	ledgerKeyPhaseID    = "phase.id"
	ledgerKeyModel      = "model"
	ledgerKeyHarness    = "harness"
	ledgerKeyTokensIn   = "tokens.in"
	ledgerKeyTokensOut  = "tokens.out"
	ledgerKeyCacheHits  = "cache.hits"
	ledgerKeyCostMicros = "cost.micros"
	ledgerKeyRetries    = "retries"
	ledgerKeyWallTime   = "wall.time"
)

// LedgerEvent builds the canonical PlaneAgent "cost.ledger" Event at
// SeverityInfo. now is supplied by the caller's injected Clock (the library reads
// no clock); pass the zero time to let the adapter stamp.
//
// The frozen contract (contracts/observability.md §2) fixes this signature as
// LedgerEvent(now time.Time, l Ledger) Event. Taking Ledger by value keeps the
// call site a plain copyable value with no aliasing; the public surface may not
// change to *Ledger, so the gocritic hugeParam suggestion is declined here.
//
//nolint:gocritic // contract §2 fixes l Ledger by value; surface is frozen.
func LedgerEvent(now time.Time, l Ledger) Event {
	return Event{
		Time:     now,
		Plane:    PlaneAgent,
		Severity: SeverityInfo,
		Name:     LedgerName,
		Fields: []Field{
			String(ledgerKeyRunID, l.RunID),
			String(ledgerKeyPhaseID, l.PhaseID),
			String(ledgerKeyModel, l.Model),
			String(ledgerKeyHarness, l.Harness),
			Int64(ledgerKeyTokensIn, l.TokensIn),
			Int64(ledgerKeyTokensOut, l.TokensOut),
			Int64(ledgerKeyCacheHits, l.CacheHits),
			Int64(ledgerKeyCostMicros, l.CostMicros),
			Int64(ledgerKeyRetries, int64(l.Retries)),
			Dur(ledgerKeyWallTime, l.WallTime),
		},
	}
}

// LedgerFrom is the public inverse of LedgerEvent: it reconstructs a typed Ledger
// from a "cost.ledger" Event's Fields, so a budget meter or FinOps reader (S9)
// round-trips token/cost data off the stream without re-deriving the field schema.
// It is the one decoder for the T6 record — the conformance fake and the property
// tests call it rather than each maintaining a private copy.
//
// The bool reports whether e is a cost.ledger Event (e.Name == LedgerName); for any
// other Event it returns the zero Ledger and false. A field whose telemetry
// projection has an unexpected type contributes its zero value (a hand-built poison
// Field cannot panic the decoder), and a Field carrying a nil Valuer is skipped
// rather than nil-dereferenced, mirroring the Any constructor's nil substitution.
//
//nolint:gocritic // Ledger returned by value to match LedgerEvent's by-value contract.
func LedgerFrom(e Event) (Ledger, bool) {
	if e.Name != LedgerName {
		return Ledger{}, false
	}
	var l Ledger
	for _, f := range e.Fields {
		if f.Value == nil {
			continue
		}
		tv := f.Value.TelemetryValue()
		switch f.Key {
		case ledgerKeyRunID:
			l.RunID = ledgerString(tv)
		case ledgerKeyPhaseID:
			l.PhaseID = ledgerString(tv)
		case ledgerKeyModel:
			l.Model = ledgerString(tv)
		case ledgerKeyHarness:
			l.Harness = ledgerString(tv)
		case ledgerKeyTokensIn:
			l.TokensIn = ledgerInt64(tv)
		case ledgerKeyTokensOut:
			l.TokensOut = ledgerInt64(tv)
		case ledgerKeyCacheHits:
			l.CacheHits = ledgerInt64(tv)
		case ledgerKeyCostMicros:
			l.CostMicros = ledgerInt64(tv)
		case ledgerKeyRetries:
			l.Retries = ledgerInt32(tv)
		case ledgerKeyWallTime:
			l.WallTime = ledgerDuration(tv)
		}
	}
	return l, true
}

// ledgerString / ledgerInt64 / ledgerInt32 / ledgerDuration project a telemetry
// value to a concrete Ledger field type, returning the zero value on a type
// mismatch so LedgerFrom never panics on a hand-built poison Field.
func ledgerString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func ledgerInt64(v any) int64 {
	if n, ok := v.(int64); ok {
		return n
	}
	return 0
}

// ledgerInt32 BOUNDS-CHECKS the int64→int32 narrowing rather than relying on a
// silent wrap. Ledger.Retries is an int32 stored on the stream as
// Int64(ledgerKeyRetries, int64(l.Retries)), so a faithful round-trip is always in
// range; a value outside [MinInt32, MaxInt32] (only reachable from a hand-built
// poison Field) is clamped to the boundary, never wrapped — a guard, not a #nosec.
func ledgerInt32(v any) int32 {
	n := ledgerInt64(v)
	switch {
	case n > math.MaxInt32:
		return math.MaxInt32
	case n < math.MinInt32:
		return math.MinInt32
	default:
		return int32(n)
	}
}

func ledgerDuration(v any) time.Duration {
	if d, ok := v.(time.Duration); ok {
		return d
	}
	return 0
}
