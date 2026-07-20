package envelope_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) fails the package on ANY goroutine left running after the suite. envelope is a
// pure crypto leaf with no goroutines of its own; the only ignore is the well-known benign
// runtime/test-harness root. The gate's threshold is ZERO leaked goroutines/fds.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
