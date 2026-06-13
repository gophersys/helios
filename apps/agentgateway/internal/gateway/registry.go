package gateway

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
)

// liveSession bundles an open agentsession.Session with the orchestrator AgentID it was
// opened for, so the gateway tails Events and issues Control against the live handle while
// the record plane (orchestrator) tracks the lifecycle. The agentsession SessionID and the
// orchestrator AgentID are the same join key by contract (orchestrator.AgentID "equals the
// agentsession SessionID once the session is open"); the registry keys on the AgentID the
// gateway minted at create time so every route resolves with one lookup.
type liveSession struct {
	agentID   orchestrator.AgentID
	sessionID string // the canonical agentsession SessionID (discovered from a streamed event); "" until known
	session   agentsession.Session
}

// registry is the gateway's in-memory map of live sessions keyed by AgentID. It is the
// gateway's hold on the live plane: orchestrator records intent and reconciles, but the
// live agentsession.Session handle (the thing Events/Control act on) lives HERE so the SSE
// route and the control channel reach it directly without orchestrator proxying the stream.
//
// Concurrency: safe for concurrent use. Lookups (every SSE/control request) take a read
// lock; register/remove take a write lock. closeAll reaps every session on shutdown so no
// harness goroutine leaks.
type registry struct {
	mu       sync.RWMutex
	sessions map[orchestrator.AgentID]*liveSession
	// idsByAgent retains the agentsession SessionID for an AgentID even AFTER the live
	// session is removed (Stop/Close), so the post-mortem transcript route can read the
	// persisted Run by its SessionID once the agent is terminal (REQ-0020 queryable after
	// end). It is append-on-discovery and never cleared on remove.
	idsByAgent map[orchestrator.AgentID]string
}

// newRegistry constructs an empty registry.
func newRegistry() *registry {
	return &registry{
		sessions:   make(map[orchestrator.AgentID]*liveSession),
		idsByAgent: make(map[orchestrator.AgentID]string),
	}
}

// register records a live session under its AgentID. If one already exists for the id it
// is replaced (the prior handle is returned so the caller reaps it — a resume re-attach).
//
//nolint:ireturn // returns the displaced agentsession.Session port for the caller to reap (the frozen surface).
func (r *registry) register(agentID orchestrator.AgentID, sessionID string, session agentsession.Session) agentsession.Session {
	r.mu.Lock()
	defer r.mu.Unlock()
	var displaced agentsession.Session
	if existing, ok := r.sessions[agentID]; ok {
		displaced = existing.session
	}
	r.sessions[agentID] = &liveSession{agentID: agentID, sessionID: sessionID, session: session}
	if sessionID != "" {
		r.idsByAgent[agentID] = sessionID
	}
	return displaced
}

// lookup returns the live session for an AgentID and whether it is present.
//
//nolint:ireturn // returns the agentsession.Session port the routes act on (the frozen surface).
func (r *registry) lookup(agentID orchestrator.AgentID) (agentsession.Session, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	entry, ok := r.sessions[agentID]
	if !ok {
		return nil, false
	}
	return entry.session, true
}

// sessionID returns the canonical agentsession SessionID discovered for an AgentID and
// whether it is known. It survives remove (Stop/Close), so the post-mortem transcript
// route resolves the SessionID for a terminal agent.
func (r *registry) sessionID(agentID orchestrator.AgentID) (string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	id, ok := r.idsByAgent[agentID]
	return id, ok
}

// remove drops the live session for an AgentID and returns it for the caller to reap.
//
//nolint:ireturn // returns the removed agentsession.Session port for the caller to reap (the frozen surface).
func (r *registry) remove(agentID orchestrator.AgentID) (agentsession.Session, bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	entry, ok := r.sessions[agentID]
	if !ok {
		return nil, false
	}
	delete(r.sessions, agentID)
	return entry.session, true
}

// closeAll reaps every live session (idempotent), bounded by ctx so shutdown never hangs
// on a wedged harness. After closeAll the registry is empty. This is the no-leak
// guarantee: every Open is matched by a Close on shutdown.
func (r *registry) closeAll(ctx context.Context) {
	r.mu.Lock()
	pending := make([]*liveSession, 0, len(r.sessions))
	for _, entry := range r.sessions {
		pending = append(pending, entry)
	}
	r.sessions = make(map[orchestrator.AgentID]*liveSession)
	r.mu.Unlock()

	for _, entry := range pending {
		_ = entry.session.Close(ctx) //nolint:errcheck // best-effort reap on shutdown; nothing to act on once we are tearing down.
	}
}
