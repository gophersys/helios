package claudeadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) fails the package on ANY goroutine left running after the
// suite drains. The claudeadapter spawn path owns ONE scanner goroutine per
// processConn (spawn.go: scan), reaped through the graceful Close ladder; the fast
// suite this TestMain governs exercises only the pure normalizer + arg/env builders
// (no process, no goroutine), so the gate's threshold is ZERO leaked goroutines.
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
