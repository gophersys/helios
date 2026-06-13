package secretstest

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// SeededPlaintext is the value the suite asserts is readable through Use and never leaks. It
// is fixed so the leak checks have a concrete needle; a Provider passed to RunProviderSuite
// MUST resolve `present` to exactly these bytes (e.g. New(map[string]string{present.String():
// secretstest.SeededPlaintext})).
const SeededPlaintext = "the-seeded-plaintext-value"

// RunProviderSuite asserts the Provider port contract against a freshly-constructed Provider.
// newProvider returns a Provider pre-seeded so that `present` resolves and `absent` does not.
//
// The Provider MUST resolve `present` to SeededPlaintext; the leak assertions use it as their
// needle. Each property is a self-contained subtest that builds its own Provider, so the
// subtests are independent and run in parallel.
func RunProviderSuite(t *testing.T, newProvider func() secrets.Provider, present, absent secrets.Reference) {
	t.Helper()
	t.Run("ResolveHappyPath", func(t *testing.T) {
		t.Parallel()
		assertResolveHappyPath(t, newProvider, present)
	})
	t.Run("NeverBothNonNil", func(t *testing.T) {
		t.Parallel()
		assertNeverBothNonNil(t, newProvider, present, absent)
	})
	t.Run("TypedNotFound", func(t *testing.T) {
		t.Parallel()
		assertTypedNotFound(t, newProvider, absent)
	})
	t.Run("TypedInvalidOnZeroReference", func(t *testing.T) {
		t.Parallel()
		assertInvalidOnZeroReference(t, newProvider)
	})
	t.Run("ForcedDeniedAndUnavailable", func(t *testing.T) {
		t.Parallel()
		assertForcedDeniedAndUnavailable(t, present)
	})
	t.Run("ErrorCarriesReferenceNeverValue", func(t *testing.T) {
		t.Parallel()
		assertErrorCarriesRef(t, newProvider, absent)
	})
	t.Run("UseIsTheOnlyReadPath", func(t *testing.T) {
		t.Parallel()
		assertUseIsTheOnlyReadPath(t, newProvider, present)
	})
	t.Run("RedactionIsTotal", func(t *testing.T) {
		t.Parallel()
		assertRedactionIsTotal(t, newProvider, present)
	})
	t.Run("ZeroizeIsIdempotent", func(t *testing.T) {
		t.Parallel()
		assertZeroizeIsIdempotent(t, newProvider, present)
	})
	t.Run("Independence", func(t *testing.T) {
		t.Parallel()
		assertIndependence(t, newProvider, present)
	})
	t.Run("ReferenceRoundTrips", func(t *testing.T) {
		t.Parallel()
		assertReferenceRoundTrips(t, present)
	})
}

// assertResolveHappyPath: Resolve(present) returns a non-nil *Secret and nil error.
func assertResolveHappyPath(t *testing.T, newProvider func() secrets.Provider, present secrets.Reference) {
	t.Helper()
	sec, err := newProvider().Resolve(context.Background(), present)
	if err != nil {
		t.Fatalf("Resolve(present) error = %v", err)
	}
	if sec == nil {
		t.Fatal("Resolve(present) returned a nil *Secret")
	}
	sec.Zeroize()
}

// assertNeverBothNonNil: a *Secret and an error are never both non-nil (nor both nil).
func assertNeverBothNonNil(t *testing.T, newProvider func() secrets.Provider, present, absent secrets.Reference) {
	t.Helper()
	sec, err := newProvider().Resolve(context.Background(), present)
	if (err == nil) == (sec == nil) {
		t.Errorf("present: secret/err both-set or both-nil: sec=%v err=%v", sec, err)
	}
	if sec != nil {
		sec.Zeroize()
	}
	sec2, err2 := newProvider().Resolve(context.Background(), absent)
	if err2 == nil {
		t.Fatal("Resolve(absent) returned nil error")
	}
	if sec2 != nil {
		t.Errorf("Resolve(absent) returned non-nil *Secret with an error: %v", sec2)
	}
}

