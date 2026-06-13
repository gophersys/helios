package errors_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) fails the package on ANY goroutine left running after the
// suite. errors is a pure, stdlib-only leaf with no goroutines of its own, so the
// only ignores are the well-known benign runtime/test-harness roots; the gate's
// threshold is ZERO leaked goroutines/fds.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own background reaper, present in every Go test binary.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
