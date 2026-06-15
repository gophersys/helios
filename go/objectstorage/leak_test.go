package objectstorage_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`, ADR-0020
// dimension (b)) FAILS the objectstorage package on ANY goroutine left running after the suite.
// The root package is a pure, SDK-free port: a *Client is a stateless router over its Backend, an
// ObjectRef is an immutable value, and the in-memory fake Backend is a mutex-guarded map — none
// spawn a background goroutine. So the only ignore is the well-known benign runtime poller root;
// the gate's threshold is ZERO leaked goroutines/fds. A regression that, say, launched a reaper
// goroutine per Put and never joined it would surface here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that touches
		// the runtime poller; not an objectstorage goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
