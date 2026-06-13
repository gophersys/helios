package secrets_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// ---- Reference: ParseReference / Ref / String / Scheme / IsZero ----

func TestParseReferenceRoundTrips(t *testing.T) {
	cases := []struct {
		in     string
		scheme string
	}{
		{"vault://eden/connectors/github#token", "vault"},
		{"env://ANTHROPIC_API_KEY", "env"},
		{"keychain://eden/anthropic", "keychain"},
		{"anthropic-api-key", ""}, // bare name, implicit scheme
	}
	for _, tc := range cases {
		t.Run(tc.in, func(t *testing.T) {
			r, err := secrets.ParseReference(tc.in)
			if err != nil {
				t.Fatalf("ParseReference(%q) error = %v", tc.in, err)
			}
			if got := r.String(); got != tc.in {
				t.Errorf("String() = %q, want %q", got, tc.in)
			}
			if got := r.Scheme(); got != tc.scheme {
				t.Errorf("Scheme() = %q, want %q", got, tc.scheme)
			}
			if r.IsZero() {
				t.Errorf("IsZero() = true for a well-formed reference %q", tc.in)
			}
			// ParseReference(r.String()) reproduces r (conformance: round-trip).
			r2, err := secrets.ParseReference(r.String())
			if err != nil {
				t.Fatalf("ParseReference(String()) error = %v", err)
			}
			if r2 != r {
				t.Errorf("round-trip mismatch: %v != %v", r2, r)
			}
		})
	}
}

func TestParseReferenceRejectsMalformed(t *testing.T) {
	// Empty string and whitespace-only cannot be a valid Reference under any scheme.
	for _, in := range []string{"", "   ", "\t"} {
		r, err := secrets.ParseReference(in)
		if err == nil {
			t.Fatalf("ParseReference(%q) = (%v, nil), want error", in, r)
		}
		if !r.IsZero() {
			t.Errorf("ParseReference(%q) returned non-zero ref on error: %v", in, r)
		}
		if !is[secrets.InvalidReferenceError](err) {
			t.Errorf("ParseReference(%q) error not AsType[InvalidReferenceError]: %v", in, err)
		}
	}
}

func TestZeroReference(t *testing.T) {
	var z secrets.Reference
	if !z.IsZero() {
		t.Error("zero Reference IsZero() = false, want true")
	}
	if z.Scheme() != "" {
		t.Errorf("zero Reference Scheme() = %q, want empty", z.Scheme())
	}
	if z.String() != "" {
		t.Errorf("zero Reference String() = %q, want empty", z.String())
	}
}

func TestReferenceIsComparableMapKey(t *testing.T) {
	// Reference must be usable as a map key (comparable).
	m := map[secrets.Reference]int{}
	m[secrets.Ref("a")] = 1
	m[secrets.Ref("a")]++
	if m[secrets.Ref("a")] != 2 {
		t.Errorf("Reference not usable as a stable map key: got %d", m[secrets.Ref("a")])
	}
}

func TestRefConstructorBareName(t *testing.T) {
	r := secrets.Ref("anthropic-api-key")
	if r.IsZero() {
		t.Fatal("Ref(valid name) produced zero reference")
	}
	if r.String() != "anthropic-api-key" {
		t.Errorf("Ref().String() = %q", r.String())
	}
	if r.Scheme() != "" {
		t.Errorf("Ref() Scheme() = %q, want empty (DefaultScheme applies)", r.Scheme())
	}
}

func TestRefPanicsOnImpossibleName(t *testing.T) {
	defer func() {
		if recover() == nil {
			t.Error("Ref(invalid) did not panic")
		}
	}()
	_ = secrets.Ref("")
}

// ---- Secret: redaction is total ----

// mintSecret builds a real *secrets.Secret via the test minting hook.
func mintSecret(t *testing.T, plaintext string) *secrets.Secret {
	t.Helper()
	return secretstest.MintSecret([]byte(plaintext))
}

