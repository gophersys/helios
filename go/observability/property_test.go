package observability_test

import (
	"context"
	stderrors "errors"
	"math"
	"strings"
	"testing"
	"time"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/observability"
)

// errScopeFailed is the sentinel a failed Scope Outcome carries (declared, not minted
// inline) so the outcome property exercises the error branch with a stable value.
var errScopeFailed = stderrors.New("scope failed")

// The `property` ctl.sh verb runs `go test ./... -race` with RAPID_CHECKS set in the
// process environment (default 1000 iterations/property, ADR-0020 dimension (a)); rapid
// reads it directly. These properties pin the library's load-bearing invariants over the
// whole input space, not a single example.

// allSeverities / allPlanes are the closed, append-only enumerations (event.go). The
// property suite draws from them so every level/plane axis is exercised.
var (
	allSeverities = []observability.Severity{
		observability.SeverityDebug, observability.SeverityInfo,
		observability.SeverityWarn, observability.SeverityError,
	}
	allPlanes = []observability.Plane{
		observability.PlaneUnset, observability.PlaneSelf,
		observability.PlaneAgent, observability.PlaneGenerated,
	}
)

// drawSeverity / drawPlane pull an enumerated value from the closed sets.
func drawSeverity(rt *rapid.T) observability.Severity {
	return allSeverities[rapid.IntRange(0, len(allSeverities)-1).Draw(rt, "severity")]
}

func drawPlane(rt *rapid.T) observability.Plane {
	return allPlanes[rapid.IntRange(0, len(allPlanes)-1).Draw(rt, "plane")]
}

// TestProperty_StringFieldRoundTrips asserts the String constructor is a faithful
// round-trip: for any key/value, the Field carries that key and its TelemetryValue
// projection is exactly the original string (the only door onto the stream must not
// mangle the payload).
func TestProperty_StringFieldRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		key := rapid.StringMatching(`[a-z][a-z0-9.]{0,30}`).Draw(rt, "key")
		val := rapid.String().Draw(rt, "val")
		f := observability.String(key, val)
		if f.Key != key {
			rt.Fatalf("String key drifted: got %q want %q", f.Key, key)
		}
		if got := f.Value.TelemetryValue(); got != val {
			rt.Fatalf("String value drifted: got %#v want %q", got, val)
		}
	})
}

// TestProperty_Int64FieldRoundTrips asserts Int64 round-trips any int64 as a typed
// int64 projection — a budget reader must recover the exact integer it metered.
func TestProperty_Int64FieldRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		key := rapid.StringMatching(`[a-z][a-z0-9.]{0,30}`).Draw(rt, "key")
		val := rapid.Int64().Draw(rt, "val")
		got, ok := observability.Int64(key, val).Value.TelemetryValue().(int64)
		if !ok {
			rt.Fatalf("Int64 projection is not an int64")
		}
		if got != val {
			rt.Fatalf("Int64 value drifted: got %d want %d", got, val)
		}
	})
}

// TestProperty_SeverityFilteringIsMonotone asserts the Emit-time filter is exactly the
// `>=` comparison the contract promises: an Event ships iff its Severity >= MinSeverity,
// for EVERY (minSeverity, eventSeverity) pair. A drift to `>` (off-by-one) would drop
// at-threshold Events and is caught here across the whole 4x4 grid plus the zero case.
func TestProperty_SeverityFilteringIsMonotone(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		minSev := drawSeverity(rt)
		evSev := drawSeverity(rt)

		exp := &propExporter{}
		p, err := observability.New(
			observability.Config{ServiceName: "prop", MinSeverity: minSev},
			observability.Deps{Exporter: exp, Clock: propClock{}},
		)
		if err != nil {
			rt.Fatalf("New: %v", err)
		}
		p.Emit(context.Background(), observability.Event{Name: "e", Severity: evSev})
		if err := p.Flush(context.Background()); err != nil {
			rt.Fatalf("Flush: %v", err)
		}

		shipped := len(exp.snapshot()) == 1
		wantShipped := evSev >= minSev
		if shipped != wantShipped {
			rt.Fatalf("severity filter wrong: min=%d ev=%d shipped=%v want %v",
				minSev, evSev, shipped, wantShipped)
		}
	})
}

