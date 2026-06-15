package ompadapter

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// MustNewForTest builds the adapter on the canonical New(configuration) (*Adapter, error)
// spine and fails the test on a (today impossible) construction error, so a black-box test
// drives the real constructor without repeating the error check at every call site.
//
//nolint:gocritic // Config is the frozen copyable configuration; the test mirrors the by-value seam.
func MustNewForTest(t *testing.T, configuration Config) *Adapter {
	t.Helper()
	adapter, err := New(configuration)
	if err != nil {
		t.Fatalf("ompadapter.New: %v", err)
	}
	return adapter
}

// NormalizeLineForTest exposes the unexported omp json normalizer (a FRESH one per call) to
// the single-line black-box tests (unknown/malformed type handling). It is compiled only in
// tests, so it is not part of the public surface.
func NormalizeLineForTest(line []byte) []agentsession.Event {
	return newNormalizer().normalize(line)
}

// StreamNormalizerForTest returns a stateful per-stream normalizer (the same one the live
// conn drives) so a fixture test threads model attribution and the terminal aggregate across
// lines exactly as a real session does.
func StreamNormalizerForTest() func(line []byte) []agentsession.Event {
	n := newNormalizer()
	return n.normalize
}

// BuildArgumentsForTest exposes the pure arg builder to the black-box tests.
//
//nolint:gocritic // contract §2/§3: Spec is the frozen copyable session input; the test mirrors the port's by-value seam.
func BuildArgumentsForTest(spec agentsession.Spec, route agentsession.Route) []string {
	return buildArguments(spec, route)
}

// ChildEnvironmentForTest exposes the pure child-env builder (scrub + inject) to the
// black-box credential-seam tests, so the precedence-trap defense is runnable without a real
// Secret or process.
func ChildEnvironmentForTest(base []string, envName, key string) []string {
	return childEnvironment(base, envName, key)
}

// InjectEnvironmentForTest exposes the REAL credential injection seam (resolve the seeded
// secrets.Secret at Secret.Use, scrub the inherited credential keys, land the plaintext on
// exactly the OpenRouter env var) to the canary redaction-property test, so the seeded key is
// threaded through the production injection closure — not a re-implementation — when asserting
// it never leaks onto a returned error and lands on EXACTLY one env entry. No process is
// spawned; only the assembled child-env []string (or an error) escapes.
func InjectEnvironmentForTest(base []string, cred agentsession.InjectedCredential) ([]string, error) {
	return injectEnvironment(base, cred)
}
