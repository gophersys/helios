package observabilitytest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain for the public-fake package (`ctl.sh leak`,
// ADR-0020 dimension (b)): the in-memory *Provider and its Exporter-backed conformance
// mode own NO background goroutine (record/append under a mutex; Flush is a synchronous
// drain), so the leak threshold is ZERO. The conformance suite fans Emit/With/Scope/Log
// across many goroutines under -race; this TestMain makes a goroutine those workers
// failed to retire a HARD FAIL of the fake package rather than a silent leak.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
