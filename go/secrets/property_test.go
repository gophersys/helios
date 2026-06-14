package secrets_test

import (
	"bytes"
	"context"
	"fmt"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS set in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a) threshold); rapid reads it directly.

// drawReferenceString draws a string that satisfies the Reference shape rule (non-empty, no
// leading/trailing/interior whitespace). It is the generator the parse/scheme invariants draw
// from so every well-formed reference shape is exercised.
func drawReferenceString(rt *rapid.T) string {
	// A token of visible, non-whitespace bytes. rapid's StringMatching keeps the corpus dense
	// around the printable, scheme-shaped forms the contract documents (vault://…, env://…, bare
	// names) while still fuzzing odd-but-valid characters.
	return rapid.StringMatching(`[A-Za-z0-9][A-Za-z0-9._/#:@%+-]{0,40}`).Draw(rt, "reference")
}

// TestProperty_ParseRoundTrips asserts the ParseReference round-trip invariant (secrets.go):
// for any well-formed reference string, ParseReference succeeds, String() reproduces the input
// verbatim, and re-parsing String() yields an EQUAL (comparable) Reference. This is the
// fingerprint-stability property of dimension (a).
func TestProperty_ParseRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in := drawReferenceString(rt)
		r, err := secrets.ParseReference(in)
		if err != nil {
			rt.Fatalf("ParseReference(%q) errored on a well-formed reference: %v", in, err)
		}
		if r.IsZero() {
			rt.Fatalf("ParseReference(%q) reported IsZero for a well-formed reference", in)
		}
		if got := r.String(); got != in {
			rt.Fatalf("String() = %q, want the exact input %q (canonical form must be verbatim)", got, in)
		}
		r2, err := secrets.ParseReference(r.String())
		if err != nil {
			rt.Fatalf("ParseReference(String()) errored: %v", err)
		}
		if r2 != r {
			rt.Fatalf("round-trip drifted: re-parsed %v != original %v", r2, r)
		}
	})
}

// TestProperty_SchemeIsPrefixBeforeSeparator asserts the Scheme() invariant (secrets.go): the
// scheme is exactly the substring before the first "://", or empty when there is none — and a
// parsed reference whose raw form contains "scheme://" reports that scheme. This pins the
// composition-root routing key the Mediator switches on.
func TestProperty_SchemeIsPrefixBeforeSeparator(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		scheme := rapid.StringMatching(`[a-z][a-z0-9+-]{0,12}`).Draw(rt, "scheme")
		path := rapid.StringMatching(`[A-Za-z0-9][A-Za-z0-9._/#-]{0,30}`).Draw(rt, "path")
		raw := scheme + "://" + path
		r, err := secrets.ParseReference(raw)
		if err != nil {
			rt.Fatalf("ParseReference(%q) errored: %v", raw, err)
		}
		if got := r.Scheme(); got != scheme {
			rt.Fatalf("Scheme() = %q, want %q (the prefix before the first %q)", got, scheme, "://")
		}
	})
}

// TestProperty_WhitespaceIsAlwaysRejected asserts the validation invariant (secrets.go): any
// string containing a leading/trailing/interior whitespace rune, or the empty string, is
// rejected with AsType[InvalidReferenceError] and returns the zero Reference. A whitespace
// reference is ambiguous in a log line / config value, so it can never be valid under any scheme.
func TestProperty_WhitespaceIsAlwaysRejected(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		base := rapid.StringMatching(`[A-Za-z0-9]{0,10}`).Draw(rt, "base")
		ws := rapid.SampledFrom([]string{" ", "\t", "\n", "\r"}).Draw(rt, "ws")
		// Insert the whitespace at a drawn position so leading, interior, and trailing cases all occur.
		pos := rapid.IntRange(0, len(base)).Draw(rt, "pos")
		in := base[:pos] + ws + base[pos:]
		r, err := secrets.ParseReference(in)
		if err == nil {
			rt.Fatalf("ParseReference(%q) accepted a whitespace-bearing reference", in)
		}
		if !is[secrets.InvalidReferenceError](err) {
			rt.Fatalf("ParseReference(%q) error not AsType[InvalidReferenceError]: %v", in, err)
		}
		if !r.IsZero() {
			rt.Fatalf("ParseReference(%q) returned a non-zero ref on error: %v", in, r)
		}
	})
}

// TestProperty_RedactionIsTotalForAnyPlaintext is the redaction fingerprint property
// (dimensions (a)+(f)): for ANY plaintext bytes, every stringification/marshaling surface of
// the minted Secret renders EXACTLY the Redacted sentinel and never contains the plaintext.
// Redaction is a property of the TYPE, so it must hold for the whole value space, not a fixture.
func TestProperty_RedactionIsTotalForAnyPlaintext(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		plaintext := rapid.SliceOfN(rapid.Byte(), 1, 64).Draw(rt, "plaintext")
		sec := secretstest.MintSecret(plaintext)
		defer sec.Zeroize()
		assertSecretRedactsToSentinel(rt, sec)
	})
}

