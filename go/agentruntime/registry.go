package agentruntime

import (
	"context"
	"sync"
)

// activeAgent is the cancelable registration of the ONE running agent the sidecar supervises: the
// kill path (a control KILL verb) consults this to cancel the agent's context immediately, the hard
// stop that bypasses a graceful drain. IsActive is the liveness bit the HTTP /health probe reads.
//
// The sidecar is one-agent-per-pod (ADR-0022 §4 on kubernetes), but the registry is keyed by AgentID
// and built as a map so the docker-multiplexed dev path (Phase 4: "multiplexed on docker") and a
// future N-agent pod register without a structural change — additive by construction.
type activeAgent struct {
	id     AgentID
	cancel context.CancelFunc
	active bool
}

// registry is the concurrent-safe table of active agents. A Register installs a cancelable entry; a
// Kill cancels it and marks it inactive; IsActive answers the probe. All state is guarded by mu so a
// control-goroutine Kill never races the run-loop's Register/Deregister.
type registry struct {
	mu     sync.Mutex
	agents map[AgentID]*activeAgent
}

// newRegistry constructs an empty registry.
func newRegistry() *registry {
	return &registry{agents: make(map[AgentID]*activeAgent)}
}

// register installs a cancelable, active entry for id and returns it. A second register for the same
// id replaces the prior entry's cancel (the re-adopt case) without canceling the prior — the caller
// owns ordering. Concurrency-safe.
func (r *registry) register(id AgentID, cancel context.CancelFunc) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.agents[id] = &activeAgent{id: id, cancel: cancel, active: true}
}

// kill cancels the agent's context immediately and marks it inactive, returning true if an active
// agent was found and killed (false if unknown/already inactive — idempotent, no double-cancel).
// This is the hard-stop the KILL verb drives, distinct from a graceful STOP.
func (r *registry) kill(id AgentID) bool {
	r.mu.Lock()
	agent, ok := r.agents[id]
	if !ok || !agent.active {
		r.mu.Unlock()
		return false
	}
	agent.active = false
	cancel := agent.cancel
	r.mu.Unlock()
	cancel()
	return true
}

// deregister removes the agent from the table (run-loop exit), marking it inactive first so a
// concurrent IsActive reads false. Idempotent.
func (r *registry) deregister(id AgentID) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if agent, ok := r.agents[id]; ok {
		agent.active = false
		delete(r.agents, id)
	}
}

// isActive reports whether id is registered and still active (the HTTP /health/{id} liveness bit).
func (r *registry) isActive(id AgentID) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	agent, ok := r.agents[id]
	return ok && agent.active
}

// count returns how many agents are currently active — the /live readiness signal and a test
// introspection point (CountOwned for the lifecycle probe).
func (r *registry) count() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	n := 0
	for _, agent := range r.agents {
		if agent.active {
			n++
		}
	}
	return n
}
