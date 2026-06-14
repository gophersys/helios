package secrets_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the secrets package on ANY goroutine left running after the
// suite. secrets is a pure, stdlib-only leaf: a Secret owns plaintext bytes (zeroized in
// place, no goroutine), the Mediator is a lock-free router, and a Reference is an immutable
// value — none of them spawn a background goroutine. So the only ignore is the well-known
// benign runtime/test-harness poller root; the gate's threshold is ZERO leaked goroutines/fds.
// A regression that, say, launched a reaper goroutine per Resolve and never joined it would
// surface here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		// testing's own network/file poller reaper, present in every Go test binary that
		// touches the runtime poller; not a secrets goroutine.
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
