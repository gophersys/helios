package orchestratorservice

import (
	"context"
	"strings"
	"sync"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
)

// namespacingStore is the composition-root DESIRED-STORE decorator that bridges the two id
// spaces the orchestrator.Pool and the production postgresstore.PostgresStore each own — the ONE
// piece of wiring the docker-first composition needs, and a deterministic bijection, never a
// redefinition of either contract.
//
// THE MISMATCH it bridges: the orchestrator.Pool mints a BARE, process-unique id (agent-<n>
// from a single monotonic counter, manager.go newAgentID) and uses it as the agent's stable
// handle for its whole life — the in-process side tables (the spawn-inputs fold material, the
// live Session/Workspace) and the workspace ownership-domain labels are all keyed on the BARE
// id. The production postgresstore keys on a PROJECT-NAMESPACED id (agent-<project>-<n>, the
// cross-project-collision fix) and REJECTS a bare id at Put (postgresstore.go isProjectNamespaced).
// Composing the Pool directly over the production store would therefore FAIL at the first Spawn.
//
// THE BRIDGE: this decorator namespaces on the way DOWN (Put rewrites the bare id to the
// MintAgentID form keyed on the agent's own Tenant.ProjectID) and de-namespaces on the way UP
// (Get/List return records carrying the BARE id the Pool expects), so the Pool's bare-id side
// tables stay coherent while the store's rows are globally unique. It binds the frozen 3-method
// orchestrator.DesiredStore (Put/Get/List); it accepts the narrow DesiredStore port and the
// concrete *postgresstore.PostgresStore (the latter for the Delete reap seam the store adds
// beyond the port — return-concrete on the underlying store, accept-interface here).
//
// Get/Delete take ONLY an id (no tenant), so to namespace them the decorator keeps a small
// in-process bare->namespaced index it populates on Put (the bare id is process-unique within
// one Pool, so the index is unambiguous). A Get for an id this process never Put is looked up
// directly (it may already be the namespaced form — e.g. a record reloaded after restart),
// preserving the store's own NotFoundError contract.
type namespacingStore struct {
	inner *postgresstore.PostgresStore

	mu sync.RWMutex
	// namespaced maps a bare process-local id (agent-<n>) to the project-namespaced store id
	// (agent-<project>-<n>) Put assigned it. It is the reverse-lookup Get/Delete consult.
	namespaced map[orchestrator.AgentID]orchestrator.AgentID
}

// static assertion: the decorator binds the frozen orchestrator.DesiredStore port the Pool holds.
var _ orchestrator.DesiredStore = (*namespacingStore)(nil)

// newNamespacingStore wraps the production store with the bare<->namespaced id bridge.
func newNamespacingStore(inner *postgresstore.PostgresStore) *namespacingStore {
	return &namespacingStore{
		inner:      inner,
		namespaced: make(map[orchestrator.AgentID]orchestrator.AgentID),
	}
}

// Put namespaces the agent's bare id to the project-namespaced store form (idempotent and
// deterministic on the agent's own sequence + Tenant.ProjectID) and records the bare->namespaced
// mapping so a later Get/Delete by the bare id resolves. It then delegates to the production
// store with the record rewritten to carry the namespaced id (so the row PK is the global id).
//
//nolint:gocritic // Agent is the contract's copyable serializable record; the decorator rewrites its own copy by value.
func (s *namespacingStore) Put(ctx context.Context, agent orchestrator.Agent) error {
	bare := agent.ID
	namespaced := s.toNamespaced(bare, agent.Tenant)
	if namespaced != bare {
		s.mu.Lock()
		s.namespaced[bare] = namespaced
		s.mu.Unlock()
		agent.ID = namespaced
		// The opaque SessionRef equals the AgentID by the orchestrator contract; keep it aligned
		// with the namespaced id so a reloaded record's Session ref round-trips to the same row.
		if agent.Session == orchestrator.SessionRef(bare) {
			agent.Session = orchestrator.SessionRef(namespaced)
		}
	}
	return s.inner.Put(ctx, agent) //nolint:wrapcheck // the production store already returns a wrapped, classified error (KindInvalid/Unavailable); re-wrapping double-classifies.
}

