package forge_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain wires goleak (test-taxonomy dimension b). The forge port package is pure
// value/classification logic with no goroutines, so the suite must leak none.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
