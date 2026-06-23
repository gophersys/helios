package orchestrator

import (
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
)

// spawnInputs is the per-agent fold material reconcile needs but that must NOT enter the
// serializable Agent record: the opaque credential Reference (threaded into
// agentsession.Spec.Credential, never resolved or stored on the record), the permission
// decider closure (a live func, un-serializable), the resolved template, and the
// per-spawn tightening. At v0 (single-node) this rides an in-process side table keyed by
// AgentID. At multi-node the credential Reference and the tightening re-derive from the
// (durable) SpawnRequest the control plane persisted alongside the record; the closure
// is re-bound by the node holding the session. The seam is the same: the record stays a
// plain serializable value holding NO secret and NO handle.
type spawnInputs struct {
	credential   secrets.Reference // OPAQUE; flows into agentsession.Spec.Credential; never the value
	onPermission func(agentsession.PermissionRequest) agentsession.Decision
	template     AgentTemplate
	systemHints  string
	budget       agentsession.Budget
	workspace    string                  // OPTIONAL host-CWD override (SpawnRequest.Workspace); "" == the provisioned WorkDir
	hostTools    []agentsession.HostTool // OPTIONAL per-spawn host-tools (SpawnRequest.HostTools); nil == the template's Hosts
}

// effectiveHostTools returns the per-spawn host-tools when supplied (the composition-root closures),
// else the template's declared Hosts.
func (in *spawnInputs) effectiveHostTools() []agentsession.HostTool {
	if len(in.hostTools) > 0 {
		return in.hostTools
	}
	return in.template.Hosts
}

// effectiveWorkDir returns the per-spawn host-workspace OVERRIDE when set (an externally
// materialized harness CWD), else the provisioned workspace's WorkDir, else the default.
func (in *spawnInputs) effectiveWorkDir(provisioned string) string {
	if in.workspace != "" {
		return in.workspace
	}
	if provisioned != "" {
		return provisioned
	}
	return defaultWorkDir
}

// spawnInputsTable is the AgentID-keyed side table. Safe for concurrent use.
type spawnInputsTable struct {
	mu     sync.Mutex
	byID   map[AgentID]spawnInputs
	credit map[AgentID]secrets.Reference // retained credential ref so Resume re-opens without a fresh SpawnRequest
}

// newSpawnInputsTable constructs an empty side table.
func newSpawnInputsTable() *spawnInputsTable {
	return &spawnInputsTable{
		byID:   make(map[AgentID]spawnInputs),
		credit: make(map[AgentID]secrets.Reference),
	}
}

// put records the fold material for an agent.
//
//nolint:gocritic // spawnInputs holds a closure + a value template; storing it by value is the intent (the table owns its copy).
func (t *spawnInputsTable) put(id AgentID, inputs spawnInputs) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.byID[id] = inputs
	t.credit[id] = inputs.credential
}

// get returns the fold material for an agent and whether it is present.
func (t *spawnInputsTable) get(id AgentID) (spawnInputs, bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	inputs, ok := t.byID[id]
	if !ok {
		// A Resume after a record-only reload re-binds from the retained credential ref;
		// the closure defaults to nil (the chat human path) until the consumer re-attaches.
		if ref, has := t.credit[id]; has {
			return spawnInputs{credential: ref}, true
		}
	}
	return inputs, ok
}

// forget drops an agent's fold material (called on terminal reap or a failed admission).
func (t *spawnInputsTable) forget(id AgentID) {
	t.mu.Lock()
	defer t.mu.Unlock()
	delete(t.byID, id)
	delete(t.credit, id)
}

// rememberSpawnInputs stashes the fold material for a freshly-admitted agent. The Pool
// lazily constructs the side table so New stays a pure value constructor.
func (p *Pool) rememberSpawnInputs(id AgentID, request *SpawnRequest, template *AgentTemplate) {
	p.ensureInputs().put(id, spawnInputs{
		credential:   request.Credential,
		onPermission: request.OnPermission,
		template:     *template,
		systemHints:  template.SystemHints + request.SystemHints,
		budget:       effectiveBudget(template.Limits, request),
		workspace:    request.Workspace,
		hostTools:    request.HostTools,
	})
}

// forgetSpawnInputs drops the fold material for an agent.
func (p *Pool) forgetSpawnInputs(id AgentID) {
	if p.inputs != nil {
		p.inputs.forget(id)
	}
}

// lookupSpawnInputs returns the fold material for an agent and whether it is present.
func (p *Pool) lookupSpawnInputs(id AgentID) (spawnInputs, bool) {
	if p.inputs == nil {
		return spawnInputs{}, false
	}
	return p.inputs.get(id)
}

// ensureInputs lazily constructs the side table under the inputsOnce guard.
func (p *Pool) ensureInputs() *spawnInputsTable {
	p.inputsOnce.Do(func() { p.inputs = newSpawnInputsTable() })
	return p.inputs
}

// effectiveBudget folds the template's default budget with the per-spawn tightening
// override (validated as a tightening at admission, so this is a plain substitution).
func effectiveBudget(limits Limits, request *SpawnRequest) agentsession.Budget {
	if request.BudgetOverride != nil {
		return *request.BudgetOverride
	}
	return limits.Budget
}
