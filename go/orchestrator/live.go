package orchestrator

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// liveHandle is the in-process ACTUAL for one agent: the open agentsession.Session and
// the provisioned workspace. It is the live object graph the orchestration record
// deliberately does NOT hold (rationale 2 — records hold refs, not handles); it lives in
// a side table keyed by AgentID so reconcile can Close the session (the harness reap)
// before Teardown (the pod reap) — the drain-then-reap order the contract fixes (§4).
//
// At v0 (single-node) this is also what the default in-process Probe reads to report the
// truthful actual. At multi-node the Probe queries the cluster instead and this table is
// the per-node cache; the record (a plain value) is unchanged.
type liveHandle struct {
	session   agentsession.Session
	workspace workspaceprovider.Workspace
}

// liveTable is the AgentID-keyed live-actual side table. Safe for concurrent use.
type liveTable struct {
	mu   sync.Mutex
	byID map[AgentID]liveHandle
}

// newLiveTable constructs an empty live-actual table.
func newLiveTable() *liveTable {
	return &liveTable{byID: make(map[AgentID]liveHandle)}
}

// putWorkspace records the provisioned workspace for an agent (set at provision time).
func (t *liveTable) putWorkspace(id AgentID, workspace workspaceprovider.Workspace) {
	t.mu.Lock()
	defer t.mu.Unlock()
	handle := t.byID[id]
	handle.workspace = workspace
	t.byID[id] = handle
}

// putSession records the open session for an agent (set at open/resume time).
func (t *liveTable) putSession(id AgentID, session agentsession.Session) {
	t.mu.Lock()
	defer t.mu.Unlock()
	handle := t.byID[id]
	handle.session = session
	t.byID[id] = handle
}

// get returns the live handle for an agent and whether it is present.
//
//nolint:gocritic // liveHandle holds two ports; returning it by value hands the caller an independent snapshot of the handle pair.
func (t *liveTable) get(id AgentID) (liveHandle, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	handle, ok := t.byID[id]
	return handle, ok
}

// drop removes the live handle for an agent (after reap).
func (t *liveTable) drop(id AgentID) {
	t.mu.Lock()
	defer t.mu.Unlock()
	delete(t.byID, id)
}

// observe reports the in-process actual for the requested ids (the default v0 Probe). An
// id with a live session reports SessionLive/WorkspaceLive true; an id with no live
// handle reports both false (the not-yet-provisioned or dropped-actual path).
//
// It does NOT fabricate SessionState: the in-process side table holds the Session HANDLE but
// the agentsession.Session interface exposes the inner agent-loop state only by tailing
// Events, which a per-pass Probe does not do. So SessionState is left at its zero value
// (the documented "not observed by this Probe" sentinel) rather than a hardcoded StateRunning
// the table cannot actually vouch for. A Probe that DOES observe the inner state (a multi-node
// cluster-query Probe, or one wired to the transcript) populates it, and driveRunning's
// unrecoverable-inner-state branch then acts on the truthful value.
func (t *liveTable) observe(_ context.Context, ids []AgentID) (map[AgentID]Actual, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := make(map[AgentID]Actual, len(ids))
	for _, id := range ids {
		handle, present := t.byID[id]
		actual := Actual{}
		if present {
			actual.WorkspaceLive = handle.workspace != nil
			actual.SessionLive = handle.session != nil
		}
		out[id] = actual
	}
	return out, nil
}

// ensureLive lazily constructs the live-actual table under the liveOnce guard.
func (p *Pool) ensureLive() *liveTable {
	p.liveOnce.Do(func() { p.live = newLiveTable() })
	return p.live
}

// defaultProbe is the in-process Probe the Pool binds when Deps.Probe is nil: it reads
// the live-actual side table. Multi-node swaps a cluster-query Probe with no surface
// change.
type defaultProbe struct{ table *liveTable }

// Observe reads the in-process actual for ids.
func (d defaultProbe) Observe(ctx context.Context, ids []AgentID) (map[AgentID]Actual, error) {
	return d.table.observe(ctx, ids)
}