// TestProperty_PlaneStampingPreservesOrInherits asserts the plane rule over the whole
// plane space: an Event with an explicit (non-Unset) Plane keeps it exactly; an Event
// emitted as PlaneUnset inherits the resolved DefaultPlane and is NEVER left on the
// sentinel PlaneUnset on the wire.
func TestProperty_PlaneStampingPreservesOrInherits(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		defaultPlane := drawPlane(rt)
		eventPlane := drawPlane(rt)

		exp := &propExporter{}
		p, err := observability.New(
			observability.Config{ServiceName: "prop", DefaultPlane: defaultPlane},
			observability.Deps{Exporter: exp, Clock: propClock{}},
		)
		if err != nil {
			rt.Fatalf("New: %v", err)
		}
		p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo, Plane: eventPlane})
		if err := p.Flush(context.Background()); err != nil {
			rt.Fatalf("Flush: %v", err)
		}

		recs := exp.snapshot()
		if len(recs) != 1 {
			rt.Fatalf("want exactly 1 shipped Record, got %d", len(recs))
		}
		got := recs[0].Event.Plane

		// New resolves a PlaneUnset DefaultPlane to PlaneSelf (event.go / New).
		resolvedDefault := defaultPlane
		if resolvedDefault == observability.PlaneUnset {
			resolvedDefault = observability.PlaneSelf
		}
		want := eventPlane
		if eventPlane == observability.PlaneUnset {
			want = resolvedDefault
		}
		if got != want {
			rt.Fatalf("plane wrong: default=%d event=%d got=%d want=%d", defaultPlane, eventPlane, got, want)
		}
		if got == observability.PlaneUnset {
			rt.Fatalf("a shipped Record kept the sentinel PlaneUnset")
		}
	})
}

// TestProperty_WithInheritedFieldsPrecedeCallSite asserts the With-inheritance ordering
// invariant for any sequence of inherited + call-site fields: inherited Fields appear
// first, in With order, then the call-site Fields, in their order — and the parent is
// never mutated. Order is part of the contract (a reader keys by position for some
// low-cardinality attributes).
func TestProperty_WithInheritedFieldsPrecedeCallSite(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		nInherit := rapid.IntRange(0, 5).Draw(rt, "nInherit")
		nCall := rapid.IntRange(0, 5).Draw(rt, "nCall")

		inherit := make([]observability.Field, nInherit)
		for i := range inherit {
			inherit[i] = observability.String("inh"+itoa(i), "v")
		}
		call := make([]observability.Field, nCall)
		for i := range call {
			call[i] = observability.String("call"+itoa(i), "v")
		}

		exp := &propExporter{}
		p, err := observability.New(
			observability.Config{ServiceName: "prop"},
			observability.Deps{Exporter: exp, Clock: propClock{}},
		)
		if err != nil {
			rt.Fatalf("New: %v", err)
		}
		child := p.With(inherit...)
		child.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo, Fields: call})
		p.Emit(context.Background(), observability.Event{Name: "parent", Severity: observability.SeverityInfo})
		if err := p.Flush(context.Background()); err != nil {
			rt.Fatalf("Flush: %v", err)
		}

		recs := exp.snapshot()
		childFields, childOK := recordFields(recs, "e")
		parentFields, parentOK := recordFields(recs, "parent")
		if !childOK || !parentOK {
			rt.Fatalf("missing records (childOK=%v parentOK=%v)", childOK, parentOK)
		}
		if len(childFields) != nInherit+nCall {
			rt.Fatalf("merged field count = %d, want %d", len(childFields), nInherit+nCall)
		}
		assertKeyPrefix(rt, childFields[:nInherit], "inh")
		assertKeyPrefix(rt, childFields[nInherit:], "call")
		// The parent must not carry any inherited field.
		for _, f := range parentFields {
			if strings.HasPrefix(f.Key, "inh") {
				rt.Fatalf("With leaked inherited field %q onto the parent", f.Key)
			}
		}
	})
}