func TestSecretRedactionTotal(t *testing.T) {
	const plaintext = "sk-super-secret-value-1234567890"
	sec := mintSecret(t, plaintext)

	// Every stringification / marshaling path must equal Redacted and never leak.
	renders := map[string]string{
		"String":   sec.String(),
		"GoString": sec.GoString(),
		"%s":       fmt.Sprintf("%s", sec),
		"%v":       fmt.Sprintf("%v", sec),
		"%+v":      fmt.Sprintf("%+v", sec),
		"%#v":      fmt.Sprintf("%#v", sec),
		"%q":       fmt.Sprintf("%q", sec),
		"%d":       fmt.Sprintf("%d", sec), // wrong verb still redacts
	}
	for name, got := range renders {
		if strings.Contains(got, plaintext) {
			t.Errorf("%s leaked plaintext: %q", name, got)
		}
	}
	for _, name := range []string{"String", "GoString", "%s", "%v", "%+v", "%#v", "%d"} {
		if renders[name] != secrets.Redacted {
			t.Errorf("%s = %q, want Redacted %q", name, renders[name], secrets.Redacted)
		}
	}

	// MarshalText.
	tb, err := sec.MarshalText()
	if err != nil {
		t.Fatalf("MarshalText error = %v", err)
	}
	if string(tb) != secrets.Redacted {
		t.Errorf("MarshalText = %q, want %q", tb, secrets.Redacted)
	}

	// MarshalJSON / encoding/json.
	jb, err := sec.MarshalJSON()
	if err != nil {
		t.Fatalf("MarshalJSON error = %v", err)
	}
	if string(jb) != `"`+secrets.Redacted+`"` {
		t.Errorf("MarshalJSON = %q, want quoted Redacted", jb)
	}
	enc, err := json.Marshal(sec)
	if err != nil {
		t.Fatalf("json.Marshal error = %v", err)
	}
	if strings.Contains(string(enc), plaintext) {
		t.Errorf("json.Marshal leaked plaintext: %q", enc)
	}
	if string(enc) != `"`+secrets.Redacted+`"` {
		t.Errorf("json.Marshal = %q, want quoted Redacted", enc)
	}

	// json.Marshal of a struct embedding the secret.
	type wrapper struct {
		Key *secrets.Secret `json:"key"`
	}
	wb, err := json.Marshal(wrapper{Key: sec})
	if err != nil {
		t.Fatalf("json.Marshal(wrapper) error = %v", err)
	}
	if strings.Contains(string(wb), plaintext) {
		t.Errorf("json.Marshal(wrapper) leaked plaintext: %q", wb)
	}
}

func TestSecretSlogRedaction(t *testing.T) {
	const plaintext = "slog-secret-abcdef"
	sec := mintSecret(t, plaintext)

	var buf bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&buf, nil))
	logger.Info("call", "credential", sec)
	out := buf.String()
	if strings.Contains(out, plaintext) {
		t.Errorf("slog leaked plaintext: %q", out)
	}
	if !strings.Contains(out, secrets.Redacted) {
		t.Errorf("slog output missing Redacted sentinel: %q", out)
	}

	// LogValue directly.
	lv := sec.LogValue()
	if lv.String() != secrets.Redacted {
		t.Errorf("LogValue().String() = %q, want Redacted", lv.String())
	}
}

func TestSecretImplementsSlogLogValuer(t *testing.T) {
	var _ slog.LogValuer = (*secrets.Secret)(nil)
}

func TestSecretTelemetryValue(t *testing.T) {
	sec := mintSecret(t, "telemetry-secret")
	if got := sec.TelemetryValue(); got != secrets.Redacted {
		t.Errorf("TelemetryValue() = %v, want Redacted", got)
	}
	// Structurally satisfies an observability.Valuer-shaped interface without
	// secrets importing observability.
	type valuer interface{ TelemetryValue() any }
	var _ valuer = sec
}