// assertSecretRedactsToSentinel fails rt unless EVERY rendering/marshaling surface of sec reduces
// to the Redacted sentinel. Extracted from the property body so the property reads as one claim
// and stays under the cognitive-complexity ceiling; it is the reusable "redaction is total" check.
func assertSecretRedactsToSentinel(rt *rapid.T, sec *secrets.Secret) {
	// Direct string surfaces must equal the sentinel exactly.
	for name, got := range map[string]string{"String": sec.String(), "GoString": sec.GoString()} {
		if got != secrets.Redacted {
			rt.Fatalf("%s = %q, want the Redacted sentinel %q", name, got, secrets.Redacted)
		}
	}
	// Every fmt verb routes through the Format override, which writes EXACTLY the sentinel
	// regardless of verb. Equality to the fixed sentinel is the load-bearing invariant: it is
	// strictly stronger than a "plaintext-absent" substring search (fragile when the drawn bytes
	// are a substring of the sentinel text), and it proves the override fired rather than letting
	// the default %v dump the struct fields.
	for _, verb := range []string{"%s", "%v", "%+v", "%#v", "%q", "%d"} {
		if rendered := fmt.Sprintf(verb, sec); rendered != secrets.Redacted {
			rt.Fatalf("fmt %s = %q, want the Redacted sentinel %q (Format override must close every verb)", verb, rendered, secrets.Redacted)
		}
	}
	// MarshalText / MarshalJSON / TelemetryValue / LogValue all reduce to the sentinel.
	tb, err := sec.MarshalText()
	if err != nil {
		rt.Fatalf("MarshalText error = %v", err)
	}
	if string(tb) != secrets.Redacted {
		rt.Fatalf("MarshalText = %q, want Redacted", tb)
	}
	jb, err := sec.MarshalJSON()
	if err != nil {
		rt.Fatalf("MarshalJSON error = %v", err)
	}
	if string(jb) != `"`+secrets.Redacted+`"` {
		rt.Fatalf("MarshalJSON = %q, want quoted Redacted", jb)
	}
	if tv := sec.TelemetryValue(); tv != secrets.Redacted {
		rt.Fatalf("TelemetryValue() = %v, want Redacted", tv)
	}
	if lv := sec.LogValue().String(); lv != secrets.Redacted {
		rt.Fatalf("LogValue().String() = %q, want Redacted", lv)
	}
}

// TestProperty_UseExposesExactlyTheMintedBytes asserts the Use read-path fidelity property: for
// any plaintext, the ONLY legitimate read path (Use) observes exactly the minted bytes, and
// after Zeroize it always fails with AsType[ZeroizedError] for the whole value space.
func TestProperty_UseExposesExactlyTheMintedBytes(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		plaintext := rapid.SliceOfN(rapid.Byte(), 0, 64).Draw(rt, "plaintext")
		sec := secretstest.MintSecret(plaintext)

		var seen []byte
		if err := sec.Use(func(b []byte) error {
			seen = append(seen, b...)
			return nil
		}); err != nil {
			rt.Fatalf("Use error = %v", err)
		}
		if !bytes.Equal(seen, plaintext) {
			rt.Fatalf("Use saw %q, want the minted bytes %q", seen, plaintext)
		}

		sec.Zeroize()
		if err := sec.Use(func([]byte) error { return nil }); !is[secrets.ZeroizedError](err) {
			rt.Fatalf("Use after Zeroize error not AsType[ZeroizedError]: %v", err)
		}
	})
}

// TestProperty_MediatorRoutesEverySeededReference asserts the routing invariant over a fuzzed
// scheme→value table: for any seeded (scheme, name, value), the Mediator routes the explicit
// "scheme://name" reference to the adapter that owns that scheme and Use observes the seeded
// value — the property the per-scheme adapter table relies on at the composition root.
func TestProperty_MediatorRoutesEverySeededReference(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		scheme := rapid.StringMatching(`[a-z][a-z0-9]{0,8}`).Draw(rt, "scheme")
		name := rapid.StringMatching(`[A-Za-z0-9][A-Za-z0-9._/#-]{0,16}`).Draw(rt, "name")
		value := rapid.StringMatching(`[ -~]{1,32}`).Draw(rt, "value")

		ref := secrets.Ref(scheme + "://" + name)
		adapter := secretstest.New(map[string]string{ref.String(): value})
		med, err := secrets.New(
			secrets.Config{},
			secrets.Deps{Resolvers: map[string]secrets.Provider{scheme: adapter}},
		)
		if err != nil {
			rt.Fatalf("secrets.New error = %v", err)
		}

		sec, err := med.Resolve(context.Background(), ref)
		if err != nil {
			rt.Fatalf("Resolve(%q) error = %v", ref, err)
		}
		defer sec.Zeroize()
		got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
		if err != nil {
			rt.Fatalf("Use1 error = %v", err)
		}
		if got != value {
			rt.Fatalf("routed Resolve saw %q, want the seeded value %q", got, value)
		}
	})
}