// recordFields returns the Fields of the first shipped Record named name and whether
// such a Record was found (distinguishing "absent" from "present with no Fields").
func recordFields(recs []observability.Record, name string) ([]observability.Field, bool) {
	for i := range recs {
		if recs[i].Event.Name == name {
			return recs[i].Event.Fields, true
		}
	}
	return nil, false
}

// assertKeyPrefix asserts fields[i].Key == prefix+i for every position, the ordering
// invariant the merge must preserve.
func assertKeyPrefix(rt *rapid.T, fields []observability.Field, prefix string) {
	rt.Helper()
	for i, f := range fields {
		if f.Key != prefix+itoa(i) {
			rt.Fatalf("field %d = %q, want %s%d", i, f.Key, prefix, i)
		}
	}
}

// TestProperty_LedgerEventRoundTrips asserts LedgerEvent is a lossless encoding of a
// Ledger: every numeric/string datum is recoverable from the Event Fields by key, for
// any drawn Ledger. This is the T6 contract a budget meter relies on — the round-trip
// must not drop or corrupt any field.
func TestProperty_LedgerEventRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		want := observability.Ledger{
			RunID:      rapid.String().Draw(rt, "runID"),
			PhaseID:    rapid.String().Draw(rt, "phaseID"),
			Model:      rapid.String().Draw(rt, "model"),
			Harness:    rapid.String().Draw(rt, "harness"),
			TokensIn:   rapid.Int64Range(0, 1<<40).Draw(rt, "tokensIn"),
			TokensOut:  rapid.Int64Range(0, 1<<40).Draw(rt, "tokensOut"),
			CacheHits:  rapid.Int64Range(0, 1<<40).Draw(rt, "cacheHits"),
			CostMicros: rapid.Int64Range(0, 1<<50).Draw(rt, "costMicros"),
			Retries:    rapid.Int32Range(0, 1<<20).Draw(rt, "retries"),
			WallTime:   time.Duration(rapid.Int64Range(0, int64(time.Hour)).Draw(rt, "wallTime")),
		}
		e := observability.LedgerEvent(time.Time{}, want)

		byKey := map[string]any{}
		for _, f := range e.Fields {
			byKey[f.Key] = f.Value.TelemetryValue()
		}
		got := observability.Ledger{
			RunID:      asString(byKey["run.id"]),
			PhaseID:    asString(byKey["phase.id"]),
			Model:      asString(byKey["model"]),
			Harness:    asString(byKey["harness"]),
			TokensIn:   asInt64(byKey["tokens.in"]),
			TokensOut:  asInt64(byKey["tokens.out"]),
			CacheHits:  asInt64(byKey["cache.hits"]),
			CostMicros: asInt64(byKey["cost.micros"]),
			Retries:    asInt32(byKey["retries"]),
			WallTime:   asDuration(byKey["wall.time"]),
		}
		if got != want {
			rt.Fatalf("Ledger round-trip drifted:\n got %+v\nwant %+v", got, want)
		}
	})
}

