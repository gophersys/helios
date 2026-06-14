//go:build lifecycle || load

package agentruntime_test

import (
	"context"
	"testing"
	"time"

	libtesting "github.com/gophersys/libs/go/testing"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// lifecycle/load timing: a short heartbeat so the probe observes liveness fast; a bounded drain.
const (
	lifecycleHeartbeat    = 5 * time.Millisecond
	lifecycleDrainTimeout = 5 * time.Second
)

// newLifecycleSessions builds an idle interactive agentsession session (no script — it ends only on a
// control verb), the shape the lifecycle + load probes drive.
//
//nolint:ireturn // returns the agentsession.Factory port (the frozen surface).
func newLifecycleSessions() agentsession.Factory { return agentruntimetest.NewSessionsNoT() }

// Shared lifecycle/load support: the testing.Report + testing.Harness adapters over *testing.T, the
// lifecycle/load runtime builder, and the lane sentinel errors. Untagged so both the `lifecycle` and
// `load` lanes (and the fast lane, harmlessly) compile it.

// tReport adapts *testing.T to the testing.Report assertion sink.
type tReport struct{ t *testing.T }

func (r *tReport) Errorf(format string, args ...any) { r.t.Errorf(format, args...) }
func (r *tReport) Fatalf(format string, args ...any) { r.t.Fatalf(format, args...) }
func (r *tReport) Skipf(format string, args ...any)  { r.t.Skipf(format, args...) }

// tHarness adapts *testing.T to the testing.Harness port. Only Cleanup and Context are exercised by
// AssertLifecycle; the deterministic-source accessors are part of the frozen 5-method port and are
// never called on this path.
type tHarness struct {
	t *testing.T
}

//nolint:ireturn // the testing.Harness port returns the Clock interface; this stub is never called on the lifecycle/load path.
func (*tHarness) Clock() libtesting.Clock { return nil }

//nolint:ireturn // the testing.Harness port returns the RandomSource interface; this stub is never called on the lifecycle/load path.
func (*tHarness) RandomSource() libtesting.RandomSource { return nil }

func (*tHarness) Has(string) bool { return false }

func (h *tHarness) Context() context.Context { return context.Background() }

func (h *tHarness) Cleanup(fn func()) { h.t.Cleanup(fn) }

// lane sentinel errors (declared, not invented inline — the errors contract).
var (
	errLifecycleNoHeartbeat = errors.New(errors.KindDeadline, "lifecycle probe: no heartbeat before Use")
	errLifecycleProbeBody   = errors.New(errors.KindInternal, "lifecycle probe: malformed /live body")
)

// buildLifecycleRuntime constructs a sidecar over a fresh fake bus + a real agentsession session
// (the interactive idle harness that ends only on a control verb), the shape the lifecycle + load
// probes drive. It returns the runtime + the fake bus (the probe steers it via the bus).
func buildLifecycleRuntime() (*agentruntime.Runtime, *agentruntimetest.FakeBus, *agentruntimetest.FakeObserver) {
	bus := agentruntimetest.NewFakeBus()
	observer := agentruntimetest.NewFakeObserver()
	runtime, err := agentruntime.New(
		agentruntime.Config{
			AgentID:           agentruntimetest.AgentID,
			Spec:              agentruntimetest.Spec(),
			HeartbeatInterval: lifecycleHeartbeat,
			DrainTimeout:      lifecycleDrainTimeout,
		},
		agentruntime.Deps{
			Sessions: newLifecycleSessions(),
			Bus:      bus,
			Observer: observer,
			Clock:    agentruntimetest.FixedClock{},
		},
	)
	if err != nil {
		panic(err) // a construction failure in a test builder is a programmer error, surfaced loudly
	}
	return runtime, bus, observer
}
