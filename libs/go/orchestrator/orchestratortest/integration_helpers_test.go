//go:build integration

package orchestratortest_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
)

// secretsRef is the seeded credential reference the integration arm threads through Spawn
// (resolved server-side at agentsession.Open; the value never rides the request/record).
func secretsRef() secrets.Reference {
	return secrets.Ref(orchestratortest.SeededCredentialRef)
}

// listAll pages through every agent the manager tracks (List is paginated; the scale
// tests track more agents than one page holds).
func listAll(t *testing.T, manager *orchestratortest.Manager) []orchestrator.Agent {
	t.Helper()
	var all []orchestrator.Agent
	cursor := ""
	for {
		page, err := manager.List(context.Background(), orchestrator.Filter{Cursor: cursor, Limit: 100})
		if err != nil {
			t.Fatalf("List: %v", err)
		}
		all = append(all, page.Agents...)
		if page.Next == "" || len(page.Agents) == 0 {
			return all
		}
		cursor = page.Next
	}
}

// isLimitError reports whether err is the typed MaxConcurrent admission refusal with the
// stable exhausted Kind.
func isLimitError(err error) bool {
	limit, ok := errors.AsType[*orchestrator.LimitError](err)
	if !ok || limit == nil {
		return false
	}
	return errors.KindOf(err) == errors.KindExhausted
}

// reconcilePump runs Reconcile on a 1ms ticker until stop is closed, on its own
// goroutine, so the verbs (Spawn/Stop/Resume) race the loop under the race detector. It
// returns a stop func that closes the ticker and joins the goroutine.
func reconcilePump(manager *orchestratortest.Manager) (stop func()) {
	done := make(chan struct{})
	closed := make(chan struct{})
	go func() {
		defer close(closed)
		ticker := time.NewTicker(time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				_, _ = manager.Reconcile(context.Background()) //nolint:errcheck // a pass error is non-fatal; the pump retries on the next tick.
			}
		}
	}()
	return func() {
		close(done)
		<-closed
	}
}

// stopAll records a Stop intent for every agent id (idempotent; an already-stopping agent
// is a benign no-op).
func stopAll(manager *orchestratortest.Manager, ids []orchestrator.AgentID) {
	for _, id := range ids {
		if id == "" {
			continue
		}
		_ = manager.Stop(context.Background(), id, "integration") //nolint:errcheck // idempotent Stop; an already-stopping agent is a benign no-op.
	}
}

// spawnAllConcurrently spawns count agents from concurrent goroutines and returns their
// ids in order (the concurrent-admission fan).
func spawnAllConcurrently(t *testing.T, manager *orchestratortest.Manager, count int) []orchestrator.AgentID {
	t.Helper()
	ids := make([]orchestrator.AgentID, count)
	var wg sync.WaitGroup
	for i := range count {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			agent, err := manager.Spawn(context.Background(), scaleRequest())
			if err != nil {
				t.Errorf("Spawn[%d]: %v", idx, err)
				return
			}
			ids[idx] = agent.ID
		}(i)
	}
	wg.Wait()
	return ids
}

// churnAgents concurrently Stops the even-indexed agents and drops the actual of the
// odd-indexed ones (so the loop moves them Running→Suspended for a later Resume).
func churnAgents(t *testing.T, manager *orchestratortest.Manager, ids []orchestrator.AgentID) {
	t.Helper()
	var wg sync.WaitGroup
	for i := range ids {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			id := ids[idx]
			if id == "" {
				return
			}
			if idx%2 == 0 {
				if err := manager.Stop(context.Background(), id, "integration"); err != nil {
					t.Errorf("Stop[%d]: %v", idx, err)
				}
				return
			}
			manager.Probe().Set(id, orchestrator.Actual{WorkspaceLive: false, SessionLive: false})
		}(i)
	}
	wg.Wait()
}

// resumeDropped issues a Resume for every odd-indexed (dropped) agent and restores its
// live actual so the pump re-attaches it.
func resumeDropped(manager *orchestratortest.Manager, ids []orchestrator.AgentID) {
	for i := 1; i < len(ids); i += 2 {
		if ids[i] == "" {
			continue
		}
		_ = manager.Resume(context.Background(), ids[i], "integration") //nolint:errcheck // a Resume racing the pump may find the agent already Running; a benign no-op.
		manager.Probe().Set(ids[i], liveActual)
	}
}

// registerReaper registers a t.Cleanup that drains every non-terminal agent the manager
// owns and converges the loop, so no workspace/session leaks past the test (the
// reap-everything-on-Cleanup discipline the brief's lifecycle guard requires). It then
// asserts no orphan remains.
func registerReaper(t *testing.T, manager *orchestratortest.Manager) {
	t.Helper()
	t.Cleanup(func() {
		// Best-effort: record a Stop for every live agent and drive the loop to terminal.
		page, err := manager.List(context.Background(), orchestrator.Filter{OnlyActive: true})
		if err == nil {
			for i := range page.Agents {
				_ = manager.Stop(context.Background(), page.Agents[i].ID, "cleanup") //nolint:errcheck // best-effort cleanup drain.
			}
		}
		for pass := 0; pass < 64; pass++ {
			report, rerr := manager.Reconcile(context.Background())
			if rerr != nil || report.Transitioned == 0 {
				break
			}
		}
		manager.AssertNoOrphans(t)
	})
}
