//go:build lifecycle

// Package claudeadapter_test's lifecycle arm drives the full object-lifecycle conformance
// (ADR-0020 dimension (c)) over the adapter's closeable handle — the os/exec-backed
// processConn returned by Spawn. It builds the REAL stub subprocess (internal/stubharness,
// NOT claude), spawns it through the genuine Spawn path with a FAKE seeded credential, and
// drives testing.AssertLifecycle: construct -> use -> first Close -> second Close is an
// idempotent no-op -> CountOwned()==0 (the child process is reaped, no orphan). goleak owns
// the orphan-goroutine half (the scanner goroutine must drain). Tagged `lifecycle` so the
// heavy probe (it compiles + spawns a process) stays out of the fast unit run.
//
//	go test -tags lifecycle ./ -race -count=1
package claudeadapter_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"syscall"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
	testingpkg "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"
)

// lifecycleCanary is the fake credential plaintext threaded through Secret.Use exactly as
// production does; the lifecycle arm asserts the conn reaches teardown, not redaction (the
// canary arm owns the no-leak property), but it is still a non-real token.
const lifecycleCanary = "LIFECYCLE-FAKE-TOKEN-do-not-leak"

// TestLifecycle_ProcessConnDoubleCloseAndReaped drives AssertLifecycle over a freshly
// spawned stub-backed processConn. The driver asserts, in order: construct (Spawn) returns
// a probe; Use exercises the live conn (Ready handshake + a Prompt + one drained Event);
// the first Close runs the graceful ladder; the SECOND Close is a no-op (no error, no
// panic, no hang — the idempotency invariant); and CountOwned()==0 (the child PID is no
// longer alive — no orphan process). goleak.VerifyNone asserts the scanner goroutine drained.
//
//nolint:paralleltest // goleak.VerifyNone snapshots the goroutine high-water at this test's end; a parallel sibling's goroutines would pollute that snapshot, so the lifecycle probe runs serially.
func TestLifecycle_ProcessConnDoubleCloseAndReaped(t *testing.T) {
	defer goleak.VerifyNone(
		t,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)

	stub := buildLifecycleStub(t)
	report := testingtest.NewReport(t)
	harness := testingtest.NewHarness(t)

	testingpkg.AssertLifecycle(context.Background(), harness, report,
		func(ctx context.Context, _ testingpkg.Harness) (testingpkg.LifecycleProbe, func(), error) {
			adapter := claudeadapter.NewWithConfig(claudeadapter.Config{Binary: stub})
			conn, err := adapter.Spawn(
				ctx,
				agentsession.Spec{Workspace: t.TempDir(), Routing: agentsession.RouteKey{Role: "assistant"}},
				agentsession.Route{Harness: "claude-code", Model: "stub-fable"},
				agentsession.InjectedCredential{
					Secret:  secretstest.MintSecret([]byte(lifecycleCanary)),
					Vehicle: agentsession.VehicleEnv,
					EnvName: "CLAUDE_CODE_OAUTH_TOKEN",
				},
			)
			if err != nil {
				return nil, nil, err
			}
			pid, ok := claudeadapter.ConnProcessPIDForTest(conn)
			if !ok {
				// Reap the conn before failing so we leave no orphan.
				_ = conn.Close(ctx) //nolint:errcheck // teardown on the unexpected-shape path.
				return nil, nil, errNoPID
			}
			probe := newProcessConnProbe(conn, pid)
			// teardown is a belt-and-braces reap even if an assertion aborts mid-lifecycle.
			teardown := func() { _ = probe.Close(context.Background()) } //nolint:errcheck // idempotent reap.
			return probe, teardown, nil
		})
}

// errNoPID signals the conn was not the os/exec-backed shape the probe can inspect.
var errNoPID = osError("claudeadapter lifecycle probe: conn exposed no child PID")

// osError is a tiny sentinel error type so the probe factory can fail without pulling the
// errors lib into this test file's surface.
type osError string

func (e osError) Error() string { return string(e) }

