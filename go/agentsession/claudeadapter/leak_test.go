package claudeadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) fails the package on ANY goroutine left running after the
// suite drains. The claudeadapter spawn path owns TWO goroutines per processConn — the
// scanner (spawn.go: scan) and the line reader it forks (spawn.go: readLines) — reaped
// through the graceful Close ladder. Most of the fast suite this TestMain governs
// exercises only the pure normalizer + arg/env builders (no process, no goroutine), but
// the peer DELIVERY tests (peer_conn_test.go) drive a REAL conn over INJECTED pipes via
// PipeConnForTest: no child process, yet both real goroutines run and must reap on Close.
// So the gate's ZERO-leaked-goroutine threshold covers those pipe-conn goroutines too —
// a scanner or reader that outlived its Close would fail this package.
//
// The allowlist holds exactly the well-known benign runtime/test-harness roots that
// every Go test binary carries; each is named so a future leak cannot hide behind an
// over-broad ignore:
//   - internal/poll.runtime_pollWait — the netpoller wait the runtime parks on for
//     any open fd (stdout/stdin pipes of a reaped child can still be draining when
//     the verifier polls); a fixed runtime root, not an adapter goroutine.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
