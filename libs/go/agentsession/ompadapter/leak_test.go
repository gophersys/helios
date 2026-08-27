package ompadapter_test

import (
	"testing"

	"go.uber.org/goleak"
)

// TestMain installs goleak.VerifyTestMain so the resource-leak lane (`ctl.sh leak`,
// ADR-0020 dimension (b)) fails the package on ANY goroutine left running after the suite
// drains. The omp adapter's spawn path owns one pump goroutine per rpcConn — it reads the one
// long-lived `omp --mode rpc` process's stdout for the whole session — reaped through the
// graceful Close ladder (rpc.go: close done -> stdin EOF -> drain -> close the events channel).
// The fast suite
// this TestMain governs exercises only the PURE normalizer + arg/env builders + the credential
// scrub seam (no process, no goroutine), so the gate's threshold here is ZERO leaked
// goroutines; the lifecycle/load lanes (their own build tags) add `defer goleak.VerifyNone(t)`
// over the real subprocess to prove the spawn goroutines reap too.
//
// The allowlist holds exactly the well-known benign runtime/test-harness roots that every Go
// test binary carries; each is named so a future real leak cannot hide behind an over-broad
// ignore:
//   - internal/poll.runtime_pollWait — the netpoller wait the runtime parks on for any open
//     fd (a reaped child's stdout pipe can still be draining when the verifier polls); a fixed
//     runtime root, never an adapter goroutine.
func TestMain(m *testing.M) {
	goleak.VerifyTestMain(
		m,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
}