// processConnProbe adapts the spawned HarnessConn to the testing.LifecycleProbe port. It
// owns exactly one external resource: the child OS process (tracked by pid). A background
// drainer continuously reads conn.Events() until the channel closes — EXACTLY as the real
// library's session pump does. This matters because the conn's graceful Close ladder closes
// stdin then waits for the scanner to finish, and the scanner only finishes once the event
// channel is being read to completion; a consumer that stops reading and then calls Close
// deadlocks (the real contract — the conn is not self-draining). The drainer is the probe's
// stand-in for that pump.
type processConnProbe struct {
	conn    agentsession.HarnessConn
	pid     int
	first   chan agentsession.Event // the Ready handshake + subsequent events, buffered for Use
	drained chan struct{}           // closed when the drainer has consumed the channel to EOF
}

// newProcessConnProbe starts the background drainer and returns the probe.
func newProcessConnProbe(conn agentsession.HarnessConn, pid int) *processConnProbe {
	p := &processConnProbe{
		conn:    conn,
		pid:     pid,
		first:   make(chan agentsession.Event, 1),
		drained: make(chan struct{}),
	}
	go p.drain()
	return p
}

// drain reads every Event the conn emits until the channel closes, forwarding the FIRST
// event to Use (non-blocking) so Use can assert the Ready handshake without racing the
// drainer for the channel. Reading to EOF is what lets Close's scanner-join complete.
func (p *processConnProbe) drain() {
	defer close(p.drained)
	for ev := range p.conn.Events() {
		select {
		case p.first <- ev:
		default:
		}
	}
}

// Use exercises the live conn once: it observes the Ready handshake the scanner emits on
// spawn (forwarded by the drainer) and sends a Prompt — proving the spawn/scan path is live
// before Close. A bounded context keeps a regression from hanging the lifecycle gate.
func (p *processConnProbe) Use(ctx context.Context) error {
	useCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	select {
	case ev := <-p.first:
		if ev.Kind != agentsession.EventSessionState || ev.State == nil || ev.State.To != agentsession.StateReady {
			return osError("first event was not the Initializing->Ready handshake")
		}
	case <-useCtx.Done():
		return osError("timed out waiting for the Ready handshake")
	}
	if err := p.conn.Send(useCtx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "make a file"}); err != nil {
		return err
	}
	return nil
}

// Close runs the conn's graceful ladder, then joins the drainer so no scanner goroutine is
// left running. processConn.Close is sync.Once-guarded, so the SECOND call AssertLifecycle
// makes is a no-op that returns nil — the double-close idempotency invariant, proven here on
// a real subprocess. The drainer-join is itself idempotent (a closed channel receives
// immediately), so a second Close stays a clean no-op.
func (p *processConnProbe) Close(ctx context.Context) error {
	closeCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	if err := p.conn.Close(closeCtx); err != nil {
		return err
	}
	select {
	case <-p.drained:
		return nil
	case <-closeCtx.Done():
		return osError("timed out joining the event drainer after Close")
	}
}

// CountOwned reports the number of external resources still owned: 1 if the child process
// is still alive, 0 once it has been reaped. Liveness is probed with signal 0 (the POSIX
// "does this process exist" test) — a real OS check, not a mock. After Close the graceful
// ladder + the CommandContext cancel must have reaped the child, so this returns 0.
func (p *processConnProbe) CountOwned(_ context.Context) (int, error) {
	if processAlive(p.pid) {
		return 1, nil
	}
	return 0, nil
}

// processAlive reports whether pid names a live process via signal 0. On a reaped child
// the process is gone (ESRCH) or a zombie already waited by the conn; either way signal 0
// to a fully-reaped pid fails, which is the "no orphan" signal the gate wants.
func processAlive(pid int) bool {
	proc, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	// Signal 0 performs error checking without delivering a signal: nil == the process
	// exists and we may signal it; an error == it is gone/reaped.
	err = proc.Signal(syscall.Signal(0))
	return err == nil
}

// buildLifecycleStub compiles the stub harness into t.TempDir() and returns its path.
func buildLifecycleStub(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	binary := filepath.Join(dir, "stubharness")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot locate the test source path")
	}
	source := filepath.Join(filepath.Dir(file), "internal", "stubharness")
	// #nosec G204 -- fixed `go build` of the in-repo stub; binary/source are test-derived paths, not user input.
	build := exec.Command("go", "build", "-o", binary, ".")
	build.Dir = source
	build.Env = os.Environ()
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build stub harness: %v\n%s", err, out)
	}
	return binary
}
