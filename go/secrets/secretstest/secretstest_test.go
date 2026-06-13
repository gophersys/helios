package secretstest_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

func TestZeroProviderResolvesNothing(t *testing.T) {
	t.Parallel()
	var p secretstest.Provider
	sec, err := p.Resolve(context.Background(), secrets.Ref("anything"))
	if err == nil {
		t.Fatalf("zero Provider Resolve = (%v, nil), want NotFoundError", sec)
	}
	if sec != nil {
		t.Error("zero Provider returned non-nil Secret with an error")
	}
	if !is[secrets.NotFoundError](err) {
		t.Errorf("zero Provider error not AsType[NotFoundError]: %v", err)
	}
}

func TestNewSeedsAndResolves(t *testing.T) {
	t.Parallel()
	p := secretstest.New(map[string]string{"api-key": "abc123"})
	sec := mustResolve(t, p, secrets.Ref("api-key"))
	defer sec.Zeroize()
	if got := readSecret(t, sec); got != "abc123" {
		t.Errorf("resolved plaintext = %q, want abc123", got)
	}
}

func TestNewCopiesSeedBytes(t *testing.T) {
	t.Parallel()
	// New copies the seed so a caller cannot alias it. We can only observe this
	// indirectly: independent Resolves must be unaffected by SUT-side Zeroize.
	p := secretstest.New(map[string]string{"k": "v"})
	s1 := mustResolve(t, p, secrets.Ref("k"))
	s1.Zeroize() // SUT-side wipe
	s2 := mustResolve(t, p, secrets.Ref("k"))
	defer s2.Zeroize()
	if got := readSecret(t, s2); got != "v" {
		t.Errorf("second Resolve plaintext = %q, want v (seed corrupted by SUT Zeroize)", got)
	}
}

func TestSetIsFluent(t *testing.T) {
	t.Parallel()
	p := secretstest.New(nil).Set("a", "1").Set("b", "2")
	for name, want := range map[string]string{"a": "1", "b": "2"} {
		sec := mustResolve(t, p, secrets.Ref(name))
		got := readSecret(t, sec)
		sec.Zeroize()
		if got != want {
			t.Errorf("Resolve(%q) = %q, want %q", name, got, want)
		}
	}
}

func TestSetReturnsSameProvider(t *testing.T) {
	t.Parallel()
	p := secretstest.New(nil)
	if p.Set("x", "y") != p {
		t.Error("Set did not return the same *Provider (not fluent)")
	}
}

func TestFailWithForcesError(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref("denied-key")
	p := secretstest.New(map[string]string{"denied-key": "value"}).
		FailWith("denied-key", secrets.DeniedError{Ref: ref})
	sec, err := p.Resolve(context.Background(), ref)
	if err == nil {
		t.Fatal("FailWith did not force an error")
	}
	if sec != nil {
		t.Error("forced-error Resolve returned non-nil Secret")
	}
	if !is[secrets.DeniedError](err) {
		t.Errorf("forced error not AsType[DeniedError]: %v", err)
	}
}

func TestFailWithUnavailable(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref("flaky")
	p := secretstest.New(nil).FailWith("flaky", secrets.UnavailableError{Ref: ref})
	_, err := p.Resolve(context.Background(), ref)
	if !is[secrets.UnavailableError](err) {
		t.Errorf("forced error not AsType[UnavailableError]: %v", err)
	}
}

func TestResolvedLogRecordsRefsNeverValues(t *testing.T) {
	t.Parallel()
	p := secretstest.New(map[string]string{"k1": "secret-one", "k2": "secret-two"})
	r1 := secrets.Ref("k1")
	r2 := secrets.Ref("k2")
	mustResolve(t, p, r1).Zeroize()
	mustResolve(t, p, r2).Zeroize()
	// A miss is also recorded (the request happened); it must surface NotFoundError.
	if _, err := p.Resolve(context.Background(), secrets.Ref("k3")); !is[secrets.NotFoundError](err) {
		t.Errorf("miss did not return NotFoundError: %v", err)
	}

	if len(p.Resolved) != 3 {
		t.Fatalf("Resolved log has %d entries, want 3: %v", len(p.Resolved), p.Resolved)
	}
	if p.Resolved[0] != r1 || p.Resolved[1] != r2 {
		t.Errorf("Resolved log order/content wrong: %v", p.Resolved)
	}
	// No value ever appears in the log's rendered form.
	for _, ref := range p.Resolved {
		if strings.Contains(ref.String(), "secret-") {
			t.Errorf("Resolved log entry leaked a value: %q", ref.String())
		}
	}
}

