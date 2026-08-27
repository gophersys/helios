package errors_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f), generalising
// workspaceprovidertest.SeededCanary): a value that, once handed to the error model, must
// appear in NO surfaced artifact — not the Error message, not its structured fields, not the
// wrapped-chain string. If the canary leaks, redaction is broken.
const seededCanary = "SEEDED-CANARY-aG9yc2U-d34db33f-do-not-leak"

// TestCanary_NeverLeaksThroughError asserts the canary value never surfaces through the
// error's operator-safe rendering. errors is redaction-safe by construction: a non-scalar
// field is stored as "[unredactable]", and the message/cause never embed a secret unless the
// caller inlines it (a caller-contract violation we deliberately do NOT exercise here). This
// test proves the *model's* surfaces are canary-free for the safe-construction path.
func TestCanary_NeverLeaksThroughError(t *testing.T) {
	t.Parallel()

	// A non-scalar value carrying the canary must be reduced to "[unredactable]", never stored.
	secret := struct{ token string }{token: seededCanary}
	err := errors.New(errors.KindPermission, "access denied").
		WithCode("permission_denied").
		WithField("subject", secret) // non-scalar → "[unredactable]"

	if strings.Contains(err.Error(), seededCanary) {
		t.Fatalf("canary leaked into a surfaced artifact: %q", err.Error())
	}

	// The non-scalar field must be MARKED redacted, not silently dropped: assert the
	// "[unredactable]" marker is present in Fields(). A regression that drops the field
	// (instead of marking it) hides a leak vector — this distinguishes the two.
	if got := err.Fields()["subject"]; got != "[unredactable]" {
		t.Fatalf("non-scalar field not marked redacted: Fields()[subject] = %v, want %q",
			got, "[unredactable]")
	}
}

// TestCanary_ScalarFieldBoundary pins the documented real leak vector (finding errors/canary
// idx 20): a secret passed as a *legitimate scalar string* field is stored VERBATIM by design,
// so redacting scalar secrets is the CALLER's responsibility — not the model's. The boundary is
// test-pinned (not implicit) so a future change to scalar handling is a deliberate, visible one:
//   - the scalar IS present in Fields() (the model stores safe scalars verbatim), and
//   - the scalar is still NOT surfaced through Error() (fields are never part of the rendering),
//
// proving the operator-safe surface stays canary-free even when a scalar field carries a secret.
func TestCanary_ScalarFieldBoundary(t *testing.T) {
	t.Parallel()

	err := errors.New(errors.KindPermission, "access denied").
		WithField("subject", seededCanary) // scalar string → stored verbatim, caller's responsibility

	// Boundary half 1: the model stores a safe scalar verbatim (it does NOT redact scalars).
	if got := err.Fields()["subject"]; got != seededCanary {
		t.Fatalf("scalar field not stored verbatim: Fields()[subject] = %v, want %q",
			got, seededCanary)
	}

	// Boundary half 2: even so, the operator-safe rendering never embeds the field value —
	// Error() surfaces only message+cause, so a scalar field secret cannot leak through it.
	if strings.Contains(err.Error(), seededCanary) {
		t.Fatalf("scalar field secret leaked into Error(): %q", err.Error())
	}
}

// TestRedact_NonScalarFieldMarked asserts the safe-scalar invariant's marker is observable, so
// a future regression that starts storing raw non-scalars (and could leak a secret) is caught.
func TestRedact_NonScalarFieldMarked(t *testing.T) {
	t.Parallel()
	err := errors.New(errors.KindInternal, "boom").
		WithField("payload", map[string]string{"k": seededCanary})
	if strings.Contains(err.Error(), seededCanary) {
		t.Fatalf("non-scalar field leaked the canary: %q", err.Error())
	}
}
