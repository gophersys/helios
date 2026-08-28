package platformconnectoradapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the platformconnectoradapter package on ANY goroutine left running after the
// suite. The adapter is request-scoped: New dials nothing, Resolve makes a synchronous transport load +
// an in-process envelope Unseal and returns — it spawns no background goroutine. The only ignore is the
// well-known benign runtime poller root. A regression that launched a background row-prefetch goroutine
// per Resolve and never joined it would surface here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that touches the
		// runtime poller; not a platformconnectoradapter goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
