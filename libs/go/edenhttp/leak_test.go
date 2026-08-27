package edenhttp_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the root edenhttp package on ANY goroutine left running after the suite. The
// spine itself spawns NO goroutine (New is pure; Middleware/pipeline run synchronously on the
// caller's request goroutine), so any leak surfaced here is a real regression. The only ignore is
// the well-known benign runtime poller root.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
