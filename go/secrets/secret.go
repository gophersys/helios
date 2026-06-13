package secrets

import (
	"fmt"
	"log/slog"
	"sync"

	"github.com/gophersys/libs/go/secrets/internal/mint"
)

// Redacted is the single sentinel every formatting/marshaling path on Secret returns.
const Redacted = "secrets.Secret(REDACTED)"

// noCopy is a zero-size sentinel that triggers go vet's copylocks analysis: a type that
// embeds it cannot be copied by value without a vet diagnostic, because the analyzer treats
// the Lock/Unlock method pair as a sync.Locker. Embedding it in Secret makes any value copy
// (which would duplicate plaintext bytes past a Zeroize) a reported error (10 §4).
type noCopy struct{}

func (*noCopy) Lock()   {}
func (*noCopy) Unlock() {}

// Secret holds secret bytes and is un-printable by construction. It is a pointer type with a
// non-copyable payload (noCopy makes `go vet` flag value copies that would duplicate bytes
// past a Zeroize). The only legitimate read path is Use; there is no Bytes() or Value().
//
// Concurrency: a Secret is NOT safe for concurrent mutation. Use is reentrant-safe for reads,
// but Zeroize must not race with Use. Treat one Secret as owned by one goroutine for its
// lifetime — which is the point-of-use scope. Zero value: not constructible by consumers;
// only adapters and secretstest mint Secrets (via an internal hook).
type Secret struct {
	_ noCopy // unexported; non-copyable payload guard

	// mu allows concurrent Use reads (RLock) while serializing Zeroize (Lock), so Use is
	// reentrant-safe for reads and Zeroize never races a read of the backing slice.
	mu        sync.RWMutex
	plaintext []byte
	spent     bool
}

// newSecret builds a Secret owning a private copy of plaintext. It is the sole constructor of
// a populated Secret and is reached only from an adapter's Resolve or, in tests, the internal
// minting hook registered below. Consumers have no path to it.
func newSecret(plaintext []byte) *Secret {
	buf := make([]byte, len(plaintext))
	copy(buf, plaintext)
	return &Secret{plaintext: buf}
}

// init installs the minting constructor into the shared internal/mint seam so secretstest can
// produce genuine, un-printable Secrets without a public constructor or //go:linkname
// (contract §3 minting note). The any return avoids an import cycle; secretstest type-asserts
// it back to *Secret.
func init() {
	mint.Register(func(plaintext []byte) any { return newSecret(plaintext) })
}

// Use grants fn the only legitimate window onto the plaintext. The slice passed to fn is
// valid ONLY for the duration of the call and is read-only by contract; fn must not retain it.
// Use returns fn's error, or a wrapped error (errors.AsType[ZeroizedError]) if the secret was
// already wiped. This is the sole read path — there is no Bytes().
func (s *Secret) Use(fn func(plaintext []byte) error) error {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.spent {
		return ZeroizedError{}
	}
	return fn(s.plaintext)
}

// Zeroize best-effort wipes the backing bytes and marks the secret spent. Idempotent. The
// idiom is `defer sec.Zeroize()` at point of use. After Zeroize, Use returns a wrapped
// ZeroizedError. Mandatory on embedded (10 §4); advisory-but-wired here.
func (s *Secret) Zeroize() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.spent {
		return
	}
	for i := range s.plaintext {
		s.plaintext[i] = 0
	}
	s.plaintext = nil
	s.spent = true
}

// String returns Redacted. A Secret is un-printable by construction.
func (s *Secret) String() string { return Redacted }

// GoString returns Redacted, defeating the %#v verb's self-describing dump.
func (s *Secret) GoString() string { return Redacted }

// Format ignores the verb and writes Redacted, so %v/%+v/%#v/%q/%d/%s all redact. It is the
// load-bearing override: fmt consults Formatter before Stringer/GoStringer, so this one method
// closes every fmt verb at once.
func (s *Secret) Format(f fmt.State, verb rune) {
	_, _ = f.Write([]byte(Redacted))
}

// MarshalText returns Redacted, so any encoding.TextMarshaler-aware encoder redacts.
func (s *Secret) MarshalText() ([]byte, error) {
	return []byte(Redacted), nil
}

// MarshalJSON returns the quoted Redacted sentinel, so encoding/json redacts.
func (s *Secret) MarshalJSON() ([]byte, error) {
	return []byte(`"` + Redacted + `"`), nil
}

// LogValue returns the Redacted sentinel, so slog (and the slog-based observability/logging
// patterns) redact. Implementing slog.LogValuer is non-negotiable (contract §6.4).
func (s *Secret) LogValue() slog.Value {
	return slog.StringValue(Redacted)
}

// TelemetryValue returns the telemetry-safe projection of a Secret — always Redacted, never
// the value. It structurally satisfies observability.Valuer (TelemetryValue() any) WITHOUT
// importing observability, so a *Secret can ride observability.Any(key, valuer) as nothing but
// its sentinel. secrets stays a leaf library (no upward dependency); Go interface satisfaction
// is implicit, so the seam needs no shared type. (observability.md Q9.)
func (s *Secret) TelemetryValue() any { return Redacted }

// Use1 is a typed convenience over Use for the common "derive exactly one value out" case
// (e.g. a signed token, an HMAC, a sealed request) without widening to a retainable accessor.
// V MUST NOT be the secret itself — the closure must transform, not copy through. It is a free
// function (not a method) because Go methods cannot carry their own type parameter.
func Use1[V any](s *Secret, fn func(plaintext []byte) (V, error)) (V, error) {
	var out V
	err := s.Use(func(plaintext []byte) error {
		v, ferr := fn(plaintext)
		if ferr != nil {
			return ferr
		}
		out = v
		return nil
	})
	if err != nil {
		var zero V
		return zero, err
	}
	return out, nil
}

// compile-time assertions: the redaction surface is wired.
var (
	_ fmt.Stringer   = (*Secret)(nil)
	_ fmt.GoStringer = (*Secret)(nil)
	_ fmt.Formatter  = (*Secret)(nil)
	_ slog.LogValuer = (*Secret)(nil)
)
