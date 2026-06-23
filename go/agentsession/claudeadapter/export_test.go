package claudeadapter

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// contextForTest returns a background context for the white-box export seams.
func contextForTest() context.Context { return context.Background() }

// MustNewForTest builds the adapter on the canonical New(configuration) (*Adapter, error)
// spine and fails the test on a (today impossible) construction error, so a black-box test
// drives the real constructor without repeating the error check at every call site.
//
//nolint:gocritic // Config is the frozen copyable configuration; the test mirrors the by-value seam.
func MustNewForTest(t *testing.T, configuration Config) *Adapter {
	t.Helper()
	adapter, err := New(configuration)
	if err != nil {
		t.Fatalf("claudeadapter.New: %v", err)
	}
	return adapter
}

// NormalizeLineForTest exposes the unexported stream-json normalizer (a FRESH one per
// call) to the single-line black-box tests (unknown/malformed type handling). It is
// compiled only in tests, so it is not part of the public surface.
func NormalizeLineForTest(line []byte) []agentsession.Event {
	return newNormalizer().normalize(line)
}

// StreamNormalizerForTest returns a stateful per-stream normalizer (the same one the live
// conn drives) so a fixture test threads model attribution across lines exactly as a real
// session does.
func StreamNormalizerForTest() func(line []byte) []agentsession.Event {
	n := newNormalizer()
	return n.normalize
}

// BuildArgumentsForTest exposes the pure arg builder to the black-box tests.
//
//nolint:gocritic // contract §2/§3: Spec is the frozen copyable session input; the fake Adapter mirrors the port's by-value seam.
func BuildArgumentsForTest(spec agentsession.Spec, route agentsession.Route) []string {
	return buildArguments(spec, route)
}

// ChildEnvironmentForTest exposes the pure child-env builder (scrub + inject) to the
// black-box credential-seam tests, so the precedence-trap defense is runnable without a
// real Secret or process.
func ChildEnvironmentForTest(base []string, envName, token string) []string {
	return childEnvironment(base, envName, token)
}

// PermissionAnswerPrefixForTest exposes the adapter's internal eden:permission frame prefix so
// a black-box test can pin it equal to the library's (the one-home invariant: a drift between
// the library's permissionAnswer render and the adapter's parse would silently break the
// translation, so the prefixes are asserted equal).
func PermissionAnswerPrefixForTest() string { return permissionAnswerPrefix }

// ParsePermissionAnswerForTest exposes the internal eden:permission frame parser (id, allow,
// by) to the white-box translation tests, so the decode is provable without a process.
func ParsePermissionAnswerForTest(text string) (requestID string, allow bool, by string, ok bool) {
	answer, ok := parsePermissionAnswer(text)
	return answer.requestID, answer.allow, answer.by, ok
}

// ParsePermissionAnswerRationaleForTest exposes the OPTIONAL audit rationale decoded off the
// 0x1f-separated frame, so the additive ratified-model field is provable without a process.
func ParsePermissionAnswerRationaleForTest(text string) (by, rationale string, ok bool) {
	answer, ok := parsePermissionAnswer(text)
	return answer.by, answer.rationale, ok
}

// RationaleSeparatorForTest exposes the adapter's internal rationale separator so a black-box
// test pins it equal to the library's agentsession.rationaleSeparator (the one-home invariant).
func RationaleSeparatorForTest() string { return rationaleSeparator }

// PermissionDecisionFrameForTest renders the can_use_tool control_response a resolved decision
// produces on the wire, given the original input the ask carried — the exact bytes Send writes
// on stdin. It threads through the normalizer's stash exactly as the live conn does: the input
// is recorded under the request id, then consumed by the frame build. Compiled only in tests.
func PermissionDecisionFrameForTest(requestID string, allow bool, by string, originalInput []byte) ([]byte, error) {
	n := newNormalizer()
	n.rememberInput(requestID, originalInput)
	stashed, _ := n.takeInput(requestID)
	result := permissionResult(allow, denyMessage(by, ""), stashed)
	return controlResponseFrame(requestID, result)
}

// HostToolRouteForTest drives the host-tool router over one JSON-RPC mcp_message and returns
// the response and any fanned-out Events, so the tools/list + tools/call wiring is provable
// without a live claude. Compiled only in tests.
func HostToolRouteForTest(tools []agentsession.HostTool, jsonrpc []byte) (response any, events []agentsession.Event, ok bool) {
	return newHostToolRouter(tools).route(contextForTest(), jsonrpc)
}

// InitializeFrameForTest renders the initialize control_request the conn writes at startup for
// a given set of HostTools, so the sdkMcpServers wire shape (an object keyed by server name, not
// an array) is pinned without a live claude. Compiled only in tests.
func InitializeFrameForTest(tools []agentsession.HostTool) ([]byte, error) {
	return initializeFrame("eden-init-test", hostToolNames(tools))
}

// ConnProcessPIDForTest exposes the OS process id the conn's subprocess was started with,
// so the lifecycle probe can verify the REAL child is reaped after Close (CountOwned via
// signal-0 liveness). It returns (0, false) for a conn type that is not the os/exec-backed
// processConn. Compiled only in tests.
func ConnProcessPIDForTest(conn agentsession.HarnessConn) (int, bool) {
	pc, ok := conn.(*processConn)
	if !ok || pc.command == nil || pc.command.Process == nil {
		return 0, false
	}
	return pc.command.Process.Pid, true
}
