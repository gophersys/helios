// Package orchestratortest provides the canonical in-memory fakes + the conformance
// suite + the integration harness for the orchestrator port (the testing pattern,
// 10 §4 / 08 §2), so consumers (S1 control plane, S4 engine, the chat backend) test the
// spawn-up reconcile loop — admission limits, the desired/actual split, Stop reaping,
// Resume re-attach, the budget watch, and the credential seam — WITHOUT a real cluster or
// a real claude/omp process, and so any future Pool/Probe adapter proves substitutability
// against the same properties.
//
// The fakes are DETERMINISTIC (an injected manual clock, no goroutines unless asked) so a
// test drives reconcile by hand and asserts exact transitions. The workspace fake REUSES
// workspaceprovidertest (one home for the workspace fake, Q8) and the session fake REUSES
// agentsessiontest's scripted Adapter wired into a real agentsession.Pool, so the suite
// exercises the REAL reconcile logic against the REAL frozen seams, not a re-implementation.
package orchestratortest

import (
	"context"
	"strings"
	"sync"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// ─────────────────────────────────────────────────────────────────────────────.
// DesiredStore — an in-memory orchestrator.DesiredStore (the v0 binding, reusable as a
// test double). Deterministic; safe for concurrent use.
// ─────────────────────────────────────────────────────────────────────────────.

// DesiredStore is an in-memory orchestrator.DesiredStore.
type DesiredStore struct {
	mu    sync.Mutex
	byID  map[orchestrator.AgentID]orchestrator.Agent
	order []orchestrator.AgentID // insertion order, for deterministic List
	// history retains EVERY record version ever Put (not just the latest), so the
	// credential-seam guard can scan transient fields (Detail/By) a later transition
	// overwrites — a leak into a record that is subsequently replaced would otherwise
	// escape a guard that reads only the final List().
	history []orchestrator.Agent
}

// NewDesiredStore constructs an empty in-memory DesiredStore.
func NewDesiredStore() *DesiredStore {
	return &DesiredStore{byID: make(map[orchestrator.AgentID]orchestrator.Agent)}
}

// Put records or replaces an Agent record.
//
//nolint:gocritic // Agent is the contract's copyable serializable record; the store keeps its own copy by value.
func (s *DesiredStore) Put(_ context.Context, agent orchestrator.Agent) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.byID[agent.ID]; !exists {
		s.order = append(s.order, agent.ID)
	}
	s.byID[agent.ID] = agent
	s.history = append(s.history, agent) // retain every version for the no-leak history scan
	return nil
}

// AllVersions returns a copy of EVERY Agent record version ever Put (the full transition
// history, including transient records a later Put replaced). The credential-seam guard
// scans this so a leak into a field that is subsequently overwritten cannot escape.
func (s *DesiredStore) AllVersions() []orchestrator.Agent {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]orchestrator.Agent, len(s.history))
	copy(out, s.history)
	return out
}

// Get returns one Agent record or a wrapped NotFoundError.
func (s *DesiredStore) Get(_ context.Context, id orchestrator.AgentID) (orchestrator.Agent, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	agent, ok := s.byID[id]
	if !ok {
		return orchestrator.Agent{}, errors.Wrap(errors.KindNotFound, "orchestratortest: get agent",
			&orchestrator.NotFoundError{ID: id})
	}
	return agent, nil
}

// List returns records matching filter in deterministic (insertion) order. Cursor
// pagination is a simple offset over the filtered set.
//
//nolint:gocritic // contract §3: DesiredStore.List takes the Filter by value (the frozen port surface).
func (s *DesiredStore) List(_ context.Context, filter orchestrator.Filter) (orchestrator.Page, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	matched := make([]orchestrator.Agent, 0, len(s.order))
	for _, id := range s.order {
		agent := s.byID[id]
		if matchesFilter(&filter, &agent) {
			matched = append(matched, agent)
		}
	}
	return paginate(matched, &filter)
}

// matchesFilter reports whether an agent passes a Filter (tenant, template, status,
// active, labels).
func matchesFilter(filter *orchestrator.Filter, agent *orchestrator.Agent) bool {
	if !filter.Tenant.IsZero() && agent.Tenant != filter.Tenant {
		return false
	}
	if filter.Template.Name != "" && agent.Template.Name != filter.Template.Name {
		return false
	}
	if filter.Template.Version != "" && agent.Template.Version != filter.Template.Version {
		return false
	}
	if filter.OnlyActive && agent.Status.Terminal() {
		return false
	}
	if len(filter.Statuses) > 0 && !containsStatus(filter.Statuses, agent.Status) {
		return false
	}
	return true
}

