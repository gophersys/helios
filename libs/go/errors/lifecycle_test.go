//go:build lifecycle

package errors_test

import (
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/errors"
)

// TestLifecycle_CopyOnWriteIsIdempotent is the leaf-library form of the full-object-lifecycle
// conformance (ADR-0020 dimension (c)): errors holds no OS resource to Close, so its lifecycle
// invariant is copy-on-write purity — a derivation NEVER mutates its receiver, and re-deriving
// is idempotent (the analog of "double-close is a no-op"). A regression that mutated the
// receiver would be the leaf-library equivalent of an orphaned resource.
func TestLifecycle_CopyOnWriteIsIdempotent(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of the lifecycle assertion

	base := errors.New(errors.KindInvalid, "bad input")
	baseRendered := base.Error()

	// Derive twice with the same args — idempotent: the second derivation equals the first,
	// and neither mutates `base` (the "double-close is a no-op" analog).
	d1 := base.WithCode("invalid_argument").WithField("field", "name")
	d2 := base.WithCode("invalid_argument").WithField("field", "name")

	if d1.Error() != d2.Error() {
		t.Fatalf("derivation not idempotent: %q != %q", d1.Error(), d2.Error())
	}
	if base.Error() != baseRendered {
		t.Fatalf("receiver mutated by derivation: was %q, now %q", baseRendered, base.Error())
	}
	if errors.KindOf(base) != errors.KindInvalid {
		t.Fatalf("receiver Kind mutated by derivation")
	}
}
