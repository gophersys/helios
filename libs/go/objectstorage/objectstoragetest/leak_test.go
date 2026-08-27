package objectstoragetest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain for the objectstoragetest package so the resource-leak
// lane (`ctl.sh leak`, ADR-0020 dimension (b)) FAILS on ANY goroutine left running after the
// suite. The fake Backend is a deterministic, in-memory map guarded by a sync.Mutex — it holds no
// clock-driven goroutine and no I/O — so the only ignore is the benign runtime poller root; the
// threshold is ZERO leaked goroutines/fds.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
