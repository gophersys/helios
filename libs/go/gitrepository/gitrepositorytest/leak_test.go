package gitrepositorytest_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) FAILS the gitrepositorytest external test package on ANY
// goroutine left running after the conformance suite (the in-memory fake arm) and the
// `integration`-tagged real system-git arm. The in-memory fake holds only mutex-guarded
// model state — no goroutine — and the real arm shells short-lived `git` children reaped
// synchronously per op. A surviving goroutine means a leaked subprocess reaper or an
// un-waited git child. The threshold is ZERO leaked goroutines/fds; the only ignores are
// the benign runtime/test-harness roots.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
		goleak.IgnoreTopFunction("os/exec.(*Cmd).watchCtx"),
	)
}
