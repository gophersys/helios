package githubadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain wires goleak (test-taxonomy dimension b): the unit suite drives the
// adapter over a fake, in-process transport, so it must leak zero goroutines. Only
// the known-benign runtime poll root is ignored; a real leaked goroutine fails here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
