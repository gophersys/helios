package claudeadapter

import "github.com/gophersys/libs/go/agentsession"

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
