package ompadapter

import (
	"io"
	"testing"
	"time"

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

// RPCConnForTest builds the REAL `--mode rpc` HarnessConn over an INJECTED transport instead of
// a spawned process: fromOMP supplies the NDJSON frames omp writes on ITS stdout, and every frame
// the conn writes to omp's stdin is written to toOMP. The returned conn is already pumping —
// Spawn adds only the child process and its two pipes on top of it — so the whole handshake /
// host-tool / extension-UI plane is provable in the fast unit lane with NO process.
//
// toOMP is a WriteCloser because the stdin EOF is load-bearing rather than incidental: closing it
// is what makes omp reject its pending extension-UI and host-tool requests, drain the accepted
// commands, dispose the session and exit 0. Compiled only in tests.
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable session input and the seam returns the frozen HarnessConn port — exactly the shapes Spawn takes and returns.
func RPCConnForTest(spec agentsession.Spec, fromOMP io.Reader, toOMP io.WriteCloser) agentsession.HarnessConn {
	return newRPCConn(spec, fromOMP, toOMP)
}

// RPCConnWithFallbackForTest builds the rpc conn with an explicit deny-on-timeout fallback: when
// a surfaced permission dialog is not resolved through the library within `fallback`, the adapter
// answers Deny itself so omp's timerless `select` (rpc-mode.ts:640) cannot stall the turn forever.
// The test injects a short window; production uses its own default. Compiled only in tests.
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable input and the seam returns the frozen HarnessConn port — the shapes Spawn takes and returns.
func RPCConnWithFallbackForTest(spec agentsession.Spec, fromOMP io.Reader, toOMP io.WriteCloser, fallback time.Duration) agentsession.HarnessConn {
	return newRPCConnWithFallback(spec, fromOMP, toOMP, fallback)
}

// VerifyOmpBinaryForTest exposes the pure binary-identity classifier: given the `--version` line a
// candidate binary printed, it reports whether that binary is the omp CODING AGENT rather than
// oh-my-posh, whose CLI is ALSO named `omp` (a bare `LookPath("omp")` on this host resolves to
// oh-my-posh). Driving oh-my-posh as the coding agent hangs on a handshake that never comes, so
// the spawn path rejects a binary this does not accept. Compiled only in tests.
func VerifyOmpBinaryForTest(versionOutput string) error {
	return verifyOmpBinary(versionOutput)
}

// SessionEnvironmentForTest exposes the rpc child-environment assembly: the scrubbed base, the
// injected OpenRouter key, and the ONE PI_CODING_AGENT_DIR that roots omp's session storage under
// the provisioned workspace. It takes the workspace because the session STORE root is the
// adapter's to choose, while the layout INSIDE it is omp's — the 17.2.9 revert of the hashed
// bucket scheme is why the adapter names the root and nothing below it. Compiled only in tests.
func SessionEnvironmentForTest(base []string, workspace string, cred agentsession.InjectedCredential) ([]string, error) {
	return sessionEnvironment(base, workspace, cred)
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

// PeerEnvelopeForTest renders the model-facing <eden-peer-message> envelope the adapter writes
// for one inbound peer delivery, so the ESCAPING of an untrusted body/attribute is assertable
// without a transport at all. It is the exact analog of claudeadapter.PeerEnvelopeForTest and
// exposes the same unexported pure renderer this package already ships (peer.go: peerEnvelope).
func PeerEnvelopeForTest(from, msgID, replyTo, body string, verified bool) string {
	return peerEnvelope(from, msgID, replyTo, body, verified)
}
