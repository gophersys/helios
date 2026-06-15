//go:build load

// Package claudeadapter_test's load arm fans out N concurrent spawn -> normalize -> Close
// cycles over the REAL stub subprocess (internal/stubharness, NOT claude) under -race
// (ADR-0020 dimension (e)). Each cycle spawns its own process through the genuine Spawn
// path, drives the Prompt, drains the normalized stream to its terminal, and Closes — so
// the os/exec lifecycle, the scanner goroutine, and the normalizer are all exercised
// concurrently. The race detector must report 0 races; every process is reaped; and goleak
// asserts the goroutine high-water returns to baseline (no orphaned scanner/process).
//
//	go test -tags load ./ -race -count=1   (EDEN_LOAD_N sets the fan-out width)
package claudeadapter_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// loadCanary is the fake credential threaded through every concurrent spawn; the load arm
// also re-asserts it never leaks onto any of the N streams (the canary property at scale).
const loadCanary = "LOAD-FAKE-TOKEN-do-not-leak"

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N). The default is
// modest here because every cycle spawns a REAL OS process (the "real-pod" class of the
// taxonomy, 50-ish), not an in-process object.
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 50
}

// loadConcurrency bounds how many subprocesses run at once so a large EDEN_LOAD_N fans out
// without exhausting the container's process table — the cycles are still concurrent, just
// admission-controlled. The race detector and goleak prove correctness regardless of width.
func loadConcurrency(n int) int {
	const maxConcurrent = 32
	if n < maxConcurrent {
		return n
	}
	return maxConcurrent
}

// TestLoad_ConcurrentSpawnNormalizeCloseRaceClean fans out N concurrent spawn/normalize/
// Close cycles over the stub subprocess. Bound by t.Context(), admission-controlled by a
// semaphore, every cycle must reach a terminal and reap its process; the race detector must
// find 0 races; goleak.VerifyNone proves the goroutine high-water returns to baseline.
//
//nolint:paralleltest // goleak.VerifyNone asserts the goroutine high-water at this test's end; a parallel sibling's goroutines would pollute that snapshot, so the load test runs serially.
func TestLoad_ConcurrentSpawnNormalizeCloseRaceClean(t *testing.T) {
	defer goleak.VerifyNone(
		t,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)

	stub := buildLoadStub(t)
	n := loadN()
	sem := make(chan struct{}, loadConcurrency(n))

	ctx, cancel := context.WithTimeout(t.Context(), 60*time.Second)
	defer cancel()

	var (
		wg        sync.WaitGroup
		failures  atomic.Int64
		terminals atomic.Int64
		firstErr  atomic.Pointer[string]
	)
	recordErr := func(msg string) {
		failures.Add(1)
		s := msg
		firstErr.CompareAndSwap(nil, &s)
	}

	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			if err := oneCycle(ctx, stub, i); err != nil {
				recordErr(err.Error())
				return
			}
			terminals.Add(1)
		}(i)
	}
	wg.Wait()

	if got := failures.Load(); got != 0 {
		msg := "(none captured)"
		if p := firstErr.Load(); p != nil {
			msg = *p
		}
		t.Fatalf("%d/%d concurrent cycles failed; first error: %s", got, n, msg)
	}
	if got := terminals.Load(); got != int64(n) {
		t.Fatalf("expected all %d cycles to reach a terminal, got %d", n, got)
	}
}

