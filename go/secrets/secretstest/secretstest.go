// Package secretstest provides the canonical in-memory fake Provider and a constructor for
// test Secrets, so consumers never hand-roll a fake that breaks the un-printable invariant.
// It mints genuine, real secrets.Secret values via an internal hook the library shares only
// with this package — the fake weakens the SOURCE of bytes, never the type.
package secretstest

import (
	"context"
	"strings"
	"sync"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/internal/mint"
)

// Provider is a deterministic, in-memory secrets.Provider for tests. Zero value resolves
// nothing (every ref → NotFoundError), so tests opt in explicitly. Deterministic; no clock,
// no I/O. Safe for concurrent use.
type Provider struct {
	// Resolved is an append-only log of the references asked for — refs only, never values —
	// for "was this credential requested?" assertions.
	Resolved []secrets.Reference

	mu       sync.Mutex
	seed     map[string][]byte
	failures map[string]error
}

// New returns a fake seeded from name→plaintext. It copies the bytes, so callers cannot alias
// the seed; each Resolve returns an independent Secret so a SUT-side Zeroize cannot corrupt it.
func New(seed map[string]string) *Provider {
	p := &Provider{
		seed:     make(map[string][]byte, len(seed)),
		failures: make(map[string]error),
	}
	for name, plaintext := range seed {
		p.seed[name] = []byte(plaintext) // []byte() allocates a fresh copy
	}
	return p
}

// Set seeds (or overrides) one reference. Fluent for table tests.
func (p *Provider) Set(name, plaintext string) *Provider {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.seed == nil {
		p.seed = make(map[string][]byte)
	}
	p.seed[name] = []byte(plaintext)
	return p
}

// FailWith forces Resolve(ref) to return err — pass a secrets error value, e.g.
// secrets.DeniedError{Ref: ...} or secrets.UnavailableError{Ref: ...}.
func (p *Provider) FailWith(name string, err error) *Provider {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.failures == nil {
		p.failures = make(map[string]error)
	}
	p.failures[name] = err
	return p
}

// Resolve implements secrets.Provider. It records ref, then returns a fresh, real,
// un-printable *secrets.Secret (via the package's internal test hook) or the forced error.
func (p *Provider) Resolve(ctx context.Context, ref secrets.Reference) (*secrets.Secret, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.Resolved = append(p.Resolved, ref)

	// The zero Reference is invalid at the port level (contract §4): every Provider rejects it
	// with InvalidReferenceError, before any seed/failure lookup.
	if ref.IsZero() {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}

	name := ref.String()
	if err, ok := p.failures[name]; ok {
		return nil, err
	}
	plaintext, ok := p.seed[name]
	if !ok {
		return nil, secrets.NotFoundError{Ref: ref}
	}
	// Mint an INDEPENDENT secret from a copy: a SUT-side Zeroize must not corrupt the seed or
	// any other resolved Secret. mint copies internally; the seed slice itself is never handed out.
	return MintSecret(plaintext), nil
}

// MintSecret builds a standalone, real *secrets.Secret from literal bytes without a Provider —
// for unit tests of code that consumes a Secret directly. It is the only place outside an
// adapter that can produce a Secret, and it produces a genuine un-printable one.
func MintSecret(plaintext []byte) *secrets.Secret {
	// The hook is registered by the secrets package's init with a constructor that always
	// returns *secrets.Secret; the comma-ok guard turns an impossible registration mismatch
	// into a clear panic instead of errcheck's flagged single-value assertion.
	sec, ok := mint.Hook()(plaintext).(*secrets.Secret)
	if !ok {
		panic("secretstest: minting hook returned a non-*secrets.Secret value")
	}
	return sec
}

// AssertNotLeaked fails t if value appears verbatim in haystack (a captured log buffer or
// rendered transcript) — giving the redaction guarantee a runnable assertion.
func AssertNotLeaked(t TestingT, haystack, value string) {
	t.Helper()
	if value == "" {
		return
	}
	if strings.Contains(haystack, value) {
		t.Errorf("secret value leaked: %q appears verbatim in the captured output", value)
	}
}

// TestingT is the minimal testing surface AssertNotLeaked needs (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}
