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

// ---- Reference: ParseReference / Ref / String / Scheme / IsZero ----.

func TestParseReferenceRoundTrips(t *testing.T) {
	t.Parallel()
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
			t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
	// Reference must be usable as a map key (comparable).
	m := map[secrets.Reference]int{}
	m[secrets.Ref("a")] = 1
	m[secrets.Ref("a")]++
	if m[secrets.Ref("a")] != 2 {
		t.Errorf("Reference not usable as a stable map key: got %d", m[secrets.Ref("a")])
	}
}

func TestRefConstructorBareName(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
	defer func() {
		if recover() == nil {
			t.Error("Ref(invalid) did not panic")
		}
	}()
	_ = secrets.Ref("")
}

// ---- Secret: redaction is total ----.

// mintSecret builds a real *secrets.Secret via the test minting hook.
func mintSecret(t *testing.T, plaintext string) *secrets.Secret {
	t.Helper()
	return secretstest.MintSecret([]byte(plaintext))
}

func TestSecretRedactionTotal(t *testing.T) {
	t.Parallel()
	const plaintext = "sk-super-secret-value-1234567890"
	sec := mintSecret(t, plaintext)

	// Every stringification / marshaling path must equal Redacted and never leak. The %s/%v
	// cases deliberately route through fmt's verb machinery (not sec.String()) because the
	// point of this test is to prove the Format override redacts those verbs; gocritic's
	// redundantSprint suggestion would bypass the very code path under test.
	renders := map[string]string{
		"String":   sec.String(),
		"GoString": sec.GoString(),
		"%s":       fmt.Sprintf("%s", sec), //nolint:gocritic // exercises the Format verb path under test.
		"%v":       fmt.Sprintf("%v", sec), //nolint:gocritic // exercises the Format verb path under test.
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
	t.Parallel()
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
	t.Parallel()
	var _ slog.LogValuer = (*secrets.Secret)(nil)
}

func TestSecretTelemetryValue(t *testing.T) {
	t.Parallel()
	sec := mintSecret(t, "telemetry-secret")
	if got := sec.TelemetryValue(); got != secrets.Redacted {
		t.Errorf("TelemetryValue() = %v, want Redacted", got)
	}
	// Structurally satisfies an observability.Valuer-shaped interface without
	// secrets importing observability.
	type valuer interface{ TelemetryValue() any }
	var _ valuer = sec
}

// ---- Secret: Use / Use1 / Zeroize ----.

func TestSecretUseExposesPlaintext(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
	sec := mintSecret(t, "x")
	sentinel := fmt.Errorf("boom")
	err := sec.Use(func([]byte) error { return sentinel })
	if !errors.Is(err, sentinel) {
		t.Errorf("Use did not return fn's error: %v", err)
	}
}

func TestZeroizeWipesAndUseFails(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
	sec := mintSecret(t, "idem")
	sec.Zeroize()
	// Second call must be a no-op and not panic.
	sec.Zeroize()
	if err := sec.Use(func([]byte) error { return nil }); err == nil {
		t.Error("Use after double Zeroize returned nil, want ZeroizedError")
	}
}

func TestUseDoesNotLeakSliceAfterReturn(t *testing.T) {
	t.Parallel()
	const plaintext = "retain-attempt"
	sec := mintSecret(t, plaintext)
	var retained []byte
	if err := sec.Use(func(b []byte) error {
		retained = b // contract says fn must not retain; we verify Zeroize wipes it
		return nil
	}); err != nil {
		t.Fatalf("Use error = %v", err)
	}
	sec.Zeroize()
	if string(retained) == plaintext {
		t.Error("Zeroize did not wipe the backing bytes that fn retained")
	}
}

func TestUse1DerivesValue(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
	const plaintext = "concurrent-read"
	sec := mintSecret(t, plaintext)
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := sec.Use(func(b []byte) error {
				if string(b) != plaintext {
					t.Errorf("concurrent Use saw %q", b)
				}
				return nil
			}); err != nil {
				t.Errorf("concurrent Use error = %v", err)
			}
		}()
	}
	wg.Wait()
}

func TestUseRacesZeroizeOnSameSecret(t *testing.T) {
	t.Parallel()
	// The contract (secret.go:27, secrets.md §2) states Use is reentrant-safe for reads but
	// Zeroize must not race with Use. The impl uses sync.RWMutex (Use=RLock, Zeroize=Lock).
	// This test interleaves many concurrent Use calls with a Zeroize on the SAME minted
	// Secret under -race: it must observe EITHER the intact plaintext OR a ZeroizedError, but
	// NEVER a torn / partially-zeroed slice. If the RWMutex were weakened to a lock-free read
	// of s.spent/s.plaintext, -race would flag the data race here and this assertion would
	// catch the torn read.
	const plaintext = "race-use-vs-zeroize"
	sec := mintSecret(t, plaintext)

	var wg sync.WaitGroup
	for i := 0; i < 64; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			err := sec.Use(func(b []byte) error {
				// Use must see a consistent view: either the full plaintext (before Zeroize)
				// or nothing (after Zeroize returns ZeroizedError, so fn is never called with
				// a wiped slice). A torn read — partial/zeroed bytes while still "live" — is a
				// contract violation.
				if s := string(b); s != plaintext {
					t.Errorf("Use observed a torn/zeroed slice: %q (want intact %q or ZeroizedError)", s, plaintext)
				}
				return nil
			})
			if err != nil && !is[secrets.ZeroizedError](err) {
				t.Errorf("Use returned an unexpected error (not ZeroizedError): %v", err)
			}
		}()
	}
	// One concurrent Zeroize on the same Secret, interleaved with the readers above.
	wg.Add(1)
	go func() {
		defer wg.Done()
		sec.Zeroize()
	}()
	wg.Wait()

	// After all goroutines join, the Secret is spent and Use is permanently ZeroizedError.
	if err := sec.Use(func([]byte) error { return nil }); !is[secrets.ZeroizedError](err) {
		t.Errorf("Use after Zeroize completed error not AsType[ZeroizedError]: %v", err)
	}
}