// oneCycle runs a single spawn -> Prompt -> drain-to-terminal -> Close over a fresh stub
// process. A background drainer reads conn.Events() to EOF (the conn is NOT self-draining —
// the graceful Close ladder waits on the scanner, which only finishes once the channel is
// read to completion; this mirrors the real library's session pump). The cycle asserts the
// stream reached a terminal AFTER the Ready handshake and the credential canary never leaked
// onto any event, then Closes and joins the drainer (proving the process is reaped).
func oneCycle(ctx context.Context, stub string, i int) error {
	adapter, err := claudeadapter.New(claudeadapter.Config{Binary: stub})
	if err != nil {
		return err
	}
	conn, err := adapter.Spawn(
		ctx,
		agentsession.Spec{Workspace: os.TempDir(), Routing: agentsession.RouteKey{Role: "assistant"}},
		agentsession.Route{Harness: "claude-code", Model: "stub-fable"},
		agentsession.InjectedCredential{
			Secret:  secretstest.MintSecret([]byte(loadCanary)),
			Vehicle: agentsession.VehicleEnv,
			EnvName: "CLAUDE_CODE_OAUTH_TOKEN",
		},
	)
	if err != nil {
		return wrapCycle(i, "spawn", err)
	}

	if err := conn.Send(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "make a file"}); err != nil {
		_ = conn.Close(context.Background()) //nolint:errcheck // reap on the prompt-failure path.
		return wrapCycle(i, "prompt", err)
	}

	// A background drainer consumes every event to EOF, recording its observations; Close
	// then unblocks the scanner and the drainer reports the full stream.
	obs := make(chan cycleObservation, 1)
	go func() { obs <- drainObservations(conn) }()

	if err := conn.Close(ctx); err != nil {
		return wrapCycle(i, "close", err)
	}
	select {
	case o := <-obs:
		return evalObservation(i, o)
	case <-ctx.Done():
		return wrapCycle(i, "drain", ctx.Err())
	}
}

// cycleObservation records what one cycle's drainer saw on its stream.
type cycleObservation struct {
	ready, terminal, leaked, terminalBeforeReady bool
}

// drainObservations reads conn.Events() to EOF, recording the Ready handshake, the terminal,
// any canary leak, and whether a terminal preceded Ready (an ordering violation).
func drainObservations(conn agentsession.HarnessConn) cycleObservation {
	var o cycleObservation
	for ev := range conn.Events() {
		if ev.Kind == agentsession.EventSessionState && ev.State != nil && ev.State.To == agentsession.StateReady {
			o.ready = true
		}
		for _, field := range eventLeakSurfaces(&ev) {
			if containsCanary(field) {
				o.leaked = true
			}
		}
		if ev.IsTerminal() {
			o.terminal = true
			if !o.ready {
				o.terminalBeforeReady = true
			}
		}
	}
	return o
}

// evalObservation maps a drainer's observation to a per-cycle error (nil on success).
func evalObservation(i int, o cycleObservation) error {
	switch {
	case o.leaked:
		return wrapCycle(i, "leak", cycleError("credential canary leaked onto a load-stream event"))
	case !o.terminal:
		return wrapCycle(i, "stream", cycleError("channel closed before a terminal"))
	case o.terminalBeforeReady:
		return wrapCycle(i, "order", cycleError("terminal observed before the Ready handshake"))
	default:
		return nil
	}
}

// eventLeakSurfaces projects the redaction-eligible string fields of an event for the
// at-scale canary check (a minimal local mirror of agentsessiontest.AssertNoSecretInEvent
// so the load cycle stays free of the *testing.T-bound helper).
func eventLeakSurfaces(ev *agentsession.Event) []string {
	out := []string{ev.SessionID, ev.TurnID, string(ev.Extension)}
	if ev.Message != nil {
		out = append(out, ev.Message.Role, ev.Message.Delta)
	}
	if ev.Tool != nil {
		out = append(out, ev.Tool.Name, ev.Tool.ArgsSummary, ev.Tool.ResultDigest)
	}
	if ev.Terminal != nil {
		out = append(out, ev.Terminal.ResultText, ev.Terminal.Detail)
	}
	return out
}

// containsCanary reports whether s embeds the load canary.
func containsCanary(s string) bool { return strings.Contains(s, loadCanary) }

// cycleError is a tiny error for the load cycle so it does not pull the errors lib in.
type cycleError string

func (e cycleError) Error() string { return string(e) }

// wrapCycle annotates a cycle error with the cycle index and stage.
func wrapCycle(i int, stage string, err error) error {
	return cycleError("cycle " + strconv.Itoa(i) + " " + stage + ": " + err.Error())
}

// buildLoadStub compiles the stub harness once into t.TempDir() for the whole fan-out.
func buildLoadStub(t *testing.T) string {
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