// assertTypedNotFound: resolving an absent reference yields AsType[NotFoundError].
func assertTypedNotFound(t *testing.T, newProvider func() secrets.Provider, absent secrets.Reference) {
	t.Helper()
	_, err := newProvider().Resolve(context.Background(), absent)
	if !isType[secrets.NotFoundError](err) {
		t.Errorf("Resolve(absent) error not AsType[NotFoundError]: %v", err)
	}
}

// assertInvalidOnZeroReference: the zero Reference yields AsType[InvalidReferenceError].
func assertInvalidOnZeroReference(t *testing.T, newProvider func() secrets.Provider) {
	t.Helper()
	var zero secrets.Reference
	sec, err := newProvider().Resolve(context.Background(), zero)
	if err == nil {
		t.Fatal("Resolve(zero ref) returned nil error")
	}
	if sec != nil {
		t.Error("Resolve(zero ref) returned non-nil *Secret with an error")
	}
	if !isType[secrets.InvalidReferenceError](err) {
		t.Errorf("Resolve(zero ref) error not AsType[InvalidReferenceError]: %v", err)
	}
}

// assertForcedDeniedAndUnavailable: the typed denial/outage errors round-trip through AsType
// across a %w wrap — the branch-on-kind property every adapter and the Mediator rely on.
func assertForcedDeniedAndUnavailable(t *testing.T, present secrets.Reference) {
	t.Helper()
	den := fmt.Errorf("backend: %w", secrets.DeniedError{Ref: present})
	if !isType[secrets.DeniedError](den) {
		t.Errorf("DeniedError not AsType-matchable through %%w: %v", den)
	}
	una := fmt.Errorf("backend: %w", secrets.UnavailableError{Ref: present})
	if !isType[secrets.UnavailableError](una) {
		t.Errorf("UnavailableError not AsType-matchable through %%w: %v", una)
	}
}

// assertErrorCarriesRef: an error carries the reference's canonical form and never the value.
func assertErrorCarriesRef(t *testing.T, newProvider func() secrets.Provider, absent secrets.Reference) {
	t.Helper()
	_, err := newProvider().Resolve(context.Background(), absent)
	if err == nil {
		t.Fatal("Resolve(absent) returned nil error")
	}
	msg := err.Error()
	if !strings.Contains(msg, absent.String()) {
		t.Errorf("error %q does not carry the reference %q", msg, absent.String())
	}
	if strings.Contains(msg, SeededPlaintext) {
		t.Errorf("error %q leaked the seeded plaintext", msg)
	}
}

// assertUseIsTheOnlyReadPath: Use exposes the seeded bytes; Use after Zeroize is ZeroizedError.
func assertUseIsTheOnlyReadPath(t *testing.T, newProvider func() secrets.Provider, present secrets.Reference) {
	t.Helper()
	sec, err := newProvider().Resolve(context.Background(), present)
	if err != nil {
		t.Fatalf("Resolve(present) error = %v", err)
	}
	var got string
	if uerr := sec.Use(func(b []byte) error { got = string(b); return nil }); uerr != nil {
		t.Fatalf("Use error = %v", uerr)
	}
	if got != SeededPlaintext {
		t.Errorf("Use saw %q, want %q", got, SeededPlaintext)
	}
	sec.Zeroize()
	if zerr := sec.Use(func([]byte) error { return nil }); !isType[secrets.ZeroizedError](zerr) {
		t.Errorf("Use after Zeroize error not AsType[ZeroizedError]: %v", zerr)
	}
}

