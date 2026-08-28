package errors_test

import (
	stderrors "errors"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/errors"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS set in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a) threshold); rapid reads it directly.

// allKinds is the closed, append-only Kind enumeration (errors.go). The property suite
// draws from it so every classification axis is exercised.
var allKinds = []errors.Kind{
	errors.KindUnknown, errors.KindInvalid, errors.KindNotFound, errors.KindConflict,
	errors.KindExhausted, errors.KindUnavailable, errors.KindDeadline, errors.KindCanceled,
	errors.KindUnauthenticated, errors.KindPermission, errors.KindInternal,
}

// TestProperty_KindStringStable asserts Kind.String() is total and stable: every enumerated
// Kind has a non-empty token, and the token round-trips through KindOf on a freshly minted
// error (fingerprint stability — ADR-0020 §a, rapid).
func TestProperty_KindStringStable(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		k := allKinds[rapid.IntRange(0, len(allKinds)-1).Draw(rt, "kind")]
		msg := rapid.StringMatching(`[a-z ]{0,40}`).Draw(rt, "message")
		err := errors.New(k, msg)
		if errors.KindOf(err) != k {
			rt.Fatalf("KindOf(New(%v,_)) = %v, want %v", k, errors.KindOf(err), k)
		}
		if k.String() == "" {
			rt.Fatalf("Kind(%d).String() is empty — tokens must be total", k)
		}
	})
}

// TestProperty_WrapInheritsKind asserts the Wrap inheritance invariant (errors.go): wrapping
// with KindUnknown inherits the cause's Kind, and wrapping with an explicit Kind sets it.
// This is an idempotency/round-trip invariant over the whole Kind space (ADR-0020 §a).
func TestProperty_WrapInheritsKind(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		inner := allKinds[rapid.IntRange(0, len(allKinds)-1).Draw(rt, "inner")]
		outer := allKinds[rapid.IntRange(0, len(allKinds)-1).Draw(rt, "outer")]
		cause := errors.New(inner, "inner")
		wrapped := errors.Wrap(outer, "outer", cause)
		got := errors.KindOf(wrapped)
		want := outer
		if outer == errors.KindUnknown {
			want = inner // KindUnknown inherits the cause's classification
		}
		if got != want {
			rt.Fatalf("Wrap(%v, _, New(%v,_)) Kind = %v, want %v", outer, inner, got, want)
		}
		// The chain is preserved: the cause is reachable via Is.
		if !errors.Is(wrapped, cause) {
			rt.Fatalf("Wrap lost the cause chain — errors.Is(wrapped, cause) is false")
		}
	})
}

// TestProperty_IsTypeAgreesWithAsType asserts the IsType/AsType agreement invariant
// over the whole Kind space and varied chain shapes: for any error, IsType[*Error]
// equals the ok of AsType[*Error]. Foreign-only and nil chains exercise the false
// branch; *Error chains exercise the true branch (ADR-0020 §a, rapid).
func TestProperty_IsTypeAgreesWithAsType(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		var err error
		switch rapid.IntRange(0, 2).Draw(rt, "shape") {
		case 0:
			// nil error.
		case 1:
			// foreign (non-*Error) chain.
			err = stderrors.New(rapid.StringMatching(`[a-z ]{0,20}`).Draw(rt, "foreign"))
		default:
			// *Error chain with a drawn Kind, optionally wrapping a foreign cause.
			k := allKinds[rapid.IntRange(0, len(allKinds)-1).Draw(rt, "kind")]
			msg := rapid.StringMatching(`[a-z ]{0,20}`).Draw(rt, "message")
			if rapid.Bool().Draw(rt, "wrapped") {
				err = errors.Wrap(k, msg, stderrors.New("cause"))
			} else {
				err = errors.New(k, msg)
			}
		}
		as, ok := errors.AsType[*errors.Error](err)
		if got := errors.IsType[*errors.Error](err); got != ok {
			rt.Fatalf("IsType[*Error] = %v, AsType ok = %v — must agree", got, ok)
		}
		// The extracted value rides AsType's ok: present iff ok.
		if (as != nil) != ok {
			rt.Fatalf("AsType value/ok disagree: value=%p ok=%v", as, ok)
		}
	})
}