func TestProviderIndependentSecrets(t *testing.T) {
	t.Parallel()
	// Two Resolves for the same ref return independent Secrets.
	p := secretstest.New(map[string]string{"k": "v"})
	s1 := mustResolve(t, p, secrets.Ref("k"))
	s2 := mustResolve(t, p, secrets.Ref("k"))
	s1.Zeroize()
	if got := readSecret(t, s2); got != "v" {
		t.Errorf("zeroizing s1 corrupted s2: got %q, want v", got)
	}
	s2.Zeroize()
}

func TestMintSecretStandalone(t *testing.T) {
	t.Parallel()
	sec := secretstest.MintSecret([]byte("literal-bytes"))
	if sec == nil {
		t.Fatal("MintSecret returned nil")
	}
	// It is a genuine un-printable secret.
	if sec.String() != secrets.Redacted {
		t.Errorf("MintSecret().String() = %q, want Redacted", sec.String())
	}
	if got := readSecret(t, sec); got != "literal-bytes" {
		t.Errorf("MintSecret Use saw %q", got)
	}
}

func TestMintSecretCopiesInput(t *testing.T) {
	t.Parallel()
	// Mutating the caller's slice after MintSecret must not change the secret.
	in := []byte("mutable")
	sec := secretstest.MintSecret(in)
	for i := range in {
		in[i] = 'X'
	}
	got := readSecret(t, sec)
	sec.Zeroize()
	if got != "mutable" {
		t.Errorf("MintSecret aliased the input slice: got %q, want mutable", got)
	}
}

func TestAssertNotLeakedPasses(t *testing.T) {
	t.Parallel()
	rec := &recordingT{}
	secretstest.AssertNotLeaked(rec, "clean log line with no secret", "super-secret")
	if rec.failed {
		t.Errorf("AssertNotLeaked failed on a clean haystack: %q", rec.lastMsg)
	}
}

func TestAssertNotLeakedFails(t *testing.T) {
	t.Parallel()
	rec := &recordingT{}
	secretstest.AssertNotLeaked(rec, "oops the value super-secret is here", "super-secret")
	if !rec.failed {
		t.Error("AssertNotLeaked did not fail when the value leaked into the haystack")
	}
}

// recordingT is a TestingT that records failures instead of failing a real test.
type recordingT struct {
	failed  bool
	lastMsg string
}

func (r *recordingT) Helper() {}
func (r *recordingT) Errorf(format string, args ...any) {
	r.failed = true
	r.lastMsg = format
}

// is reports whether err's chain carries a value of type E, via the errors library's one-arg
// generic errors.AsType[E](err) (E, bool).
func is[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// readSecret reads sec's plaintext via the only legitimate path (Use), failing the test if Use
// errors. It centralizes the Use-and-check the tests share so each call site is a one-liner that
// still honors the checked-error contract.
func readSecret(t *testing.T, sec *secrets.Secret) string {
	t.Helper()
	var got string
	if err := sec.Use(func(b []byte) error { got = string(b); return nil }); err != nil {
		t.Fatalf("sec.Use error = %v", err)
	}
	return got
}

// mustResolve resolves ref via p, failing the test on error. Used where the resolution is setup
// for the assertion that follows, not the property under test.
func mustResolve(t *testing.T, p *secretstest.Provider, ref secrets.Reference) *secrets.Secret {
	t.Helper()
	sec, err := p.Resolve(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve(%s) error = %v", ref, err)
	}
	return sec
}

// Compile-time: *testing.T satisfies secretstest.TestingT.
var _ secretstest.TestingT = (*testing.T)(nil)

// Compile-time: the fake satisfies the port.
var _ secrets.Provider = (*secretstest.Provider)(nil)
