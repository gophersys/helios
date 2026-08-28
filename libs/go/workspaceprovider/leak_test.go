package workspaceprovider_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the root workspaceprovider package on ANY goroutine left
// running after the suite. The library itself owns NO background daemon goroutine of its
// own that outlives a torn-down workspace — a Provisioner is pure routing over an Adapter,
// a workspace handle holds only a mutex + the adapter Connection, and Teardown reaps the
// native object synchronously. So a leak here is a real regression: a Run whose terminal
// gate goroutine was not released, a Files stream left open, or an adapter Connection that
// spun a watcher and never stopped it. The threshold is ZERO leaked goroutines/fds; the only
// ignores are the well-known benign runtime/test-harness roots (the in-memory fake spawns no
// background goroutine — the real docker SDK / k3d roots live only behind the
// `//go:build integration` lane, which has its own package).
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that
		// touches the runtime poller; not a workspaceprovider goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
