package observability_test

import (
	"context"
	stderrors "errors"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// ── Enum zero-value / ordering guarantees (contract §2) ─────────────────────.

func TestPlaneZeroIsUnset(t *testing.T) {
	t.Parallel()
	var p observability.Plane
	if p != observability.PlaneUnset {
		t.Fatalf("zero Plane = %d, want PlaneUnset (%d)", p, observability.PlaneUnset)
	}
}

func TestPlaneOrdering(t *testing.T) {
	t.Parallel()
	// The order is the wire/telemetry contract: append-only, never reordered.
	cases := []struct {
		got  observability.Plane
		want uint8
	}{
		{observability.PlaneUnset, 0},
		{observability.PlaneSelf, 1},
		{observability.PlaneAgent, 2},
		{observability.PlaneGenerated, 3},
	}
	for _, tc := range cases {
		if uint8(tc.got) != tc.want {
			t.Errorf("Plane = %d, want %d", uint8(tc.got), tc.want)
		}
	}
}

func TestSeverityZeroIsDebug(t *testing.T) {
	t.Parallel()
	var s observability.Severity
	if s != observability.SeverityDebug {
		t.Fatalf("zero Severity = %d, want SeverityDebug (%d)", s, observability.SeverityDebug)
	}
}

func TestSeverityOrdering(t *testing.T) {
	t.Parallel()
	cases := []struct {
		got  observability.Severity
		want uint8
	}{
		{observability.SeverityDebug, 0},
		{observability.SeverityInfo, 1},
		{observability.SeverityWarn, 2},
		{observability.SeverityError, 3},
	}
	for _, tc := range cases {
		if uint8(tc.got) != tc.want {
			t.Errorf("Severity = %d, want %d", uint8(tc.got), tc.want)
		}
	}
	// Severities must be totally ordered so MinSeverity filtering is a simple <.
	if observability.SeverityDebug >= observability.SeverityInfo ||
		observability.SeverityInfo >= observability.SeverityWarn ||
		observability.SeverityWarn >= observability.SeverityError {
		t.Fatal("severity levels are not strictly increasing")
	}
}

// ── Field constructors: the only doors onto the stream (contract §2) ────────.

func TestStringField(t *testing.T) {
	t.Parallel()
	f := observability.String("phase", "implement")
	if f.Key != "phase" {
		t.Errorf("Key = %q, want %q", f.Key, "phase")
	}
	if f.Value == nil {
		t.Fatal("Value is nil")
	}
	if got := f.Value.TelemetryValue(); got != "implement" {
		t.Errorf("TelemetryValue() = %#v, want %q", got, "implement")
	}
}

func TestInt64Field(t *testing.T) {
	t.Parallel()
	f := observability.Int64("tokens.in", 4096)
	if f.Key != "tokens.in" {
		t.Errorf("Key = %q, want %q", f.Key, "tokens.in")
	}
	if got := f.Value.TelemetryValue(); got != int64(4096) {
		t.Errorf("TelemetryValue() = %#v (%T), want int64(4096)", got, got)
	}
}

func TestFloat64Field(t *testing.T) {
	t.Parallel()
	f := observability.Float64("ratio", 0.5)
	if got := f.Value.TelemetryValue(); got != 0.5 {
		t.Errorf("TelemetryValue() = %#v, want 0.5", got)
	}
}

func TestBoolField(t *testing.T) {
	t.Parallel()
	f := observability.Bool("gate.passed", true)
	if f.Key != "gate.passed" {
		t.Errorf("Key = %q, want %q", f.Key, "gate.passed")
	}
	if got := f.Value.TelemetryValue(); got != true {
		t.Errorf("TelemetryValue() = %#v, want true", got)
	}
}

func TestDurField(t *testing.T) {
	t.Parallel()
	f := observability.Dur("elapsed", 250*time.Millisecond)
	if got := f.Value.TelemetryValue(); got != 250*time.Millisecond {
		t.Errorf("TelemetryValue() = %#v, want 250ms", got)
	}
}

func TestErrFieldKeyIsError(t *testing.T) {
	t.Parallel()
	cause := stderrors.New("boom")
	f := observability.Err(cause)
	if f.Key != "error" {
		t.Errorf("Err field Key = %q, want %q", f.Key, "error")
	}
	got, ok := f.Value.TelemetryValue().(string)
	if !ok {
		t.Fatalf("Err TelemetryValue() = %#v (%T), want a string", got, f.Value.TelemetryValue())
	}
	if !strings.Contains(got, "boom") {
		t.Errorf("Err TelemetryValue() = %q, want it to contain %q", got, "boom")
	}
}

// secretFieldError models an *errors.Error that honors the errors-contract
// no-secret-in-message rule: it carries the secret only as a redacted field, so
// its Error() string never interpolates the raw value.
type secretFieldError struct {
	redactedField string
}

func (e secretFieldError) Error() string {
	// The message names the field by its redacted projection, never the raw secret
	// — exactly what an *errors.Error built via WithField produces.
	return "auth failed (token=" + e.redactedField + ")"
}

// TestErrRedactionIsDelegatedToTheError pins the REAL guarantee behind the Err
// constructor's "redaction-safe error string" wording: Err renders err.Error(),
// which is leak-safe iff the error honors the errors-contract no-secret-in-message
// rule. An error carrying a secret only as a redacted field never surfaces the raw
// material through Err — this is the case the contract's secret-safety claim relies
// on, and it was asserted by no test.
func TestErrRedactionIsDelegatedToTheError(t *testing.T) {
	t.Parallel()
	const canary = "ghp_realsecretvalue"
	safe := secretFieldError{redactedField: "secrets.Secret(REDACTED)"}
	f := observability.Err(safe)

	rendered, ok := f.Value.TelemetryValue().(string)
	if !ok {
		t.Fatalf("Err TelemetryValue() is not a string: %#v", f.Value.TelemetryValue())
	}
	if strings.Contains(rendered, canary) {
		t.Errorf("Err over a no-secret-in-message error leaked the canary: %q", rendered)
	}
	if !strings.Contains(rendered, "secrets.Secret(REDACTED)") {
		t.Errorf("Err did not render the error's redacted projection: %q", rendered)
	}
}

// TestErrSurfacesAnInterpolatedSecret documents the boundary of the guarantee: Err
// performs NO redaction itself — it is exactly stringValue(err.Error()). An error
// that VIOLATES the no-secret-in-message rule by interpolating a raw secret into
// its message (the classic fmt.Errorf("token=%s", secret)) DOES surface that secret
// through Err. This is the negative case the "redaction-safe error string" wording
// overstates; the safety is the error's contract, not Err's.
func TestErrSurfacesAnInterpolatedSecret(t *testing.T) {
	t.Parallel()
	const canary = "ghp_realsecretvalue"
	//nolint:err113 // a literal fmt.Errorf is the misuse this test deliberately models.
	leaky := stderrors.New("token=" + canary) // models fmt.Errorf("token=%s", secret)
	f := observability.Err(leaky)

	rendered, ok := f.Value.TelemetryValue().(string)
	if !ok {
		t.Fatalf("Err TelemetryValue() is not a string: %#v", f.Value.TelemetryValue())
	}
	// Err does NOT redact: a secret interpolated into the message reaches the wire.
	// This proves the "redaction-safe" wording on Err is delegated, not intrinsic —
	// the safety lives with the error, not the constructor.
	if !strings.Contains(rendered, canary) {
		t.Errorf("Err unexpectedly redacted an interpolated secret (%q); Err performs no redaction by design", rendered)
	}
}

func TestErrFieldNilCause(t *testing.T) {
	t.Parallel()
	// Err(nil) must not panic; it yields the "error" key with a benign value.
	f := observability.Err(nil)
	if f.Key != "error" {
		t.Errorf("Err(nil) Key = %q, want %q", f.Key, "error")
	}
	if f.Value == nil {
		t.Fatal("Err(nil) produced a nil Valuer")
	}
	// Must be safe to render without panicking.
	_ = f.Value.TelemetryValue()
}

// stubValuer is an arbitrary external Valuer the Any door must accept.
type stubValuer struct{ v any }

func (s stubValuer) TelemetryValue() any { return s.v }

func TestAnyField(t *testing.T) {
	t.Parallel()
	f := observability.Any("token", stubValuer{v: "redacted-projection"})
	if f.Key != "token" {
		t.Errorf("Key = %q, want %q", f.Key, "token")
	}
	if got := f.Value.TelemetryValue(); got != "redacted-projection" {
		t.Errorf("TelemetryValue() = %#v, want %q", got, "redacted-projection")
	}
}

func TestAnyNilValuerIsMisuseResistant(t *testing.T) {
	t.Parallel()
	// Any(key, nil) is a valid-looking misuse: without a guard it lands a
	// Field{Value: nil} that nil-derefs every later inspection (LedgerFrom, an
	// Exporter walking Fields). The constructor must substitute a safe no-value
	// Valuer so the Field is never a poison value.
	f := observability.Any("tokens.in", nil)
	if f.Key != "tokens.in" {
		t.Errorf("Key = %q, want %q", f.Key, "tokens.in")
	}
	if f.Value == nil {
		t.Fatal("Any(key, nil) produced a Field with a nil Valuer (poison value)")
	}
	// The substituted projection must be a benign no-value, never raw material,
	// and inspectable without a panic.
	if got := f.Value.TelemetryValue(); got != "" {
		t.Errorf("Any(key, nil).TelemetryValue() = %#v, want \"\" (no-value)", got)
	}
}

// ── ConfigError (contract §2; Q7) ───────────────────────────────────────────.

func TestConfigErrorFormat(t *testing.T) {
	t.Parallel()
	e := &observability.ConfigError{Field: "ServiceName", Message: "required"}
	want := "ServiceName: required"
	if e.Error() != want {
		t.Errorf("ConfigError.Error() = %q, want %q", e.Error(), want)
	}
}

func TestConfigErrorUnwrapNilWhenNoCause(t *testing.T) {
	t.Parallel()
	// A ConfigError with no wrapped cause unwraps to nil (Unwrap is the %w seam
	// the contract promises; New-produced validation errors carry no cause).
	e := &observability.ConfigError{Field: "Exporter", Message: "nil"}
	if got := stderrors.Unwrap(e); got != nil {
		t.Errorf("Unwrap(ConfigError without cause) = %v, want nil", got)
	}
}

// ── LedgerEvent (T6; contract §2 + §4) ──────────────────────────────────────.

func TestLedgerEventShape(t *testing.T) {
	t.Parallel()
	now := time.Unix(1700000000, 0).UTC()
	l := observability.Ledger{
		RunID: "run-1", PhaseID: "implement", Model: "claude", Harness: "claudecode",
		TokensIn: 100, TokensOut: 200, CacheHits: 10, CostMicros: 12345,
		Retries: 2, WallTime: 3 * time.Second,
	}
	e := observability.LedgerEvent(now, l)

	if e.Name != "cost.ledger" {
		t.Errorf("Name = %q, want %q", e.Name, "cost.ledger")
	}
	if e.Plane != observability.PlaneAgent {
		t.Errorf("Plane = %v, want PlaneAgent", e.Plane)
	}
	if e.Severity != observability.SeverityInfo {
		t.Errorf("Severity = %v, want SeverityInfo", e.Severity)
	}
	if !e.Time.Equal(now) {
		t.Errorf("Time = %v, want %v", e.Time, now)
	}
	if len(e.Fields) == 0 {
		t.Fatal("LedgerEvent produced no Fields")
	}

	// Every Ledger datum must be recoverable from the Fields by key, so a
	// budget test can read them off the structured stream.
	fields := map[string]any{}
	for _, f := range e.Fields {
		fields[f.Key] = f.Value.TelemetryValue()
	}
	checks := []struct {
		key  string
		want any
	}{
		{"run.id", "run-1"},
		{"phase.id", "implement"},
		{"model", "claude"},
		{"harness", "claudecode"},
		{"tokens.in", int64(100)},
		{"tokens.out", int64(200)},
		{"cache.hits", int64(10)},
		{"cost.micros", int64(12345)},
		{"retries", int64(2)},
		{"wall.time", 3 * time.Second},
	}
	for _, c := range checks {
		got, ok := fields[c.key]
		if !ok {
			t.Errorf("LedgerEvent missing field %q", c.key)
			continue
		}
		if got != c.want {
			t.Errorf("LedgerEvent field %q = %#v, want %#v", c.key, got, c.want)
		}
	}
}

func TestLedgerEventZeroTimeLeftZero(t *testing.T) {
	t.Parallel()
	// now == zero → the adapter stamps; LedgerEvent must leave Time zero.
	e := observability.LedgerEvent(time.Time{}, observability.Ledger{RunID: "r"})
	if !e.Time.IsZero() {
		t.Errorf("LedgerEvent(zero, _).Time = %v, want zero", e.Time)
	}
}

// ── New validation (contract §2 + §4 Purity of New) ─────────────────────────.

func TestNewRejectsEmptyServiceName(t *testing.T) {
	t.Parallel()
	_, err := observability.New(
		observability.Config{ServiceName: ""},
		observability.Deps{Exporter: noopExporter{}, Clock: fixedClock{}},
	)
	if err == nil {
		t.Fatal("New with empty ServiceName returned nil error")
	}
	var cfgErr *observability.ConfigError
	if !stderrors.As(err, &cfgErr) {
		t.Fatalf("error is not *ConfigError: %T", err)
	}
	if cfgErr.Field != "ServiceName" {
		t.Errorf("ConfigError.Field = %q, want %q", cfgErr.Field, "ServiceName")
	}
}

func TestNewRejectsNilExporter(t *testing.T) {
	t.Parallel()
	_, err := observability.New(
		observability.Config{ServiceName: "svc"},
		observability.Deps{Exporter: nil, Clock: fixedClock{}},
	)
	if err == nil {
		t.Fatal("New with nil Exporter returned nil error")
	}
	var cfgErr *observability.ConfigError
	if !stderrors.As(err, &cfgErr) {
		t.Fatalf("error is not *ConfigError: %T", err)
	}
	if cfgErr.Field != "Exporter" {
		t.Errorf("ConfigError.Field = %q, want %q", cfgErr.Field, "Exporter")
	}
}

func TestNewRejectsNilClock(t *testing.T) {
	t.Parallel()
	// Scope cannot stamp duration without a Clock — New must reject a nil Clock.
	_, err := observability.New(
		observability.Config{ServiceName: "svc"},
		observability.Deps{Exporter: noopExporter{}, Clock: nil},
	)
	if err == nil {
		t.Fatal("New with nil Clock returned nil error")
	}
	var cfgErr *observability.ConfigError
	if !stderrors.As(err, &cfgErr) {
		t.Fatalf("error is not *ConfigError: %T", err)
	}
	if cfgErr.Field != "Clock" {
		t.Errorf("ConfigError.Field = %q, want %q", cfgErr.Field, "Clock")
	}
}

func TestNewValidReturnsUsableProvider(t *testing.T) {
	t.Parallel()
	p, err := observability.New(
		observability.Config{ServiceName: "svc", DefaultPlane: observability.PlaneSelf},
		observability.Deps{Exporter: noopExporter{}, Clock: fixedClock{}},
	)
	if err != nil {
		t.Fatalf("New(valid) error: %v", err)
	}
	if p == nil {
		t.Fatal("New(valid) returned a nil Provider")
	}
}

// ── Test doubles local to this file ─────────────────────────────────────────.

type noopExporter struct{}

func (noopExporter) Export(_ context.Context, _ []observability.Record) error { return nil }

type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Unix(0, 0).UTC() }