// ---- Secret: Use / Use1 / Zeroize ----

func TestSecretUseExposesPlaintext(t *testing.T) {
	const plaintext = "use-me-once"
	sec := mintSecret(t, plaintext)

	var seen string
	err := sec.Use(func(b []byte) error {
		seen = string(b)
		return nil
	})
	if err != nil {
		t.Fatalf("Use error = %v", err)
	}
	if seen != plaintext {
		t.Errorf("Use saw %q, want %q", seen, plaintext)
	}
}

func TestSecretUseReturnsFnError(t *testing.T) {
	sec := mintSecret(t, "x")
	sentinel := fmt.Errorf("boom")
	err := sec.Use(func([]byte) error { return sentinel })
	if !errors.Is(err, sentinel) {
		t.Errorf("Use did not return fn's error: %v", err)
	}
}

func TestZeroizeWipesAndUseFails(t *testing.T) {
	const plaintext = "zeroize-me"
	sec := mintSecret(t, plaintext)
	sec.Zeroize()

	err := sec.Use(func([]byte) error {
		t.Error("fn called after Zeroize")
		return nil
	})
	if err == nil {
		t.Fatal("Use after Zeroize returned nil error")
	}
	if !is[secrets.ZeroizedError](err) {
		t.Errorf("Use-after-Zeroize error not AsType[ZeroizedError]: %v", err)
	}
}

func TestZeroizeIsIdempotent(t *testing.T) {
	sec := mintSecret(t, "idem")
	sec.Zeroize()
	// Second call must be a no-op and not panic.
	sec.Zeroize()
	if err := sec.Use(func([]byte) error { return nil }); err == nil {
		t.Error("Use after double Zeroize returned nil, want ZeroizedError")
	}
}

func TestUseDoesNotLeakSliceAfterReturn(t *testing.T) {
	const plaintext = "retain-attempt"
	sec := mintSecret(t, plaintext)
	var retained []byte
	_ = sec.Use(func(b []byte) error {
		retained = b // contract says fn must not retain; we verify Zeroize wipes it
		return nil
	})
	sec.Zeroize()
	if string(retained) == plaintext {
		t.Error("Zeroize did not wipe the backing bytes that fn retained")
	}
}

func TestUse1DerivesValue(t *testing.T) {
	const plaintext = "derive-from-me"
	sec := mintSecret(t, plaintext)
	n, err := secrets.Use1(sec, func(b []byte) (int, error) {
		return len(b), nil
	})
	if err != nil {
		t.Fatalf("Use1 error = %v", err)
	}
	if n != len(plaintext) {
		t.Errorf("Use1 returned %d, want %d", n, len(plaintext))
	}
}

func TestUse1AfterZeroize(t *testing.T) {
	sec := mintSecret(t, "x")
	sec.Zeroize()
	v, err := secrets.Use1(sec, func(b []byte) (string, error) {
		return string(b), nil
	})
	if !is[secrets.ZeroizedError](err) {
		t.Errorf("Use1 after Zeroize error not AsType[ZeroizedError]: %v", err)
	}
	if v != "" {
		t.Errorf("Use1 after Zeroize returned non-zero value %q", v)
	}
}

func TestUse1PropagatesFnError(t *testing.T) {
	sec := mintSecret(t, "x")
	sentinel := fmt.Errorf("derive failed")
	v, err := secrets.Use1(sec, func([]byte) (int, error) {
		return 42, sentinel
	})
	if !errors.Is(err, sentinel) {
		t.Errorf("Use1 did not return fn's error: %v", err)
	}
	if v != 0 {
		t.Errorf("Use1 on fn error returned %d, want zero value", v)
	}
}

