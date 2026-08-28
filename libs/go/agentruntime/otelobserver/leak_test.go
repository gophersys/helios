package otelobserver_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the otelobserver package on ANY goroutine left running after the suite. The
// adapter spawns NO goroutine: Logf/Inject/Extract are synchronous transforms and Flush is a
// synchronous drain. The only ignore is the well-known benign runtime poller root.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
