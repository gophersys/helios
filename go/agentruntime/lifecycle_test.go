//go:build lifecycle

package agentruntime_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"go.uber.org/goleak"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
)

// TestLifecycle_RuntimeDrainsCleanNoOrphans is the full-object-lifecycle conformance (ADR-0020
// dimension (c)) for the sidecar: construct → Use (Run to a graceful STOP) → first Close (a second
// STOP / the already-returned Run is a no-op) → CountOwned()==0 (the active-agent registration was
// deregistered, no orphan) — driven by testing.AssertLifecycle. The orphan-GOROUTINE half (the pump,
// heartbeat ticker, and control subscription must all be reaped) is asserted by the surrounding
// goleak.VerifyNone. Tagged `//go:build lifecycle` so the heavy drive stays out of the fast unit run.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling would make it flaky.
func TestLifecycle_RuntimeDrainsCleanNoOrphans(t *testing.T) {
	defer goleak.VerifyNone(
		t,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
	report := &tReport{t: t}
	harness := &tHarness{t: t}
	libtesting.AssertLifecycle(context.Background(), harness, report, newRuntimeProbe)
}

// runtimeProbe is the testing.LifecycleProbe binding for a running sidecar. Its "owned resource" is
// the active-agent registration: Use starts Run and stops it via a STOP verb; Close is idempotent
// (Run has returned); CountOwned reads the active-agent count off the /live probe, which must be 0
// after the run drained.
type runtimeProbe struct {
	runtime *agentruntime.Runtime
	bus     *agentruntimetest.FakeBus
	cancel  context.CancelFunc
	done    chan agentruntime.TerminationReason
}

// newRuntimeProbe constructs a fresh sidecar over the fake bus + a real agentsession session, starts
// Run, and returns the probe. The teardown cancels the parent ctx as a backstop.
//
//nolint:ireturn // contract: LifecycleFactory returns the LifecycleProbe port (the frozen seam).
func newRuntimeProbe(_ context.Context, _ libtesting.Harness) (libtesting.LifecycleProbe, func(), error) {
	runtime, bus, _ := buildLifecycleRuntime()
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan agentruntime.TerminationReason, 1)
	go func() {
		reason, _ := runtime.Run(ctx) //nolint:errcheck // the lifecycle probe asserts the reason via CountOwned/teardown, not the run error.
		done <- reason
	}()
	probe := &runtimeProbe{runtime: runtime, bus: bus, cancel: cancel, done: done}
	teardown := func() { cancel() }
	return probe, teardown, nil
}

// Use drives the sidecar through its working phase, then a graceful STOP to a clean drain.
func (p *runtimeProbe) Use(_ context.Context) error {
	<-p.bus.Subscribed()
	// Wait for the run loop to be live (a heartbeat published) before steering it.
	deadline := time.After(5 * time.Second)
	for len(p.bus.Heartbeats()) == 0 {
		select {
		case <-deadline:
			return errLifecycleNoHeartbeat
		case <-time.After(2 * time.Millisecond):
		}
	}
	p.bus.Inject(agentruntime.ControlMessage{AgentID: agentruntimetest.AgentID, Verb: agentruntime.VerbStop})
	<-p.done
	return nil
}

// Close is idempotent: Run has already returned (Use drained it); a second close cancels the backstop
// and is a no-op. It returns nil both times so AssertLifecycle's double-close check passes.
func (p *runtimeProbe) Close(_ context.Context) error {
	p.cancel()
	return nil
}

// CountOwned reads the active-agent count off the /live probe body ("live agents=N"). After the run
// drained, the registration is deregistered, so the count MUST be 0 (no orphan).
func (p *runtimeProbe) CountOwned(_ context.Context) (int, error) {
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/live", http.NoBody)
	p.runtime.ProbeHandler().ServeHTTP(recorder, request)
	body := recorder.Body.String()
	const marker = "agents="
	index := strings.Index(body, marker)
	if index < 0 {
		return 0, errLifecycleProbeBody
	}
	field := strings.TrimSpace(body[index+len(marker):])
	count, err := strconv.Atoi(field)
	if err != nil {
		return 0, errLifecycleProbeBody
	}
	return count, nil
}
