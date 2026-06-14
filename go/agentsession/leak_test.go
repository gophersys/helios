package agentsession_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the root agentsession package on ANY goroutine left
// running after the suite. The package's load-bearing concurrency is the per-session
// pump goroutine and the per-subscriber broadcaster fan-out: a Session.Close that did
// NOT reap the pump, or an Events stream that left a subscriber attached, would surface
// here as a leaked goroutine. The threshold is ZERO leaked goroutines/fds; the only
// ignores are the well-known benign runtime/test-harness roots — agentsession owns no
// background daemon goroutine of its own that outlives a closed Session.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that
		// touches the runtime poller; not an agentsession goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