// containsStatus reports whether statuses contains want.
func containsStatus(statuses []orchestrator.Status, want orchestrator.Status) bool {
	for _, s := range statuses {
		if s == want {
			return true
		}
	}
	return false
}

// paginate slices the matched set by the filter's Cursor/Limit and returns the page plus
// the next cursor.
func paginate(matched []orchestrator.Agent, filter *orchestrator.Filter) (orchestrator.Page, error) {
	start := 0
	if filter.Cursor != "" {
		for i := range matched {
			if string(matched[i].ID) == filter.Cursor {
				start = i + 1
				break
			}
		}
	}
	limit := filter.Limit
	if limit <= 0 || start+limit > len(matched) {
		limit = len(matched) - start
	}
	if start > len(matched) {
		start = len(matched)
	}
	page := orchestrator.Page{Agents: append([]orchestrator.Agent(nil), matched[start:start+limit]...)}
	if start+limit < len(matched) && limit > 0 {
		page.Next = string(matched[start+limit-1].ID)
	}
	return page, nil
}

// compile-time assertion: *DesiredStore is an orchestrator.DesiredStore.
var _ orchestrator.DesiredStore = (*DesiredStore)(nil)

// ─────────────────────────────────────────────────────────────────────────────.
// TemplateStore — an in-memory orchestrator.TemplateStore seeded from a map.
// ─────────────────────────────────────────────────────────────────────────────.

// TemplateStore is an in-memory orchestrator.TemplateStore.
type TemplateStore struct {
	mu    sync.Mutex
	byKey map[string]orchestrator.AgentTemplate
}

// NewTemplateStore constructs a TemplateStore seeded with the given templates (keyed by
// their Ref).
func NewTemplateStore(seed ...orchestrator.AgentTemplate) *TemplateStore {
	templateStore := &TemplateStore{byKey: make(map[string]orchestrator.AgentTemplate)}
	for i := range seed {
		templateStore.byKey[refKey(seed[i].Ref)] = seed[i]
	}
	return templateStore
}

// Add seeds (or overrides) one template. Fluent.
//
//nolint:gocritic // AgentTemplate is the contract's data record; the store keeps its own copy by value.
func (s *TemplateStore) Add(template orchestrator.AgentTemplate) *TemplateStore {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.byKey[refKey(template.Ref)] = template
	return s
}

// Resolve returns the immutable template for ref, or a wrapped TemplateNotFoundError.
func (s *TemplateStore) Resolve(_ context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	template, ok := s.byKey[refKey(ref)]
	if !ok {
		return orchestrator.AgentTemplate{}, errors.Wrap(errors.KindNotFound, "orchestratortest: resolve template",
			&orchestrator.TemplateNotFoundError{Ref: ref})
	}
	return template, nil
}

// refKey is the map key for a TemplateRef (name@version).
func refKey(ref orchestrator.TemplateRef) string { return ref.Name + "@" + ref.Version }

// compile-time assertion: *TemplateStore is an orchestrator.TemplateStore.
var _ orchestrator.TemplateStore = (*TemplateStore)(nil)

// ─────────────────────────────────────────────────────────────────────────────.
// Probe — a scriptable orchestrator.Probe: a test sets the observed Actual per agent.
// ─────────────────────────────────────────────────────────────────────────────.

// Probe is a scriptable orchestrator.Probe. A test sets the observed Actual per agent so
// reconcile's diff is exercised against a controlled "world" (workspace died? session
// went away? ledger crossed budget?). Safe for concurrent use.
type Probe struct {
	mu     sync.Mutex
	byID   map[orchestrator.AgentID]orchestrator.Actual
	def    orchestrator.Actual
	hasDef bool
}

// NewProbe constructs an empty Probe (every unset id reports the zero Actual unless a
// default is set).
func NewProbe() *Probe {
	return &Probe{byID: make(map[orchestrator.AgentID]orchestrator.Actual)}
}

// Set pins the observed Actual for one agent. Fluent.
//
//nolint:gocritic // Actual is the contract's copyable value record; the probe keeps its own copy by value.
func (p *Probe) Set(id orchestrator.AgentID, actual orchestrator.Actual) *Probe {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.byID[id] = actual
	return p
}

