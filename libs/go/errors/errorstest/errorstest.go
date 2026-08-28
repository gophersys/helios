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
func RequireKind(tb testing.TB, err error, want errors.Kind) {
	tb.Helper()
	got := errors.KindOf(err)
	if got != want {
		tb.Fatalf("RequireKind: KindOf(err) = %v, want %v (err: %v)", got, want, render(err))
	}
}

// RequireNoSecret fails if err.Error() or any attached Field's rendered value
// contains any of the needles. It walks the whole Unwrap chain — the canonical
// redaction-safety conformance check every consumer runs over its error paths.
func RequireNoSecret(tb testing.TB, err error, needles ...string) {
	tb.Helper()
	if err == nil {
		return
	}
	// Render of the whole chain (Error() already includes ": <cause>").
	haystacks := []string{err.Error()}
	// Walk the chain collecting EACH *errors.Error node's rendered field values:
	// a secret could sit in any node's field map, and the probe must inspect them
	// all. We unwrap node-by-node and read this node's concrete type, so errors.As
	// (which finds only the first match and re-unwraps) is deliberately not used.
	for cur := err; cur != nil; cur = unwrap(cur) {
		//nolint:errorlint // intentional node-by-node walk; errors.As would skip nodes.
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
				tb.Fatalf("RequireNoSecret: needle %q leaked into %q", needle, h)
			}
		}
	}
}

// AssertUnwrapsTo asserts the cause is reachable via errors.AsType[E] and returns
// the extracted value for further assertions.
func AssertUnwrapsTo[E error](tb testing.TB, err error) E {
	tb.Helper()
	got, ok := errors.AsType[E](err)
	if !ok {
		var zero E
		tb.Fatalf("AssertUnwrapsTo: chain does not unwrap to %T (err: %v)", zero, render(err))
	}
	return got
}

// Internal helpers follow.

func render(err error) string {
	if err == nil {
		return "<nil>"
	}
	return err.Error()
}

// unwrap advances one step along the chain, tolerating both single-cause and
// multi-cause (errors.Join) shapes; for Join it follows the first branch so the
// redaction walk visits at least one path of the tree. It switches on the Unwrap
// SHAPE the error implements — the same traversal stdlib errors.Is/As perform
// internally — so errorlint's "use errors.As" does not apply, and it returns the
// raw next link verbatim, so wrapcheck's "wrap the result" would corrupt the walk.
//
//nolint:errorlint,wrapcheck // deliberate chain-shape switch returning the raw next link.
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
