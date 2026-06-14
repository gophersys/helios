package slogadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain for the slog Exporter adapter (`ctl.sh leak`,
// ADR-0020 dimension (b)): the Exporter holds only a *slog.Logger and spawns NO
// goroutine — Export renders synchronously on the caller's goroutine — so the leak
// threshold is ZERO. A future buffered/async slog sink that forgot to reap its writer
// goroutine would surface here.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
