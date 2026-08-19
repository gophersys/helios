//go:build lifecycle

// The full-object-lifecycle conformance (ADR-0020 dimension (c)) for the omp adapter's closeable
// handle — the live agentsession.Session backed by the REAL rpcConn driving ONE long-lived
// stub-harness subprocess. It drives testing.AssertLifecycle over a probe whose owned resource is
// that ONE session process: construct -> use (one real Prompt on the live session) -> first Close
// -> SECOND Close is a no-op (idempotent) -> CountOwned()==0 (no orphan stubharness process left
// parented to this test). The orphan-GOROUTINE half (the pump goroutine must reap, no scanner
// left attached) is asserted by the surrounding goleak.VerifyNone. Tagged `//go:build lifecycle`
// so the heavy spawn/double-close/reap drive stays out of the fast unit run.
package ompadapter_test

import (
	"context"
	"testing"
	"time"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/testing/testingtest"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets"
)

// TestLifecycle_SessionDoubleCloseIdempotentNoOrphanProcess drives the lifecycle conformance
// over a real stub-subprocess-backed session. It is NOT t.Parallel(): CountOwned scans /proc for
// stubharness children of THIS process, so running it alongside other subprocess-spawning tests
// would miscount.
//
//nolint:paralleltest // see the doc comment: CountOwned scans /proc for this process's children.
func TestLifecycle_SessionDoubleCloseIdempotentNoOrphanProcess(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of dimension (c)

	stub := buildStub(t)
	report := testingtest.NewReport(t)
	harness := testingtest.NewHarness(t)
	libtesting.AssertLifecycle(context.Background(), harness, report, newOmpSessionProbe(t, stub))
}

// ompSessionProbe is the testing.LifecycleProbe binding for the omp adapter's Session. Its owned
// resource is the ONE long-lived session process: after Use drives a Prompt on it and Close reaps
// the conn, CountOwned counts the live stubharness children of THIS process — which must be zero.
type ompSessionProbe struct {
	session agentsession.Session
}

// newOmpSessionProbe returns the testing.LifecycleFactory the driver invokes once: it builds a
// real Pool over the stub-binary adapter and opens a ready Session.
func newOmpSessionProbe(t *testing.T, stub string) libtesting.LifecycleFactory {
	t.Helper()
	return func(ctx context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
		adapter, err := ompadapter.New(ompadapter.Config{Binary: stub})
		if err != nil {
			return nil, nil, err
		}
		pool := newPool(t, adapter)
		session, err := pool.Open(ctx, agentsession.Spec{
			Workspace:  t.TempDir(),
			Routing:    agentsession.RouteKey{Role: "assistant"},
			Grants:     []agentsession.ToolGrant{{ID: "g-read", Tool: "read", ReadOnly: true}},
			Credential: secrets.Ref(vaultReference),
		})
		if err != nil {
			return nil, nil, err
		}
		probe := &ompSessionProbe{session: session}
		teardown := func() { _ = probe.session.Close(context.Background()) } //nolint:errcheck // final best-effort reap so a failed assertion never leaks the session.
		return probe, teardown, nil
	}
}

// Use exercises the live session once: open a tail, prompt, and drain to the TURN BOUNDARY so
// the conn spawns one real stub process and reaps it through the full path before Close.
//
// Re-pinned for contract revision R1: the session under lifecycle here is one that SURVIVES its
// turn, so Use must stop on the boundary payload — the same event on both sides of the revision.
// Waiting for a session terminal would wait for one that never comes: post-R1 the terminal is
// what the driver's own Close produces, one step later, and a Use that blocks on it turns the
// lifecycle probe into a deadlock on its own next step.
func (p *ompSessionProbe) Use(ctx context.Context) error {
	stream := p.session.Events(ctx, agentsession.FromSeq(0))
	if _, err := p.session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "read the file"}); err != nil {
		return err
	}
	for {
		ev, ok := stream.Next(ctx)
		if !ok {
			return stream.Err()
		}
		if ev.Terminal == nil {
			continue
		}
		if ev.IsTerminal() {
			return errTurnEndedTheSession(ev.Kind)
		}
		return nil
	}
}

// errTurnEndedTheSession names the pre-R1 defect the lifecycle probe hits: the harness's one
// turn ended the SESSION, so the handle the driver is about to Close is already dead and the
// construct->use->close->double-close ladder never runs against a live session.
func errTurnEndedTheSession(kind agentsession.EventKind) error {
	return lifecycleAssertionError("the omp turn ended the SESSION on a " + kind.String() +
		" terminal; a clean `agent_end` is a TURN boundary and the session must still be alive for Close to reap")
}

// lifecycleAssertionError is a tiny error type so the probe reports a contract violation without
// pulling the errors lib into this lane's surface.
type lifecycleAssertionError string

func (e lifecycleAssertionError) Error() string { return string(e) }

// Close closes the session. The library + conn guarantee Close is idempotent, so the driver's
// SECOND call must also return nil (the double-close invariant).
func (p *ompSessionProbe) Close(ctx context.Context) error { return p.session.Close(ctx) }

// CountOwned reports how many stub-harness child processes this test process still owns. After
// the session's double-Close it must read zero — the one session process was reaped, no orphan.
// A short settle accounts for the kernel reaping a just-exited child the conn already Wait()ed.
func (p *ompSessionProbe) CountOwned(context.Context) (int, error) {
	// The conn reaps the session process via command.Wait() at Close; give a just-finished reap a
	// brief moment to complete before counting (bounded, not a sleep race — a leaked process would
	// still be present after this window and fail the count).
	deadline := time.Now().Add(2 * time.Second)
	for {
		n, err := liveStubChildren()
		if err != nil {
			return 0, err
		}
		if n == 0 || time.Now().After(deadline) {
			return n, nil
		}
		time.Sleep(20 * time.Millisecond)
	}
}
