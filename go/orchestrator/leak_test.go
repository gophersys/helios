package orchestrator_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the root orchestrator package on ANY goroutine left running
// after the suite. The orchestrator's load-bearing concurrency is the reconcile loop
// goroutine started by Pool.Start and the per-subscriber Watch fan-out: a Close that did NOT
// reap the loop goroutine (the stop/done handshake), a Watch ctx-reaper goroutine left
// attached, or an overflowed subscriber never dropped would surface here as a leaked
// goroutine. The threshold is ZERO leaked goroutines/fds; the only ignores are the
// well-known benign runtime/test-harness roots — the Pool owns no background daemon
// goroutine of its own that outlives a Closed Pool, and New is a pure value constructor that
// starts nothing.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that
		// touches the runtime poller; not an orchestrator goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
