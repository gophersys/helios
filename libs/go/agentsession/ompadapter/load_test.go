//go:build load

// The load / scale lane (ADR-0020 dimension (e)) for the omp adapter: N concurrent SESSIONS, each
// the FULL real path (Open -> Prompt -> spawn+scan the GENUINE stub subprocess -> drain to
// terminal -> Close), fanned out under -race and bounded by t.Context() + an errgroup. It proves
// the spawn/parse/reap ladder is race-clean at fan-out, every session process is reaped (no
// orphan stubharness child survives), and the goroutine high-water returns to baseline
// (goleak.VerifyNone) once the fan-out joins. The fan-out width is EDEN_LOAD_N (default 500
// in-process); concurrency is capped so the container is not flooded with simultaneous processes
// while still driving all N turns to completion.
package ompadapter_test

import (
	"context"
	"os"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"go.uber.org/goleak"
	"golang.org/x/sync/errgroup"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// loadFanout reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500;
// ADR-0020 dimension (e)). Named distinctly from the agentsession package's loadN so the two
// taxonomy overlays never collide.
func loadFanout() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentTurnsRaceCleanAllReaped fans out N concurrent full turns over the real stub
// subprocess. Each goroutine opens its own session, prompts, drains to a TURN boundary carrying the
// four-token ledger, asserts the credential canary never leaked, and closes — all under -race.
// After every turn joins, the goroutine high-water must return to baseline (goleak) and zero
// stubharness children may remain (every spawned process reaped). It is NOT t.Parallel(): this
// lane IS the fan-out and asserts the global goroutine/process high-water returns to baseline, so
// running it alongside other tests would corrupt that count.
//
//nolint:paralleltest // see the doc comment: this lane owns the global goroutine/process count.
func TestLoad_ConcurrentTurnsRaceCleanAllReaped(t *testing.T) {
	defer goleak.VerifyNone(t)

	stub := buildStub(t)
	n := loadFanout()

	// Cap simultaneous in-flight processes so N=500 does not flood the container with 500
	// concurrent subprocesses at once; all N turns still run to completion, just in waves.
	limit := runtime.GOMAXPROCS(0) * 8
	if limit < 1 {
		limit = 8
	}

	ctx, cancel := context.WithTimeout(t.Context(), 4*time.Minute)
	defer cancel()
	group, ctx := errgroup.WithContext(ctx)
	group.SetLimit(limit)

	for i := 0; i < n; i++ {
		group.Go(func() error { return runOneLoadTurn(ctx, stub) })
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a concurrent turn failed under fan-out N=%d: %v", n, err)
	}

	// Every session process must be reaped: no orphan stubharness child of this test process.
	if owned := waitForZeroStubChildren(t, 5*time.Second); owned != 0 {
		t.Fatalf("%d stubharness process(es) survived the fan-out — orphan leak (want 0)", owned)
	}
}

// runOneLoadTurn runs one full turn end-to-end over its own session and reaps it. It returns a
// non-nil error to fail the whole group fast on any race/regression, and never logs the canary.
func runOneLoadTurn(ctx context.Context, stub string) error {
	adapter, err := ompadapter.New(ompadapter.Config{Binary: stub})
	if err != nil {
		return err
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "omp", Model: "stub-deepseek"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"omp": adapter},
			Secrets:    secretstest.New(map[string]string{vaultReference: fakeCanary}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      integrationClock{},
		},
	)
	if err != nil {
		return err
	}

	session, err := pool.Open(ctx, agentsession.Spec{
		Workspace:  loadWorkspace(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "g-read", Tool: "read", ReadOnly: true}},
		Credential: secrets.Ref(vaultReference),
	})
	if err != nil {
		return err
	}
	defer func() { _ = session.Close(context.Background()) }() //nolint:errcheck // best-effort reap; the error path already returned.

	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "read the file"}); err != nil {
		return err
	}
	var events []agentsession.Event
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			if streamErr := stream.Err(); streamErr != nil {
				return streamErr
			}
			break
		}
		events = append(events, ev)
		// Re-pinned for contract revision R1: the fan-out drains to the TURN boundary — the same
		// event on both sides of the revision. Waiting for a session terminal post-R1 would hold
		// every one of the N goroutines to the context deadline, since a healthy session emits no
		// terminal until it is Closed.
		if ev.Terminal != nil || ev.IsTerminal() {
			break
		}
	}
	return assertLoadTurnInvariants(events)
}

// assertLoadTurnInvariants checks the per-turn correctness invariants WITHOUT a *testing.T (the
// fan-out goroutines report via error so the group fails fast and no canary is ever logged).
func assertLoadTurnInvariants(events []agentsession.Event) error {
	if len(events) == 0 {
		return errLoad("a concurrent turn produced no events")
	}
	boundary := events[len(events)-1]
	if boundary.Terminal == nil {
		return errLoad("a concurrent turn did not reach a boundary carrying a ledger")
	}
	if boundary.IsTerminal() {
		return errLoad("a concurrent turn ended the SESSION; a clean `agent_end` ends the TURN and the session takes the next Prompt")
	}
	if boundary.Terminal.Ledger.Harness != "omp" {
		return errLoad("a concurrent turn-boundary ledger lost the omp harness attribution")
	}
	// Seq is monotonic + gap-free even under fan-out (each session is independent).
	var prev uint64
	for i := range events {
		if events[i].Seq != prev+1 {
			return errLoad("a concurrent turn produced a Seq gap")
		}
		prev = events[i].Seq
	}
	// The fake canary must never appear on any field of any event on this stream.
	for i := range events {
		for _, field := range []string{
			events[i].SessionID, events[i].TurnID, string(events[i].Extension),
		} {
			if strings.Contains(field, fakeCanary) {
				return errLoad("the credential canary leaked onto a concurrent stream")
			}
		}
		if t := events[i].Terminal; t != nil && (strings.Contains(t.ResultText, fakeCanary) || strings.Contains(t.Detail, fakeCanary)) {
			return errLoad("the credential canary leaked onto a concurrent terminal")
		}
	}
	return nil
}

// loadAssertionError is the typed error the fan-out goroutines return so the errgroup fails the
// whole run fast on any per-turn invariant violation (and no canary is ever logged).
type loadAssertionError string

func (e loadAssertionError) Error() string { return string(e) }

func errLoad(msg string) error { return loadAssertionError(msg) }

// loadWorkspace returns a per-turn ephemeral workspace dir (the stub writes nothing, so a shared
// temp root is fine; a fresh subdir keeps sessions isolated).
func loadWorkspace() string {
	dir, err := os.MkdirTemp("", "omp-load-")
	if err != nil {
		return os.TempDir()
	}
	return dir
}

// waitForZeroStubChildren polls until no stubharness child of this process remains or the window
// elapses, returning the final count. A genuinely orphaned process stays present past the window.
func waitForZeroStubChildren(t *testing.T, window time.Duration) int {
	t.Helper()
	deadline := time.Now().Add(window)
	for {
		n, err := liveStubChildren()
		if err != nil {
			t.Fatalf("counting stub children: %v", err)
		}
		if n == 0 || time.Now().After(deadline) {
			return n
		}
		time.Sleep(25 * time.Millisecond)
	}
}
