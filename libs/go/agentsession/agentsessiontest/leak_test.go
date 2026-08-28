package agentsessiontest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the agentsessiontest package on ANY goroutine left running
// after its suite — covering BOTH the default fake-conformance run AND the `-tags
// integration` many-concurrent-tailers fan-out run (the same agentsessiontest_test package).
// Each opened session is reaped on t.Cleanup, so a leaked pump or an attached subscriber
// surfaces here. The threshold is ZERO leaked goroutines/fds; the only ignore is the
// well-known benign runtime poller reaper present in every Go test binary.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