// SetDefault pins the observed Actual for every id not explicitly Set (the "all agents
// live" shortcut). Fluent.
//
//nolint:gocritic // Actual is the contract's copyable value record; the probe keeps its own copy by value.
func (p *Probe) SetDefault(actual orchestrator.Actual) *Probe {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.def = actual
	p.hasDef = true
	return p
}

// Observe returns the scripted Actual for each requested id.
func (p *Probe) Observe(_ context.Context, ids []orchestrator.AgentID) (map[orchestrator.AgentID]orchestrator.Actual, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	out := make(map[orchestrator.AgentID]orchestrator.Actual, len(ids))
	for _, id := range ids {
		if actual, ok := p.byID[id]; ok {
			out[id] = actual
			continue
		}
		if p.hasDef {
			out[id] = p.def
		}
	}
	return out, nil
}

// compile-time assertion: *Probe is an orchestrator.Probe.
var _ orchestrator.Probe = (*Probe)(nil)

// ─────────────────────────────────────────────────────────────────────────────.
// Telemetry — captures emitted ObservabilityEvents for transition/limit/ledger asserts.
// ─────────────────────────────────────────────────────────────────────────────.

// Telemetry captures emitted ObservabilityEvents. Safe for concurrent use; read Events
// via Snapshot (a race-safe copy) after quiescing the loop.
type Telemetry struct {
	mu     sync.Mutex
	events []orchestrator.ObservabilityEvent
}

// Emit records one event.
//
//nolint:gocritic // ObservabilityEvent is a small copyable value envelope; the recorder keeps its own copy by value.
func (t *Telemetry) Emit(_ context.Context, event orchestrator.ObservabilityEvent) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.events = append(t.events, event)
}

// Snapshot returns a race-safe copy of the recorded events.
func (t *Telemetry) Snapshot() []orchestrator.ObservabilityEvent {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := make([]orchestrator.ObservabilityEvent, len(t.events))
	copy(out, t.events)
	return out
}

// CountKind returns how many recorded events carry kind.
func (t *Telemetry) CountKind(kind orchestrator.ObservabilityKind) int {
	t.mu.Lock()
	defer t.mu.Unlock()
	n := 0
	for i := range t.events {
		if t.events[i].Kind == kind {
			n++
		}
	}
	return n
}

// containsCanary reports whether any recorded event's loggable form contains canary (the
// credential-seam guard).
func (t *Telemetry) containsCanary(canary string) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	for i := range t.events {
		if strings.Contains(t.events[i].Detail, canary) {
			return true
		}
	}
	return false
}

// compile-time assertion: *Telemetry is an orchestrator.Telemetry.
var _ orchestrator.Telemetry = (*Telemetry)(nil)

// ─────────────────────────────────────────────────────────────────────────────.
// Clock — a manual clock (mirrors observability/agentsession test clocks).
// ─────────────────────────────────────────────────────────────────────────────.

// Clock is a deterministic manual clock. Advance steps it; Now reads it. Safe for
// concurrent use.
type Clock struct {
	mu  sync.Mutex
	now time.Time
}

// NewClock constructs a manual clock at a fixed deterministic instant.
func NewClock() *Clock {
	return &Clock{now: time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)}
}

// Now reads the clock.
func (c *Clock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

// Advance steps the clock by d. Fluent.
func (c *Clock) Advance(d time.Duration) *Clock {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
	return c
}

// compile-time assertion: *Clock is an orchestrator.Clock.
var _ orchestrator.Clock = (*Clock)(nil)

// recordContainsCanary reports whether an Agent record's loggable form contains canary —
// the credential-seam guard. It flattens every string-bearing field a serialized record
// would carry (ids, refs, detail, handle, labels-free record). The credential Reference
// is never on the record by construction; this proves it.
func recordContainsCanary(agent *orchestrator.Agent, canary string) bool {
	var b strings.Builder
	b.WriteString(string(agent.ID))
	b.WriteString(string(agent.Session))
	b.WriteString(string(agent.Template.Name))
	b.WriteString(string(agent.Template.Version))
	b.WriteString(agent.RunID)
	b.WriteString(agent.By)
	b.WriteString(agent.Detail)
	b.WriteString(agent.Tenant.OrganizationID)
	b.WriteString(agent.Tenant.ProjectID)
	b.WriteString(agent.Cluster.ID)
	b.WriteString(agent.Workspace.String())
	b.WriteString(agent.Ledger.Model)
	b.WriteString(agent.Ledger.Harness)
	return strings.Contains(b.String(), canary)
}
