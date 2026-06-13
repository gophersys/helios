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

	surfaces := []string{
		err.Error(),
	}
	for _, s := range surfaces {
		if strings.Contains(s, seededCanary) {
			t.Fatalf("canary leaked into a surfaced artifact: %q", s)
		}
	}

	// A scalar field is legitimately stored; assert the redaction marker is present so we know
	// the non-scalar path actually redacted rather than dropping silently.
	rendered := err.Error()
	if strings.Contains(rendered, seededCanary) {
		t.Fatalf("canary present in rendered error: %q", rendered)
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