func TestUseReentrantReads(t *testing.T) {
	const plaintext = "concurrent-read"
	sec := mintSecret(t, plaintext)
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = sec.Use(func(b []byte) error {
				if string(b) != plaintext {
					t.Errorf("concurrent Use saw %q", b)
				}
				return nil
			})
		}()
	}
	wg.Wait()
}

// ---- New / Mediator routing ----

func TestNewRequiresResolvers(t *testing.T) {
	_, err := secrets.New(secrets.Config{}, secrets.Deps{})
	if err == nil {
		t.Fatal("New with no resolvers returned nil error")
	}
	_, err = secrets.New(secrets.Config{DefaultScheme: "vault"}, secrets.Deps{Resolvers: map[string]secrets.Provider{}})
	if err == nil {
		t.Fatal("New with empty resolvers map returned nil error")
	}
}

func TestNewReturnsConcreteMediator(t *testing.T) {
	prov := secretstest.New(map[string]string{"k": "v"})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "test"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"test": prov}},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	// Return-concrete: New returns *secrets.Mediator.
	var _ *secrets.Mediator = med
	// And it satisfies the Provider port.
	var _ secrets.Provider = med
}

func TestMediatorRoutesByScheme(t *testing.T) {
	vault := secretstest.New(map[string]string{"vault://db#password": "vault-pw"})
	env := secretstest.New(map[string]string{"env://API": "env-key"})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": vault, "env": env}},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	ctx := context.Background()

	vref := secrets.Ref("vault://db#password")
	sec, err := med.Resolve(ctx, vref)
	if err != nil {
		t.Fatalf("Resolve(vault) error = %v", err)
	}
	mustUse(t, sec, "vault-pw")

	eref := secrets.Ref("env://API")
	sec2, err := med.Resolve(ctx, eref)
	if err != nil {
		t.Fatalf("Resolve(env) error = %v", err)
	}
	mustUse(t, sec2, "env-key")
}

func TestMediatorAppliesDefaultScheme(t *testing.T) {
	// A schemeless reference routes through DefaultScheme.
	vault := secretstest.New(map[string]string{"anthropic-api-key": "the-key"})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": vault}},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	sec, err := med.Resolve(context.Background(), secrets.Ref("anthropic-api-key"))
	if err != nil {
		t.Fatalf("Resolve(bare) error = %v", err)
	}
	mustUse(t, sec, "the-key")
}

func TestMediatorSchemelessNoDefaultIsInvalid(t *testing.T) {
	// Empty DefaultScheme + schemeless reference => InvalidReferenceError.
	any := secretstest.New(map[string]string{"x": "y"})
	med, err := secrets.New(
		secrets.Config{}, // DefaultScheme empty
		secrets.Deps{Resolvers: map[string]secrets.Provider{"": any, "vault": any}},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	sec, err := med.Resolve(context.Background(), secrets.Ref("bare-name"))
	if err == nil {
		t.Fatalf("Resolve(schemeless, no default) = (%v, nil), want InvalidReferenceError", sec)
	}
	if sec != nil {
		t.Error("Resolve returned non-nil Secret with an error")
	}
	if !is[secrets.InvalidReferenceError](err) {
		t.Errorf("error not AsType[InvalidReferenceError]: %v", err)
	}
}

func TestMediatorZeroReferenceIsInvalid(t *testing.T) {
	prov := secretstest.New(map[string]string{"x": "y"})
	med, _ := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": prov}},
	)
	var zero secrets.Reference
	sec, err := med.Resolve(context.Background(), zero)
	if err == nil {
		t.Fatal("Resolve(zero ref) returned nil error")
	}
	if sec != nil {
		t.Error("Resolve(zero ref) returned non-nil Secret with an error")
	}
	if !is[secrets.InvalidReferenceError](err) {
		t.Errorf("error not AsType[InvalidReferenceError]: %v", err)
	}
}

