package observability_test

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f)): a secret value that,
// once handed to the observability stream through the ONLY door (a Valuer), must appear
// in NO surfaced artifact — not a shipped Record's Fields, not a Log line, not a Scope
// span's outcome. observability is secret-safe BY CONSTRUCTION: a Field value can enter
// only as a Valuer, whose redacted TelemetryValue projection is the only thing that
// reaches the wire. This suite proves the needle never crosses that boundary.
const seededCanary = "SEEDED-CANARY-aG9yc2U-d34db33f-do-not-leak"

// canarySecret models a secrets.Secret: it HOLDS the raw needle but its TelemetryValue
// projection is the redacted sentinel, so the raw material can only escape if some path
// bypasses TelemetryValue (a real leak). observability never imports secrets — this
// local Valuer keeps the lib a stdlib-only leaf.
type canarySecret struct{ raw string }

func (canarySecret) TelemetryValue() any { return "secrets.Secret(REDACTED)" }

// shippedStrings flushes the Provider and returns every string projection that reached a
// shipped Record, plus the full set of Field keys — the surfaces a secret could leak on.
func shippedStrings(t *testing.T, p observability.Provider, exp *canaryExporter) []string {
	t.Helper()
	if err := p.Flush(context.Background()); err != nil {
		t.Fatalf("Flush: %v", err)
	}
	var out []string
	for _, r := range exp.snapshot() {
		for _, f := range r.Event.Fields {
			if f.Value == nil {
				continue
			}
			if s, ok := f.Value.TelemetryValue().(string); ok {
				out = append(out, s)
			}
		}
	}
	return out
}

// TestCanary_SecretNeverLeaksThroughEmit drives the needle through Emit as a redacting
// Valuer and asserts no shipped Record renders the raw needle on any field.
func TestCanary_SecretNeverLeaksThroughEmit(t *testing.T) {
	t.Parallel()
	exp := &canaryExporter{}
	p := newCanaryProvider(t, exp)

	p.Emit(context.Background(), observability.Event{
		Name: "model.call", Severity: observability.SeverityInfo,
		Fields: []observability.Field{observability.Any("token", canarySecret{raw: seededCanary})},
	})

	for _, s := range shippedStrings(t, p, exp) {
		if strings.Contains(s, seededCanary) {
			t.Fatalf("canary leaked onto a shipped Record via Emit: %q", s)
		}
	}
}

// TestCanary_SecretNeverLeaksThroughLog drives the needle through Log — the subordinate
// logging Sink (10 §4) — and asserts the operator-facing line never carries the raw
// needle. Logging rides the same stream, so it inherits the same by-construction safety.
func TestCanary_SecretNeverLeaksThroughLog(t *testing.T) {
	t.Parallel()
	exp := &canaryExporter{}
	p := newCanaryProvider(t, exp)

	p.Log(context.Background(), observability.SeverityWarn, "credential rejected",
		observability.Any("credential", canarySecret{raw: seededCanary}))

	for _, s := range shippedStrings(t, p, exp) {
		if strings.Contains(s, seededCanary) {
			t.Fatalf("canary leaked onto a Log line: %q", s)
		}
	}
}

// TestCanary_SecretNeverLeaksThroughSpan drives the needle through a Scope span — both as
// a span Field and via the span's Outcome error string — and asserts the span Event the
// close func emits never surfaces the raw needle. The error half models the
// errors-contract no-secret-in-message guarantee: an error whose Error() renders a
// redacted projection keeps the needle off the span.
func TestCanary_SecretNeverLeaksThroughSpan(t *testing.T) {
	t.Parallel()
	exp := &canaryExporter{}
	p := newCanaryProvider(t, exp)

	ctx := context.Background()
	_, end := p.Scope(ctx, "phase.start",
		observability.Any("credential", canarySecret{raw: seededCanary}))
	// The Outcome error honors the errors-contract: its message carries the redacted
	// projection, never the raw needle (the secret is referenced, not inlined).
	end(observability.Outcome{Err: redactedError{}})

	for _, s := range shippedStrings(t, p, exp) {
		if strings.Contains(s, seededCanary) {
			t.Fatalf("canary leaked onto a Scope span: %q", s)
		}
	}
}

// TestCanary_RedactionMarkerIsObservable asserts the redacted projection is actually
// PRESENT on the stream (not silently dropped), so the no-leak result above is a real
// redaction rather than the field vanishing — a future regression that started storing
// raw material would both leak the needle AND lose this marker.
func TestCanary_RedactionMarkerIsObservable(t *testing.T) {
	t.Parallel()
	exp := &canaryExporter{}
	p := newCanaryProvider(t, exp)
	p.Emit(context.Background(), observability.Event{
		Name: "e", Severity: observability.SeverityInfo,
		Fields: []observability.Field{observability.Any("token", canarySecret{raw: seededCanary})},
	})

	var sawMarker bool
	for _, s := range shippedStrings(t, p, exp) {
		if s == "secrets.Secret(REDACTED)" {
			sawMarker = true
		}
	}
	if !sawMarker {
		t.Fatal("the redacted projection did not reach the stream — redaction must mark, not drop")
	}
}

// redactedError models an *errors.Error built via WithField: its Error() names the
// secret only by its redacted projection, never the raw needle.
type redactedError struct{}

func (redactedError) Error() string {
	return "credential rejected (token=secrets.Secret(REDACTED))"
}

// Compile-time check the model is a real error (and not accidentally the needle itself).
var _ error = redactedError{}

// ── canary helpers ─────────────────────────────────────────────────────────.

type canaryExporter struct {
	records []observability.Record
}

func (e *canaryExporter) Export(_ context.Context, records []observability.Record) error {
	e.records = append(e.records, records...)
	return nil
}

func (e *canaryExporter) snapshot() []observability.Record { return e.records }

type canaryClock struct{}

func (canaryClock) Now() time.Time { return time.Unix(1700000000, 0).UTC() }

//nolint:ireturn // observability.New returns the frozen Provider port; the canary suite drives that port.
func newCanaryProvider(t *testing.T, exp *canaryExporter) observability.Provider {
	t.Helper()
	p, err := observability.New(
		observability.Config{ServiceName: "canary-svc", DefaultPlane: observability.PlaneAgent},
		observability.Deps{Exporter: exp, Clock: canaryClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return p
}