// Get resolves the bare id to its namespaced store id (via the Put-populated index, else the id
// as-given) and returns the record with the BARE id restored, so the Pool sees its own id space.
func (s *namespacingStore) Get(ctx context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	agent, err := s.inner.Get(ctx, s.lookupNamespaced(id))
	if err != nil {
		return orchestrator.Agent{}, err //nolint:wrapcheck // the store already returns a wrapped, classified NotFoundError; re-wrapping double-classifies.
	}
	return s.restoreBare(agent), nil
}

// List delegates to the store and restores each returned record's bare id, so the Pool's
// running-set view (and its reconcile pass) operates entirely in the bare id space.
//
//nolint:gocritic // contract §3: DesiredStore.List takes the Filter by value (the frozen port surface).
func (s *namespacingStore) List(ctx context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	page, err := s.inner.List(ctx, filter)
	if err != nil {
		return orchestrator.Page{}, err //nolint:wrapcheck // the store already returns a wrapped, classified error; re-wrapping double-classifies.
	}
	for i := range page.Agents {
		page.Agents[i] = s.restoreBare(page.Agents[i])
	}
	return page, nil
}

// toNamespaced rewrites a bare process-local id (agent-<n>) to the project-namespaced store id
// (agent-<project>-<n>) via the production minter. An id that is ALREADY namespaced (a record
// reloaded after a restart, or one this decorator did not mint) is returned unchanged — the
// rewrite is applied at most once, so it is idempotent on a re-Put of an already-stored record.
func (s *namespacingStore) toNamespaced(id orchestrator.AgentID, tenant orchestrator.Tenancy) orchestrator.AgentID {
	if tenant.ProjectID == "" {
		return id // cannot namespace without a project; the store will reject it (the contract's guard)
	}
	if strings.HasPrefix(string(id), idPrefix+tenant.ProjectID+"-") {
		return id // already namespaced (reloaded record / re-Put) — leave it
	}
	sequence, ok := bareSequence(id)
	if !ok {
		return id // not the bare agent-<n> form; pass it through for the store to validate
	}
	return postgresstore.MintAgentID(tenant, sequence)
}

// lookupNamespaced resolves a bare id to its namespaced store id via the Put-populated index;
// an id absent from the index (already namespaced, or never Put through this process) is used
// as-given so the store applies its own NotFoundError contract.
func (s *namespacingStore) lookupNamespaced(id orchestrator.AgentID) orchestrator.AgentID {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if namespaced, ok := s.namespaced[id]; ok {
		return namespaced
	}
	return id
}

// restoreBare rewrites a record's namespaced store id back to the bare id the Pool expects,
// consulting the reverse of the Put-populated index. A record whose namespaced id maps to no
// known bare id (a record authored by another process / reloaded after restart) keeps its id as
// stored — the Pool then operates on that id directly (its side tables are repopulated lazily).
//
//nolint:gocritic // Agent is the contract's copyable serializable record; restoreBare rewrites its own copy by value.
func (s *namespacingStore) restoreBare(agent orchestrator.Agent) orchestrator.Agent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for bare, namespaced := range s.namespaced {
		if namespaced == agent.ID {
			if agent.Session == orchestrator.SessionRef(namespaced) {
				agent.Session = orchestrator.SessionRef(bare)
			}
			agent.ID = bare
			return agent
		}
	}
	return agent
}

// idPrefix is the stable agent-id namespace token (mirrors orchestrator's minter and the store's
// idPrefix). It lives here as the decorator's local copy of the boundary token it parses; the
// production minter is the authority for the FORM (MintAgentID), this only recognizes the prefix.
const idPrefix = "agent-"

// bareSequence parses the monotonic sequence out of a bare process-local id (agent-<n>),
// reporting whether id is exactly that form. A namespaced or malformed id yields ok=false.
func bareSequence(id orchestrator.AgentID) (uint64, bool) {
	rest, ok := strings.CutPrefix(string(id), idPrefix)
	if !ok || rest == "" || strings.Contains(rest, "-") {
		return 0, false // namespaced (agent-<project>-<n>) or not the bare form
	}
	var sequence uint64
	for _, r := range rest {
		if r < '0' || r > '9' {
			return 0, false
		}
		sequence = sequence*10 + uint64(r-'0')
	}
	return sequence, true
}
