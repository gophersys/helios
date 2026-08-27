package testingtest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain for the testingtest binary (ADR-0020 dimension
// (b), `ctl.sh leak`). It covers BOTH test packages compiled into this directory's single
// test binary — the external testingtest_test and the white-box testingtest internal test
// — so a leaked goroutine from either fails the package. testingtest's concurrency surface
// is the FakeClock (the alias of the internal virtual-time engine): a cancellable After
// waiter that Advance/cancel failed to unwind would surface here. The threshold is ZERO
// leaked goroutines/fds; the lone ignore is the runtime poller reaper every Go test binary
// carries.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
