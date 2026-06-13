// Package errorstest provides deterministic builders, conformance assertions, and
// the redaction-safety probe for consumers writing table tests against the errors
// contract. There is no port to stub (errors is a pure value library), so the
// surface is builders + assertions over testing.TB.
package errorstest

import (
	"fmt"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
)

// Leaf mints a deterministic *errors.Error of the given Kind and message, so
// tests arrange inputs without importing the verb set at every call site.
func Leaf(kind errors.Kind, message string) *errors.Error {
	return errors.New(kind, message)
}

// Wrapping builds a two-level chain (outer Kind over inner) so tests can assert
// AsType/Unwrap traversal and Kind precedence/inheritance.
func Wrapping(outer errors.Kind, inner error) *errors.Error {
	return errors.Wrap(outer, "wrapped", inner)
}

// RequireKind fails the test unless errors.KindOf(err) == want, reporting the
// actual Kind and the rendered error.
func RequireKind(t testing.TB, err error, want errors.Kind) {
	t.Helper()
	got := errors.KindOf(err)
	if got != want {
		t.Fatalf("RequireKind: KindOf(err) = %v, want %v (err: %v)", got, want, render(err))
	}
}

// RequireNoSecret fails if err.Error() or any attached Field's rendered value
// contains any of the needles. It walks the whole Unwrap chain — the canonical
// redaction-safety conformance check every consumer runs over its error paths.
func RequireNoSecret(t testing.TB, err error, needles ...string) {
	t.Helper()
	if err == nil {
		return
	}
	// Render of the whole chain (Error() already includes ": <cause>").
	haystacks := []string{err.Error()}
	// Walk the chain collecting each *errors.Error's rendered field values.
	for cur := err; cur != nil; cur = unwrap(cur) {
		if e, ok := cur.(*errors.Error); ok {
			for k, v := range e.Fields() {
				haystacks = append(haystacks, k, fmt.Sprint(v))
			}
		}
	}
	for _, needle := range needles {
		if needle == "" {
			continue
		}
		for _, h := range haystacks {
			if strings.Contains(h, needle) {
				t.Fatalf("RequireNoSecret: needle %q leaked into %q", needle, h)
			}
		}
	}
}

// AssertUnwrapsTo asserts the cause is reachable via errors.AsType[E] and returns
// the extracted value for further assertions.
func AssertUnwrapsTo[E error](t testing.TB, err error) E {
	t.Helper()
	got, ok := errors.AsType[E](err)
	if !ok {
		var zero E
		t.Fatalf("AssertUnwrapsTo: chain does not unwrap to %T (err: %v)", zero, render(err))
	}
	return got
}

// --- internal helpers --------------------------------------------------------

func render(err error) string {
	if err == nil {
		return "<nil>"
	}
	return err.Error()
}

// unwrap advances one step along the chain, tolerating both single-cause and
// multi-cause (errors.Join) shapes; for Join it follows the first branch so the
// redaction walk visits at least one path of the tree.
func unwrap(err error) error {
	switch x := err.(type) {
	case interface{ Unwrap() error }:
		return x.Unwrap()
	case interface{ Unwrap() []error }:
		if errs := x.Unwrap(); len(errs) > 0 {
			return errs[0]
		}
	}
	return nil
}
