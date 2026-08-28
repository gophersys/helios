package observability_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the root observability package on ANY goroutine left
// running after the suite. observability is a pure, stdlib-only leaf whose Provider
// owns NO background goroutine: Emit/With/Scope/Log append under a mutex and Flush is
// a synchronous drain — there is no exporter pump, no batch timer, no fan-out worker.
// So a leaked goroutine here would be a real regression (e.g. a future async Flush that
// forgot to reap its worker). The threshold is ZERO leaked goroutines/fds; the only
// ignores are the well-known benign runtime/test-harness roots, which observability
// does not own.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary; not
		// an observability goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