func TestMediatorUnknownSchemeIsInvalid(t *testing.T) {
	prov := secretstest.New(map[string]string{"x": "y"})
	med, _ := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": prov}},
	)
	// A scheme with no adapter bound.
	sec, err := med.Resolve(context.Background(), secrets.Ref("keychain://thing"))
	if err == nil {
		t.Fatal("Resolve(unbound scheme) returned nil error")
	}
	if sec != nil {
		t.Error("Resolve(unbound scheme) returned non-nil Secret with an error")
	}
	if !is[secrets.InvalidReferenceError](err) {
		t.Errorf("error not AsType[InvalidReferenceError]: %v", err)
	}
}

func TestMediatorPropagatesAdapterError(t *testing.T) {
	prov := secretstest.New(nil)
	med, _ := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": prov}},
	)
	// Unseeded name -> NotFoundError from the adapter, routed through the Mediator.
	sec, err := med.Resolve(context.Background(), secrets.Ref("missing"))
	if err == nil {
		t.Fatal("Resolve(missing) returned nil error")
	}
	if sec != nil {
		t.Error("Resolve(missing) returned non-nil Secret with an error")
	}
	if !is[secrets.NotFoundError](err) {
		t.Errorf("error not AsType[NotFoundError]: %v", err)
	}
}

func TestMediatorConcurrentResolve(t *testing.T) {
	prov := secretstest.New(map[string]string{"vault://k": "v"})
	med, _ := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": prov}},
	)
	ref := secrets.Ref("vault://k")
	var wg sync.WaitGroup
	for i := 0; i < 32; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			sec, err := med.Resolve(context.Background(), ref)
			if err != nil {
				t.Errorf("concurrent Resolve error = %v", err)
				return
			}
			defer sec.Zeroize()
			_ = sec.Use(func(b []byte) error {
				if string(b) != "v" {
					t.Errorf("concurrent Resolve saw %q", b)
				}
				return nil
			})
		}()
	}
	wg.Wait()
}

// ---- Error taxonomy ----

func TestErrorTypesCarryReferenceNeverValue(t *testing.T) {
	ref := secrets.Ref("vault://eden/secret#field")
	const plaintext = "the-actual-secret"
	cases := []error{
		secrets.InvalidReferenceError{Ref: ref},
		secrets.NotFoundError{Ref: ref},
		secrets.DeniedError{Ref: ref},
		secrets.UnavailableError{Ref: ref},
	}
	for _, e := range cases {
		msg := e.Error()
		if !strings.Contains(msg, ref.String()) {
			t.Errorf("%T.Error() = %q, missing reference %q", e, msg, ref.String())
		}
		if strings.Contains(msg, plaintext) {
			t.Errorf("%T.Error() leaked a value: %q", e, msg)
		}
	}
	// ZeroizedError carries no reference and is non-empty.
	if (secrets.ZeroizedError{}).Error() == "" {
		t.Error("ZeroizedError.Error() is empty")
	}
}

func TestErrorTypesAreDistinctViaAsType(t *testing.T) {
	ref := secrets.Ref("x")
	wrapped := fmt.Errorf("context: %w", secrets.NotFoundError{Ref: ref})

	if !is[secrets.NotFoundError](wrapped) {
		t.Error("AsType[NotFoundError] failed through %w wrap")
	}
	if is[secrets.DeniedError](wrapped) {
		t.Error("AsType[DeniedError] matched a NotFoundError")
	}
}

// mustUse asserts the secret's plaintext equals want, then zeroizes.
func mustUse(t *testing.T, sec *secrets.Secret, want string) {
	t.Helper()
	if sec == nil {
		t.Fatal("nil secret")
	}
	defer sec.Zeroize()
	err := sec.Use(func(b []byte) error {
		if string(b) != want {
			t.Errorf("Use saw %q, want %q", b, want)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("Use error = %v", err)
	}
}

// is reports whether err's chain carries a value of type E, via the errors library's one-arg
// generic errors.AsType[E](err) (E, bool).
func is[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}
