package dependenciestest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) fails THIS package on any leaked goroutine. The fakes spawn a
// ctx-bridge goroutine inside Clock.After exactly as the real adapter does; every one must
// unwind by suite end (the canceled-After / fired-After paths both terminate it). Threshold:
// ZERO leaked goroutines/fds.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
