package dependencies_test

import (
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f)): a value handed to the library's
// secret-carrying seam — the Sink (the "emit one record outward" port) — that must appear in NO
// surfaced artifact the library itself renders. dependencies has exactly one rendered surface,
// MissingPortError.Error(), and one emit seam, Sink.Emit(record any); neither may echo a record
// the caller hands it. The canary proves the library never inlines a record into its own
// operator-facing text.
const seededCanary = "SEEDED-CANARY-aG9yc2U-d34db33f-do-not-leak"

// TestCanary_DiscardSinkNeverSurfaces asserts the default DiscardSink — the safe wiring when a
// component has no observability backend — DROPS the record entirely: emitting the canary returns
// a nil (accepted) with no retained or surfaced copy. A DiscardSink that buffered or logged the
// record would leak any secret a caller emitted; this pins it to a true black hole.
func TestCanary_DiscardSinkNeverSurfaces(t *testing.T) {
	t.Parallel()
	sink := dependencies.DiscardSink()
	// A secret carried inside a record handed to the emit seam.
	secret := struct{ token string }{token: seededCanary}
	if err := sink.Emit(context.Background(), secret); err != nil {
		t.Fatalf("DiscardSink.Emit returned error: %v", err)
	}
	// The sink exposes no surface at all; the only observable is the returned error, which must
	// not embed the record. (A nil error cannot carry the needle; this guards a future regression
	// that started returning a record-derived error string.)
	if err := sink.Emit(context.Background(), seededCanary); err != nil && strings.Contains(err.Error(), seededCanary) {
		t.Fatalf("DiscardSink surfaced the canary through its error: %q", err.Error())
	}
}

// TestCanary_MissingPortErrorCarriesNoRecord asserts the ONE rendered surface in the library —
// MissingPortError.Error() — names only the port, never any caller-supplied value. Even when a
// canary-bearing record was emitted through the same Set's Sink first, the validation error for a
// different (unwired) port must not pick the secret up. This pins "errors reference, never inline,
// secrets" (the redaction-safe contract) for this library's sole error type.
func TestCanary_MissingPortErrorCarriesNoRecord(t *testing.T) {
	t.Parallel()
	// Emit a canary through a recording sink, then validate a Set missing a DIFFERENT port.
	set, _, _, sink := dependenciestest.Fakes()
	if err := sink.Emit(context.Background(), struct{ token string }{seededCanary}); err != nil {
		t.Fatalf("seed emit failed: %v", err)
	}
	// Now drop the Clock to force a MissingPortError and assert it carries no record text.
	set.Clock = nil
	err := dependencies.Validate(set)
	if err == nil {
		t.Fatal("expected a MissingPortError")
	}
	if strings.Contains(err.Error(), seededCanary) {
		t.Fatalf("MissingPortError leaked the canary: %q", err.Error())
	}
	// Wrapping it (as a narrowing Constructor would) must also not introduce the needle.
	wrapped := fmt.Errorf("engine: %w", err)
	if strings.Contains(wrapped.Error(), seededCanary) {
		t.Fatalf("wrapped MissingPortError leaked the canary: %q", wrapped.Error())
	}
}

// TestRedact_RecordingSinkRetainsOnlyViaExplicitSnapshot documents the one place a record IS
// retained — the test-only RecordingSink, whose entire purpose is to let a test inspect what was
// emitted. It is NOT a leak: the capture is caller-controlled test scaffolding, and the canary is
// retrievable ONLY through the explicit Records() snapshot API (the sink's sole accessor), which
// returns a COPY the caller already owns. This pins that a production DiscardSink (above) — which
// retains nothing — is the wiring that keeps a secret off any retained surface, while the recorder
// hands the record back solely on explicit demand. A regression that made Records() alias internal
// state (so a caller could mutate captured secrets in place) is caught by the snapshot check.
func TestRedact_RecordingSinkRetainsOnlyViaExplicitSnapshot(t *testing.T) {
	t.Parallel()
	var sink dependenciestest.RecordingSink
	if err := sink.Emit(context.Background(), seededCanary); err != nil {
		t.Fatalf("emit failed: %v", err)
	}
	recs := sink.Records()
	if len(recs) != 1 || recs[0] != seededCanary {
		t.Fatalf("RecordingSink did not capture the record via the explicit API: %v", recs)
	}
	// Records() returns a snapshot copy: mutating the returned slice must not change what a later
	// caller sees (the captured secret cannot be altered in place through an alias).
	recs[0] = "REDACTED-BY-CALLER"
	if again := sink.Records(); again[0] != seededCanary {
		t.Fatalf("Records() aliased internal state; snapshot must be a copy, got %v", again[0])
	}
}