// TestProperty_ScopeSpanIDsAreDistinctAndMonotone asserts that N successive Scopes on
// one Provider mint DISTINCT, strictly increasing span ordinals — the trace/span
// correlation must never collide across spans (two phases sharing an ID would corrupt a
// trace). This pins the span counter's monotonic-increment behavior: a counter that
// decremented, stalled, or repeated would surface here as a duplicate or out-of-order ID.
func TestProperty_ScopeSpanIDsAreDistinctAndMonotone(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		n := rapid.IntRange(2, 8).Draw(rt, "nScopes")
		exp := &propExporter{}
		p := newPropProvider(rt, exp)
		ctx := context.Background()
		for i := 0; i < n; i++ {
			_, end := p.Scope(ctx, "span")
			end(observability.Outcome{})
		}
		if err := p.Flush(ctx); err != nil {
			rt.Fatalf("Flush: %v", err)
		}

		recs := exp.snapshot()
		if len(recs) != n {
			rt.Fatalf("got %d span Records, want %d", len(recs), n)
		}
		assertSpanIDsDistinctMonotone(rt, recs)
	})
}

// assertSpanIDsDistinctMonotone checks every span Record carries correlation IDs that are
// non-empty, distinct, and strictly increasing — the span-counter invariant.
func assertSpanIDsDistinctMonotone(rt *rapid.T, recs []observability.Record) {
	rt.Helper()
	seen := map[string]bool{}
	var prev string
	for i, r := range recs {
		if r.SpanID == "" || r.TraceID == "" {
			rt.Fatalf("span %d missing correlation: trace=%q span=%q", i, r.TraceID, r.SpanID)
		}
		if seen[r.SpanID] {
			rt.Fatalf("span %d reused SpanID %q — IDs must be distinct", i, r.SpanID)
		}
		seen[r.SpanID] = true
		// IDs are "span-<ordinal>"; a monotone counter makes each strictly greater than the
		// previous, so a non-increment mutant (no ++, or --) produces a collision caught
		// above OR a non-increasing equal-length suffix.
		if prev != "" && r.SpanID <= prev && len(r.SpanID) == len(prev) {
			rt.Fatalf("span %d SpanID %q is not after %q — ordinals must increase", i, r.SpanID, prev)
		}
		prev = r.SpanID
	}
}

// TestProperty_ScopeOutcomeRecordsOkFlag asserts the Scope close func records ok=true for
// a nil Outcome and ok=false (plus the error field) for a failed Outcome, across the
// whole boolean axis. This pins the outcome branch: a negated condition would invert the
// ok flag and mislabel every span's success/failure.
func TestProperty_ScopeOutcomeRecordsOkFlag(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		fail := rapid.Bool().Draw(rt, "fail")
		exp := &propExporter{}
		p := newPropProvider(rt, exp)
		ctx := context.Background()
		_, end := p.Scope(ctx, "span")
		var outcome observability.Outcome
		if fail {
			outcome = observability.Outcome{Err: errScopeFailed}
		}
		end(outcome)
		if err := p.Flush(ctx); err != nil {
			rt.Fatalf("Flush: %v", err)
		}

		recs := exp.snapshot()
		if len(recs) != 1 {
			rt.Fatalf("got %d span Records, want 1", len(recs))
		}
		okVal, sawOK := boolField(recs[0].Event.Fields, "ok")
		_, sawError := stringField(recs[0].Event.Fields, "error")
		if !sawOK {
			rt.Fatalf("span Event missing the ok flag")
		}
		if okVal != !fail {
			rt.Fatalf("ok flag = %v, want %v (fail=%v)", okVal, !fail, fail)
		}
		// A failed Outcome must carry the error field; a clean one must NOT.
		if sawError != fail {
			rt.Fatalf("error field present=%v, want %v (fail=%v)", sawError, fail, fail)
		}
	})
}

// boolField returns the bool projection of the field named key and whether it was found.
func boolField(fields []observability.Field, key string) (value, found bool) {
	for _, f := range fields {
		if f.Key != key || f.Value == nil {
			continue
		}
		if b, ok := f.Value.TelemetryValue().(bool); ok {
			return b, true
		}
	}
	return false, false
}

// stringField returns the string projection of the field named key and whether it was
// found.
func stringField(fields []observability.Field, key string) (value string, found bool) {
	for _, f := range fields {
		if f.Key != key || f.Value == nil {
			continue
		}
		if s, ok := f.Value.TelemetryValue().(string); ok {
			return s, true
		}
	}
	return "", false
}

