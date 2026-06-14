//go:build load

package agentruntime_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500 in-process;
// ADR-0020 dimension (e)).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ManySidecarsRaceCleanAllReaped runs N concurrent sidecars — each pumping a real
// agentsession session over the canonical script to a terminal and publishing to its own fake bus —
// under the race detector, asserting every Run returns a clean terminal reason, every event stream
// reached its bus Seq-ordered, and the goroutine high-water returns to baseline (goleak.VerifyNone):
// no pump/heartbeat/subscription goroutine leaked across the fan-out. 0 races; all N reaped.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; it runs serially.
func TestLoad_ManySidecarsRaceCleanAllReaped(t *testing.T) {
	defer goleak.VerifyNone(
		t,
		goleak.IgnoreTopFunction("internal/poll.runtime_pollWait"),
	)
	n := loadN()
	var workers sync.WaitGroup
	workers.Add(n)
	reasons := make([]agentruntime.TerminationReason, n)
	seqOK := make([]bool, n)

	for i := range n {
		go func(index int) {
			defer workers.Done()
			bus := agentruntimetest.NewFakeBus()
			observer := agentruntimetest.NewFakeObserver()
			runtime, err := agentruntime.New(
				agentruntime.Config{
					AgentID:           agentruntime.AgentID("agent-load-" + strconv.Itoa(index)),
					Spec:              agentruntimetest.Spec(),
					HeartbeatInterval: 20 * time.Millisecond,
					DrainTimeout:      5 * time.Second,
					InitialPrompt:     "go", // seed so the scripted body streams to a terminal
				},
				agentruntime.Deps{
					Sessions: agentruntimetest.NewSessionsNoT(agentruntimetest.CanonicalScript()...),
					Bus:      bus,
					Observer: observer,
					Clock:    agentruntimetest.FixedClock{},
				},
			)
			if err != nil {
				t.Errorf("sidecar %d construct: %v", index, err)
				return
			}
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			reason, runErr := runtime.Run(ctx)
			if runErr != nil {
				t.Errorf("sidecar %d run: %v", index, runErr)
				return
			}
			reasons[index] = reason
			seqOK[index] = busSeqOrdered(bus.Events())
		}(i)
	}
	workers.Wait()

	for i := range n {
		if reasons[i] != agentruntime.TerminationSessionEnd {
			t.Errorf("sidecar %d reason = %s, want session-end", i, reasons[i])
		}
		if !seqOK[i] {
			t.Errorf("sidecar %d event stream was not Seq-ordered/gap-free", i)
		}
	}
}

// busSeqOrdered reports whether the published envelopes are strictly Seq-ordered with no holes.
func busSeqOrdered(events []agentruntime.EventEnvelope) bool {
	var prev uint64
	for i := range events {
		if events[i].Seq != prev+1 {
			return false
		}
		prev = events[i].Seq
	}
	return len(events) > 0
}