// assertRedactionIsTotal: every stringification/marshaling path renders Redacted, never the value.
func assertRedactionIsTotal(t *testing.T, newProvider func() secrets.Provider, present secrets.Reference) {
	t.Helper()
	sec, err := newProvider().Resolve(context.Background(), present)
	if err != nil {
		t.Fatalf("Resolve(present) error = %v", err)
	}
	defer sec.Zeroize()

	formatted := fmt.Sprintf("%s %v %+v %#v %q", sec, sec, sec, sec, sec)
	if strings.Contains(formatted, SeededPlaintext) {
		t.Errorf("fmt verbs leaked plaintext: %q", formatted)
	}
	if strings.Count(formatted, secrets.Redacted) != 5 {
		t.Errorf("fmt verbs did not all render Redacted: %q", formatted)
	}

	var buf bytes.Buffer
	slog.New(slog.NewJSONHandler(&buf, nil)).Info("m", "cred", sec)
	if strings.Contains(buf.String(), SeededPlaintext) {
		t.Errorf("slog leaked plaintext: %q", buf.String())
	}
	if !strings.Contains(buf.String(), secrets.Redacted) {
		t.Errorf("slog missing Redacted: %q", buf.String())
	}

	jb, jerr := json.Marshal(sec)
	if jerr != nil {
		t.Fatalf("json.Marshal error = %v", jerr)
	}
	if strings.Contains(string(jb), SeededPlaintext) {
		t.Errorf("json.Marshal leaked plaintext: %q", jb)
	}

	tb, terr := sec.MarshalText()
	if terr != nil {
		t.Fatalf("MarshalText error = %v", terr)
	}
	if string(tb) != secrets.Redacted {
		t.Errorf("MarshalText = %q, want Redacted", tb)
	}
}

// assertZeroizeIsIdempotent: a second Zeroize is a no-op and Use stays ZeroizedError.
func assertZeroizeIsIdempotent(t *testing.T, newProvider func() secrets.Provider, present secrets.Reference) {
	t.Helper()
	sec, err := newProvider().Resolve(context.Background(), present)
	if err != nil {
		t.Fatalf("Resolve(present) error = %v", err)
	}
	sec.Zeroize()
	sec.Zeroize() // second call must be a no-op (no panic).
	if zerr := sec.Use(func([]byte) error { return nil }); !isType[secrets.ZeroizedError](zerr) {
		t.Errorf("Use after double Zeroize error not AsType[ZeroizedError]: %v", zerr)
	}
}

// assertIndependence: two Resolves for the same ref return independent Secrets.
func assertIndependence(t *testing.T, newProvider func() secrets.Provider, present secrets.Reference) {
	t.Helper()
	p := newProvider()
	s1, err1 := p.Resolve(context.Background(), present)
	if err1 != nil {
		t.Fatalf("first Resolve error = %v", err1)
	}
	s2, err2 := p.Resolve(context.Background(), present)
	if err2 != nil {
		t.Fatalf("second Resolve error = %v", err2)
	}
	s1.Zeroize()
	var got string
	if uerr := s2.Use(func(b []byte) error { got = string(b); return nil }); uerr != nil {
		t.Fatalf("s2.Use after s1.Zeroize error = %v", uerr)
	}
	if got != SeededPlaintext {
		t.Errorf("zeroizing s1 affected s2: got %q, want %q", got, SeededPlaintext)
	}
	s2.Zeroize()
}

// assertReferenceRoundTrips: ParseReference(r.String()) reproduces r; the zero ref IsZero.
func assertReferenceRoundTrips(t *testing.T, present secrets.Reference) {
	t.Helper()
	r2, err := secrets.ParseReference(present.String())
	if err != nil {
		t.Fatalf("ParseReference(present.String()) error = %v", err)
	}
	if r2 != present {
		t.Errorf("round-trip mismatch: %v != %v", r2, present)
	}
	var zero secrets.Reference
	if !zero.IsZero() {
		t.Error("zero Reference IsZero() = false")
	}
}

// isType reports whether err's chain carries a value of type E, via the errors library's
// one-arg generic errors.AsType[E](err) (E, bool). A readability wrapper so the suite reads as
// a branch-on-kind check without a blank-identifier discard at every call site.
func isType[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}
