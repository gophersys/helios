//go:build load

package agentsession_test

import (
	"context"
	"os"
	"strconv"
	"testing"
	"time"

	"go.uber.org/goleak"
	"golang.org/x/sync/errgroup"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500
// in-process; ADR-0020 dimension (e)).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentTailersFanoutRaceClean opens N concurrent FromSeq tailers over ONE
// session and drives one prompt; every tailer drains its own gap-free Seq stream to terminal.
// It stresses the broadcaster fan-out + the demotion/catch-up replay path under -race at
// fan-out, and goleak asserts the goroutine high-water returns to baseline afterward (every
// subscriber detached, the pump reaped) — ADR-0020 dimension (e).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would make the high-water assertion flaky, so the fan-out load runs serially.
func TestLoad_ConcurrentTailersFanoutRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	session, _ := openLoadSession(t)

	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()

	group, groupCtx := errgroup.WithContext(ctx)
	for i := range n {
		cursor := agentsession.FromSeq(uint64(i % 4))
		slow := i%5 == 0
		group.Go(func() error {
			stream := session.Events(groupCtx, cursor)
			return drainToTerminal(groupCtx, stream, slow)
		})
	}
	if _, err := session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
		t.Fatalf("Prompt: %v", err)
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a tailer faulted under fan-out: %v", err)
	}
	if err := session.Close(context.Background()); err != nil {
		t.Fatalf("Close: %v", err)
	}
}

// TestLoad_ManyConcurrentSessionsRaceClean opens many sessions concurrently through one Pool,
// drives each to its terminal, and reaps each on its own goroutine. It proves the Pool +
// per-session pump + broadcaster scale across independent sessions under -race with no shared
// state corruption, and goleak proves every pump goroutine is reaped (no orphan per session).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine assertion.
func TestLoad_ManyConcurrentSessionsRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	// Bound the per-session fan-out so the session count stays meaningful without exploding
	// the goroutine budget; EDEN_LOAD_N still scales the session count in real-pod runs.
	sessions := loadN() / 10
	if sessions < 10 {
		sessions = 10
	}

	pool := newLoadPool(t)
	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()

	group, groupCtx := errgroup.WithContext(ctx)
	for range sessions {
		group.Go(func() error {
			session, err := pool.Open(groupCtx, loadSpec())
			if err != nil {
				return err
			}
			stream := session.Events(groupCtx, agentsession.FromSeq(0))
			if _, err := session.Control(groupCtx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "go"}); err != nil {
				_ = session.Close(context.Background()) //nolint:errcheck // best-effort reap on the error path; the Control error is the actionable outcome.
				return err
			}
			if err := drainToTerminal(groupCtx, stream, false); err != nil {
				_ = session.Close(context.Background()) //nolint:errcheck // best-effort reap on the error path; the drain error is the actionable outcome.
				return err
			}
			return session.Close(context.Background())
		})
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a session faulted under load: %v", err)
	}
}

// ── load harness ──────────────────────────────────────────────────────────────.

const loadRef = "vault://eden/anthropic#load" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

var loadKey = agentsession.RouteKey{Role: "assistant"}

// loadClock is a deterministic Clock for the load harness.
type loadClock struct{}

func (loadClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// newLoadPool builds a Pool over a fresh scripted fake adapter (one Spawn per Open) and a
// real in-memory transcript.
func newLoadPool(t *testing.T) *agentsession.Pool {
	t.Helper()
	adapter := agentsessiontest.New(agentsessiontest.CanonicalScript()...)
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			loadKey: {Harness: "fake", Model: "fake-fable-5"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    secretstest.New(map[string]string{loadRef: "S3CR3T-load-do-not-leak"}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      loadClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return pool
}

// loadSpec returns the canonical load Spec.
func loadSpec() agentsession.Spec {
	return agentsession.Spec{
		Workspace:  "/workspace/eden",
		Routing:    loadKey,
		Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		Credential: secrets.Ref(loadRef),
	}
}

// openLoadSession opens one live session over a fresh load pool, reaped on Cleanup.
//
//nolint:ireturn // returns the agentsession.Session port (the contract surface the consumer holds).
func openLoadSession(t *testing.T) (agentsession.Session, *agentsession.Pool) {
	t.Helper()
	pool := newLoadPool(t)
	session, err := pool.Open(context.Background(), loadSpec())
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) }) //nolint:errcheck // best-effort session reap on test cleanup.
	return session, pool
}

// drainToTerminal reads a stream to its terminal; when slow is set it yields between reads to
// force a live-subscriber overflow -> demotion -> transcript catch-up. Returns the stream's
// terminal fault, if any.
func drainToTerminal(ctx context.Context, stream agentsession.Stream, slow bool) error {
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			return stream.Err()
		}
		if ev.IsTerminal() {
			return nil
		}
		if slow {
			time.Sleep(time.Millisecond)
		}
	}
}
