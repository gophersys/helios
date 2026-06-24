package workspaceprovider

import "sync"

// The workspace lifecycle State machine (types.go State doc): legal transitions are enforced by
// the LIBRARY, not the adapter. The legalTransitions table below is the SINGLE source of truth; the
// sketch here mirrors it edge-for-edge so a reader sees the shape, but the table — not this prose —
// is authoritative (10 §9, and the very drift this finding fixed):
//
//	Provisioning → {Ready, Running, Degraded, Evicted, Gone}
//	Ready        → {Running, Degraded, Evicted, Gone, Provisioning}
//	Running      → {Ready, Degraded, Evicted, Gone}
//	Degraded     → {Ready, Running, Evicted, Gone}
//	Evicted      → {Gone, Provisioning}              (the drift signal: reaped or re-provisioned)
//	Gone         → {}                                (terminal: never transitions out)
//
// plus the always-legal self-transition (a repeated Status read of the same State) and the initial
// entry (the first observed State from the zero machine). This file backs that invariant with code
// (it was previously documented but unimplemented — half-wired growth); the conformance
// caseStateTransitionGuard drives an adapter through an ILLEGAL transition (Gone → Ready) and
// asserts the library rejects it, turning the doc claim into an executed test.

// legalTransitions is the closed adjacency set of the documented State graph. A State maps to the
// set of States it may transition INTO. A self-transition (s → s) and the initial entry are handled
// in the guard, not the table. Gone is terminal: it has no outgoing edges.
var legalTransitions = map[State]map[State]bool{
	StateProvisioning: {StateReady: true, StateRunning: true, StateGone: true, StateDegraded: true, StateEvicted: true},
	StateReady:        {StateRunning: true, StateDegraded: true, StateEvicted: true, StateGone: true, StateProvisioning: true},
	StateRunning:      {StateReady: true, StateDegraded: true, StateEvicted: true, StateGone: true},
	StateDegraded:     {StateReady: true, StateRunning: true, StateEvicted: true, StateGone: true},
	StateEvicted:      {StateGone: true, StateProvisioning: true},
	StateGone:         {}, // terminal: never transitions out
}

// stateMachine tracks the last-observed State of one workspace so the library can enforce the
// documented legal-transition set on every Status/Supervised read. It is safe for concurrent use
// (the Workspace concurrent-use guarantee): many callers may Status one workspace at once.
type stateMachine struct {
	mu      sync.Mutex
	current State
	started bool
}

// observe records a newly-read State and reports whether the transition from the last-observed
// State was LEGAL. The first observation (the initial entry) and a self-transition are always
// legal; a terminal Gone never transitions, so any move OUT of Gone is illegal; otherwise the move
// must be in legalTransitions[current]. On a legal transition the machine advances; on an illegal
// one the machine does NOT advance (the caller rejects the read, so the last good State is kept).
func (m *stateMachine) observe(next State) bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	if !m.started {
		m.started = true
		m.current = next
		return true
	}
	if m.current == next {
		return true // a repeated read of the same State is always legal
	}
	if legalTransitions[m.current][next] {
		m.current = next
		return true
	}
	return false
}

// last reports the last-observed (legal) State the machine advanced to — used to render the From
// of an IllegalStateTransitionError after observe rejected a move.
func (m *stateMachine) last() State {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.current
}