// ---- New / Mediator routing ----.

func TestNewRequiresResolvers(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
	prov := secretstest.New(map[string]string{"k": "v"})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "test"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"test": prov}},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	// Return-concrete: New returns *secrets.Mediator. The explicit type is the assertion (it
	// proves New's static return type is the concrete *Mediator, contract §6.5); omitting it as
	// QF1011 suggests would assert nothing.
	var _ *secrets.Mediator = med //nolint:staticcheck // QF1011: the explicit type IS the return-concrete assertion.
	// And it satisfies the Provider port.
	var _ secrets.Provider = med
}

func TestMediatorRoutesByScheme(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
	// Empty DefaultScheme + schemeless reference => InvalidReferenceError.
	prov := secretstest.New(map[string]string{"x": "y"})
	med, err := secrets.New(
		secrets.Config{}, // DefaultScheme empty
		secrets.Deps{Resolvers: map[string]secrets.Provider{"": prov, "vault": prov}},
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
	t.Parallel()
	prov := secretstest.New(map[string]string{"x": "y"})
	med := newVaultMediator(t, prov)
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
	t.Parallel()
	prov := secretstest.New(map[string]string{"x": "y"})
	med := newVaultMediator(t, prov)
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
	t.Parallel()
	prov := secretstest.New(nil)
	med := newVaultMediator(t, prov)
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

func TestMediatorPropagatesDeniedError(t *testing.T) {
	t.Parallel()
	// The Mediator is a pure router (mediator.go:80): it MUST return the adapter's
	// already-typed DeniedError unchanged so callers can branch on AsType[DeniedError].
	ref := secrets.Ref("vault://locked#field")
	prov := secretstest.New(nil).FailWith(ref.String(), secrets.DeniedError{Ref: ref})
	med := newVaultMediator(t, prov)
	sec, err := med.Resolve(context.Background(), ref)
	if err == nil {
		t.Fatal("Resolve(denied) returned nil error")
	}
	if sec != nil {
		t.Error("Resolve(denied) returned non-nil Secret with an error")
	}
	if !is[secrets.DeniedError](err) {
		t.Errorf("DeniedError did not pass through the Mediator unchanged: not AsType[DeniedError]: %v", err)
	}
}

func TestMediatorPropagatesUnavailableError(t *testing.T) {
	t.Parallel()
	// Unavailable is the one retryable signal (contract §6 rationale 6): the Mediator must
	// preserve it unchanged so the caller's retry-on-Unavailable branch still fires after
	// routing. A Mediator that re-wrapped or swallowed it would defeat that branch.
	ref := secrets.Ref("vault://flaky#field")
	prov := secretstest.New(nil).FailWith(ref.String(), secrets.UnavailableError{Ref: ref})
	med := newVaultMediator(t, prov)
	sec, err := med.Resolve(context.Background(), ref)
	if err == nil {
		t.Fatal("Resolve(unavailable) returned nil error")
	}
	if sec != nil {
		t.Error("Resolve(unavailable) returned non-nil Secret with an error")
	}
	if !is[secrets.UnavailableError](err) {
		t.Errorf("UnavailableError did not pass through the Mediator unchanged: not AsType[UnavailableError]: %v", err)
	}
}

func TestMediatorConcurrentResolve(t *testing.T) {
	t.Parallel()
	prov := secretstest.New(map[string]string{"vault://k": "v"})
	med := newVaultMediator(t, prov)
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
			if uerr := sec.Use(func(b []byte) error {
				if string(b) != "v" {
					t.Errorf("concurrent Resolve saw %q", b)
				}
				return nil
			}); uerr != nil {
				t.Errorf("concurrent Use error = %v", uerr)
			}
		}()
	}
	wg.Wait()
}

// newVaultMediator builds a *secrets.Mediator with DefaultScheme "vault" routing to prov,
// failing the test if New errors. It centralizes the construction the Mediator routing tests
// share so each can focus on the behavior it asserts.
func newVaultMediator(t *testing.T, prov secrets.Provider) *secrets.Mediator {
	t.Helper()
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": prov}},
	)
	if err != nil {
		t.Fatalf("secrets.New error = %v", err)
	}
	return med
}

// ---- Error taxonomy ----.

func TestErrorTypesCarryReferenceNeverValue(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
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
