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
	p := secretstest.New(map[string]string{"api-key": "abc123"})
	sec, err := p.Resolve(context.Background(), secrets.Ref("api-key"))
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	defer sec.Zeroize()
	var got string
	_ = sec.Use(func(b []byte) error { got = string(b); return nil })
	if got != "abc123" {
		t.Errorf("resolved plaintext = %q, want abc123", got)
	}
}

func TestNewCopiesSeedBytes(t *testing.T) {
	// New copies the seed so a caller cannot alias it. We can only observe this
	// indirectly: independent Resolves must be unaffected by SUT-side Zeroize.
	p := secretstest.New(map[string]string{"k": "v"})
	s1, _ := p.Resolve(context.Background(), secrets.Ref("k"))
	s1.Zeroize() // SUT-side wipe
	s2, err := p.Resolve(context.Background(), secrets.Ref("k"))
	if err != nil {
		t.Fatalf("second Resolve error = %v", err)
	}
	defer s2.Zeroize()
	var got string
	_ = s2.Use(func(b []byte) error { got = string(b); return nil })
	if got != "v" {
		t.Errorf("second Resolve plaintext = %q, want v (seed corrupted by SUT Zeroize)", got)
	}
}

func TestSetIsFluent(t *testing.T) {
	p := secretstest.New(nil).Set("a", "1").Set("b", "2")
	for name, want := range map[string]string{"a": "1", "b": "2"} {
		sec, err := p.Resolve(context.Background(), secrets.Ref(name))
		if err != nil {
			t.Fatalf("Resolve(%q) error = %v", name, err)
		}
		var got string
		_ = sec.Use(func(b []byte) error { got = string(b); return nil })
		sec.Zeroize()
		if got != want {
			t.Errorf("Resolve(%q) = %q, want %q", name, got, want)
		}
	}
}

func TestSetReturnsSameProvider(t *testing.T) {
	p := secretstest.New(nil)
	if p.Set("x", "y") != p {
		t.Error("Set did not return the same *Provider (not fluent)")
	}
}

func TestFailWithForcesError(t *testing.T) {
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
	ref := secrets.Ref("flaky")
	p := secretstest.New(nil).FailWith("flaky", secrets.UnavailableError{Ref: ref})
	_, err := p.Resolve(context.Background(), ref)
	if !is[secrets.UnavailableError](err) {
		t.Errorf("forced error not AsType[UnavailableError]: %v", err)
	}
}

func TestResolvedLogRecordsRefsNeverValues(t *testing.T) {
	p := secretstest.New(map[string]string{"k1": "secret-one", "k2": "secret-two"})
	ctx := context.Background()
	r1 := secrets.Ref("k1")
	r2 := secrets.Ref("k2")
	s1, _ := p.Resolve(ctx, r1)
	s1.Zeroize()
	s2, _ := p.Resolve(ctx, r2)
	s2.Zeroize()
	// A miss is also recorded (the request happened).
	_, _ = p.Resolve(ctx, secrets.Ref("k3"))

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
	// Two Resolves for the same ref return independent Secrets.
	p := secretstest.New(map[string]string{"k": "v"})
	ctx := context.Background()
	s1, _ := p.Resolve(ctx, secrets.Ref("k"))
	s2, _ := p.Resolve(ctx, secrets.Ref("k"))
	s1.Zeroize()
	var got string
	err := s2.Use(func(b []byte) error { got = string(b); return nil })
	if err != nil {
		t.Fatalf("s2.Use after s1.Zeroize error = %v", err)
	}
	if got != "v" {
		t.Errorf("zeroizing s1 corrupted s2: got %q, want v", got)
	}
	s2.Zeroize()
}

func TestMintSecretStandalone(t *testing.T) {
	sec := secretstest.MintSecret([]byte("literal-bytes"))
	if sec == nil {
		t.Fatal("MintSecret returned nil")
	}
	// It is a genuine un-printable secret.
	if sec.String() != secrets.Redacted {
		t.Errorf("MintSecret().String() = %q, want Redacted", sec.String())
	}
	var got string
	_ = sec.Use(func(b []byte) error { got = string(b); return nil })
	if got != "literal-bytes" {
		t.Errorf("MintSecret Use saw %q", got)
	}
}

func TestMintSecretCopiesInput(t *testing.T) {
	// Mutating the caller's slice after MintSecret must not change the secret.
	in := []byte("mutable")
	sec := secretstest.MintSecret(in)
	for i := range in {
		in[i] = 'X'
	}
	var got string
	_ = sec.Use(func(b []byte) error { got = string(b); return nil })
	sec.Zeroize()
	if got != "mutable" {
		t.Errorf("MintSecret aliased the input slice: got %q, want mutable", got)
	}
}

func TestAssertNotLeakedPasses(t *testing.T) {
	rec := &recordingT{}
	secretstest.AssertNotLeaked(rec, "clean log line with no secret", "super-secret")
	if rec.failed {
		t.Errorf("AssertNotLeaked failed on a clean haystack: %q", rec.lastMsg)
	}
}

func TestAssertNotLeakedFails(t *testing.T) {
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

// Compile-time: *testing.T satisfies secretstest.TestingT.
var _ secretstest.TestingT = (*testing.T)(nil)

// Compile-time: the fake satisfies the port.
var _ secrets.Provider = (*secretstest.Provider)(nil)
