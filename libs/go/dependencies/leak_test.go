package dependencies_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) fails the package on ANY goroutine left running after the
// suite. dependencies is a stdlib-only leaf; its only background goroutines are the
// short-lived ones spawned by Clock.After's ctx-bridge, every one of which MUST have
// unwound by the time its test returns (the cancellation contract, §2 Clock). The gate's
// threshold is ZERO leaked goroutines/fds, so the only ignore is the well-known testing
// reaper present in every Go test binary.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own background reaper, present in every Go test binary.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
