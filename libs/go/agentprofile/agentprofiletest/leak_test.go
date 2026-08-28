package agentprofiletest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain for the agentprofiletest package so the resource-leak lane
// (`ctl.sh leak`, ADR-0020 dimension (b)) FAILS on ANY goroutine left running after the suite. Both
// fakes are deterministic in-memory values guarded by a sync.Mutex — no clock, no I/O, no background
// goroutine — so the only ignore is the benign runtime/test-harness poller root that every Go test
// binary carries. The threshold is ZERO leaked goroutines/fds.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper; not an agentprofiletest goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
