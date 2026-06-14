package testing_test

import (
	gotest "testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the root testing package on ANY goroutine left running
// after the suite. The package's only load-bearing concurrency is the FakeClock's
// best-effort per-waiter cancellation goroutine (one per After(ctx,…) with a cancellable
// ctx): a clock whose Advance or cancel did NOT unwind a waiter goroutine would surface
// here as a leak. The threshold is ZERO leaked goroutines/fds; the lone ignore is the
// well-known runtime poller reaper present in every Go test binary — not a testing
// goroutine. (The package under test is itself named `testing`, so the stdlib import is
// aliased `gotest`.)
func TestMain(m *gotest.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that
		// touches the runtime poller; not a testing-library goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
