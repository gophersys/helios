package agentruntime_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the root agentruntime package on ANY goroutine left running after the suite.
// The package's load-bearing concurrency is the per-Run pump goroutine, the heartbeat ticker
// goroutine, and the control subscription: a Run that did NOT reap any of the three would surface
// here as a leaked goroutine. The threshold is ZERO leaked goroutines/fds; the only ignore is the
// well-known benign runtime poller root — agentruntime owns no background daemon goroutine that
// outlives a returned Run.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that touches the
		// runtime poller; not an agentruntime goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