// newPropProvider builds a valid Provider over exp for the Scope properties, failing the
// rapid case on a construction error.
//
//nolint:ireturn // observability.New returns the frozen Provider port the properties drive.
func newPropProvider(rt *rapid.T, exp *propExporter) observability.Provider {
	rt.Helper()
	p, err := observability.New(
		observability.Config{ServiceName: "prop"},
		observability.Deps{Exporter: exp, Clock: propClock{}},
	)
	if err != nil {
		rt.Fatalf("New: %v", err)
	}
	return p
}

// TestNewResolvesUnsetDefaultPlaneToSelf pins, deterministically, the New default-plane
// resolution that the plane property exercises only when rapid happens to draw the right
// pair: a Config DefaultPlane left PlaneUnset resolves to PlaneSelf, while an explicit
// non-Unset DefaultPlane is preserved EXACTLY. A negated resolution condition (which
// would overwrite a concrete DefaultPlane with PlaneSelf) is caught here on the PlaneAgent
// / PlaneGenerated rows that the fallback value (PlaneSelf) would otherwise mask.
func TestNewResolvesUnsetDefaultPlaneToSelf(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name         string
		configured   observability.Plane
		wantResolved observability.Plane
	}{
		{"unset->self", observability.PlaneUnset, observability.PlaneSelf},
		{"self preserved", observability.PlaneSelf, observability.PlaneSelf},
		{"agent preserved", observability.PlaneAgent, observability.PlaneAgent},
		{"generated preserved", observability.PlaneGenerated, observability.PlaneGenerated},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			exp := &propExporter{}
			p, err := observability.New(
				observability.Config{ServiceName: "plane", DefaultPlane: tc.configured},
				observability.Deps{Exporter: exp, Clock: propClock{}},
			)
			if err != nil {
				t.Fatalf("New: %v", err)
			}
			// An Event emitted as PlaneUnset inherits the RESOLVED DefaultPlane.
			p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo})
			if err := p.Flush(context.Background()); err != nil {
				t.Fatalf("Flush: %v", err)
			}
			recs := exp.snapshot()
			if len(recs) != 1 {
				t.Fatalf("got %d Records, want 1", len(recs))
			}
			if got := recs[0].Event.Plane; got != tc.wantResolved {
				t.Errorf("configured DefaultPlane %v resolved to %v, want %v", tc.configured, got, tc.wantResolved)
			}
		})
	}
}

// ── property helpers (test-local) ───────────────────────────────────────────.

type propExporter struct {
	records []observability.Record
}

func (e *propExporter) Export(_ context.Context, records []observability.Record) error {
	e.records = append(e.records, records...)
	return nil
}

func (e *propExporter) snapshot() []observability.Record { return e.records }

type propClock struct{}

func (propClock) Now() time.Time { return time.Unix(1700000000, 0).UTC() }

func asString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func asInt64(v any) int64 {
	if n, ok := v.(int64); ok {
		return n
	}
	return 0
}

// asInt32 narrows a telemetry value to int32 with an explicit bounds check (no silent
// wrap) — the int32 Retries field is stored as an int64 on the stream, so the round-trip
// is always in range; an out-of-range value is clamped, mirroring the production decoder.
func asInt32(v any) int32 {
	n := asInt64(v)
	switch {
	case n > math.MaxInt32:
		return math.MaxInt32
	case n < math.MinInt32:
		return math.MinInt32
	default:
		return int32(n)
	}
}

func asDuration(v any) time.Duration {
	if d, ok := v.(time.Duration); ok {
		return d
	}
	return 0
}

func itoa(i int) string {
	if i == 0 {
		return "0"
	}
	var buf [20]byte
	pos := len(buf)
	for i > 0 {
		pos--
		buf[pos] = byte('0' + i%10)
		i /= 10
	}
	return string(buf[pos:])
}
