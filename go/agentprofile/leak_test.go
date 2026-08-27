package agentprofile_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the agentprofile package on ANY goroutine left running after the suite.
// agentprofile is a pure, stdlib-only computation leaf: New parses and binds, Render composes and
// hashes, Drift reads through the injected Tree port — none of them spawns a background goroutine,
// opens a file or dials anything. So the only ignore is the well-known benign runtime/test-harness
// poller root that every Go test binary carries; the gate's threshold is ZERO leaked goroutines/fds.
// A regression that, say, rendered each cell on its own goroutine and never joined it surfaces here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that touches the
		// runtime poller; not an agentprofile goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
