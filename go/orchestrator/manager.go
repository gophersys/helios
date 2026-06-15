package orchestrator

import (
	"context"
	"strconv"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// Spawn records the DESIRED intent to run one agent and returns the assigned Agent at
// StatusPending immediately. It admits BEFORE provisioning: template resolution and the
// (Tenant, Template) MaxConcurrent ceiling are checked, the per-spawn override is
// validated as a tightening (never a widening), and the desired record is written. No
// workspace is requested here — reconcile provisions asynchronously.
//
//nolint:gocritic // contract §2: SpawnRequest is the frozen, copyable spawn input (the configuration pattern); the port takes it by value.
func (p *Pool) Spawn(ctx context.Context, request SpawnRequest) (Agent, error) {
	if err := validateRequestShape(&request); err != nil {
		return Agent{}, wrapKind(err)
	}

	template, err := p.dependencies.Templates.Resolve(ctx, request.Template)
	if err != nil {
		// Resolve returns a wrapped, classified TemplateNotFoundError; surface it as-is when
		// it carries our type (re-wrapping would double-classify), else synthesize ours.
		if errors.IsType[*TemplateNotFoundError](err) {
			return Agent{}, err //nolint:wrapcheck // the TemplateStore already returns a wrapped, classified TemplateNotFoundError; re-wrapping double-classifies.
		}
		return Agent{}, errors.Wrap(errors.KindNotFound, "orchestrator: resolve template",
			&TemplateNotFoundError{Ref: request.Template})
	}

	effective, err := p.effectiveLimits(&template, &request)
	if err != nil {
		return Agent{}, wrapKind(err)
	}

	// Admission is the count-then-record critical section: it must be atomic so two
	// concurrent Spawns racing the same ceiling cannot both pass (the single admission
	// authority). The lock is held across the DesiredStore count + Put.
	p.mu.Lock()
	defer p.mu.Unlock()

	current, err := p.activeCount(ctx, request.Tenant, request.Template.Name)
	if err != nil {
		return Agent{}, err
	}
	maxConcurrent := effective.MaxConcurrent
	if maxConcurrent > 0 && current >= maxConcurrent {
		limit := &LimitError{Tenant: request.Tenant, Template: request.Template, Max: maxConcurrent, Current: current}
		p.emit(ctx, ObservabilityEvent{
			AgentID: "", Tenant: request.Tenant, Kind: ObsLimitRejected,
			Detail: "max concurrent reached: " + strconv.Itoa(current) + " of " + strconv.Itoa(maxConcurrent),
		})
		return Agent{}, wrapKind(limit)
	}

	cluster := request.Cluster
	if cluster.IsZero() {
		cluster = p.configuration.DefaultCluster
	}

	p.idSeq++
	now := p.now()
	agent := Agent{
		ID:        p.newAgentID(),
		Tenant:    request.Tenant,
		Template:  request.Template,
		RunID:     request.RunID,
		Desired:   DesiredRunning,
		Status:    StatusPending,
		Limits:    effective,
		Cluster:   cluster,
		By:        request.By,
		CreatedAt: now,
		UpdatedAt: now,
		Detail:    "spawn admitted",
	}
	// The orchestrator persists the spawn inputs it needs to fold at provision time
	// (the credential ref, the permission decider, the tightening) OUT-OF-BAND of the
	// serializable record, so no secret value and no live closure enters the store. At
	// v0 (single-node) they ride an in-memory side table keyed by AgentID.
	p.rememberSpawnInputs(agent.ID, &request, &template)

	if err := p.dependencies.Desired.Put(ctx, agent); err != nil {
		p.forgetSpawnInputs(agent.ID)
		return Agent{}, errors.Wrap(errors.KindUnavailable, "orchestrator: record desired agent", err)
	}

	p.emit(ctx, ObservabilityEvent{
		AgentID: agent.ID, Tenant: agent.Tenant, Kind: ObsSpawnAdmitted,
		From: StatusPending, To: StatusPending, Detail: "spawn admitted",
	})
	p.notifyWatchers(AgentEvent{AgentID: agent.ID, From: StatusPending, To: StatusPending, At: now, Reason: "spawn admitted"})
	return agent, nil
}

// Get returns the current Agent record or a wrapped NotFoundError.
func (p *Pool) Get(ctx context.Context, id AgentID) (Agent, error) {
	agent, err := p.dependencies.Desired.Get(ctx, id)
	if err != nil {
		if errors.IsType[*NotFoundError](err) {
			return Agent{}, err //nolint:wrapcheck // the DesiredStore already returns a wrapped, classified NotFoundError; re-wrapping double-classifies.
		}
		return Agent{}, errors.Wrap(errors.KindNotFound, "orchestrator: get agent", &NotFoundError{ID: id})
	}
	return agent, nil
}

// List returns the Agents matching filter (a point-in-time snapshot).
//
//nolint:gocritic // contract §2: Filter is the frozen, copyable query value; the port takes it by value.
func (p *Pool) List(ctx context.Context, filter Filter) (Page, error) {
	if filter.Limit <= 0 {
		filter.Limit = defaultPageSize
	}
	page, err := p.dependencies.Desired.List(ctx, filter)
	if err != nil {
		return Page{}, errors.Wrap(errors.KindUnavailable, "orchestrator: list agents", err)
	}
	return page, nil
}

// Stop records the DESIRED terminal intent. Idempotent: stopping an already-terminal or
// already-stopping agent is a no-op success. It returns when the intent is RECORDED, not
// when teardown completes.
func (p *Pool) Stop(ctx context.Context, id AgentID, by string) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	agent, err := p.dependencies.Desired.Get(ctx, id)
	if err != nil {
		if errors.IsType[*NotFoundError](err) {
			return err //nolint:wrapcheck // the DesiredStore already returns a wrapped, classified NotFoundError; re-wrapping double-classifies.
		}
		return errors.Wrap(errors.KindNotFound, "orchestrator: stop agent", &NotFoundError{ID: id})
	}
	if agent.Status.Terminal() || agent.Desired == DesiredStopped {
		return nil // idempotent: already stopping or terminal
	}

	agent.Desired = DesiredStopped
	if by != "" {
		agent.By = by
	}
	agent.UpdatedAt = p.now()
	agent.Detail = "stop requested"
	if err := p.dependencies.Desired.Put(ctx, agent); err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestrator: record stop intent", err)
	}
	return nil
}

// Resume records the DESIRED intent to re-attach a stopped/disconnected agent. It
// validates resumability synchronously (ConflictError on a non-resumable status,
// NotFoundError on an unknown id); the actual re-attach is driven by reconcile, which
// surfaces UnsupportedError when the bound adapter declares CapResume absent.
func (p *Pool) Resume(ctx context.Context, id AgentID, by string) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	agent, err := p.dependencies.Desired.Get(ctx, id)
	if err != nil {
		if errors.IsType[*NotFoundError](err) {
			return err //nolint:wrapcheck // the DesiredStore already returns a wrapped, classified NotFoundError; re-wrapping double-classifies.
		}
		return errors.Wrap(errors.KindNotFound, "orchestrator: resume agent", &NotFoundError{ID: id})
	}
	// A resumable agent is one that is Suspended (a dropped actual) or already Stopped
	// gracefully (reload an old Run) — never one mid-provisioning or Failed.
	if !resumable(agent.Status) {
		return wrapKind(&ConflictError{ID: id, Status: agent.Status})
	}

	from := agent.Status
	agent.Desired = DesiredRunning
	agent.Status = StatusResuming
	if by != "" {
		agent.By = by
	}
	now := p.now()
	agent.UpdatedAt = now
	agent.Detail = "resume requested"
	if err := p.dependencies.Desired.Put(ctx, agent); err != nil {
		return errors.Wrap(errors.KindUnavailable, "orchestrator: record resume intent", err)
	}
	p.notifyWatchers(AgentEvent{AgentID: id, From: from, To: StatusResuming, At: now, Reason: "resume requested"})
	return nil
}

// resumable reports whether an agent in status may be Resumed. Suspended (a dropped
// actual) and Stopped (graceful) are resumable; everything else is a conflict.
func resumable(status Status) bool {
	return status == StatusSuspended || status == StatusStopped
}

// validateRequestShape checks the non-credential shape of a SpawnRequest. A missing
// tenant or template is an InvalidRequestError (KindInvalid). The credential ref is NOT
// validated for content here — it is opaque and resolved server-side.
func validateRequestShape(request *SpawnRequest) error {
	if request.Tenant.IsZero() {
		return &InvalidRequestError{Reason: "Tenant is required (org/project keys)"}
	}
	if request.Template.IsZero() {
		return &InvalidRequestError{Reason: "Template ref is required (Name and Version)"}
	}
	return nil
}

// effectiveLimits folds the template's default Limits with the per-spawn override,
// enforcing that the override only TIGHTENS (never widens) the template ceiling. A
// widening override is an InvalidRequestError (the template is the ceiling).
func (p *Pool) effectiveLimits(template *AgentTemplate, request *SpawnRequest) (Limits, error) {
	effective := template.Limits
	if effective.MaxConcurrent == 0 {
		effective.MaxConcurrent = p.configuration.DefaultMaxConcurrent
	}
	if request.BudgetOverride != nil {
		if widens(template.Limits.Budget, *request.BudgetOverride) {
			return Limits{}, &InvalidRequestError{Reason: "BudgetOverride widens the template ceiling (only tightening is allowed)"}
		}
		effective.Budget = *request.BudgetOverride
	}
	return effective, nil
}

// widens reports whether override loosens any non-zero ceiling of the template budget.
// A template ceiling of 0 means "unbounded here" (agentsession enforces), so any
// override of a zero ceiling is a tightening, not a widening. A non-zero template
// ceiling may only be lowered.
func widens(template, override agentsession.Budget) bool {
	if template.MaxCostMicros != 0 && (override.MaxCostMicros == 0 || override.MaxCostMicros > template.MaxCostMicros) {
		return true
	}
	if template.MaxTurns != 0 && (override.MaxTurns == 0 || override.MaxTurns > template.MaxTurns) {
		return true
	}
	if template.MaxWall != 0 && (override.MaxWall == 0 || override.MaxWall > template.MaxWall) {
		return true
	}
	return false
}

// activeCount returns the number of non-terminal agents for the (tenant, templateName)
// class — the admission counter. Counting by template Name (not Ref) means all versions
// of a template share the class ceiling. The caller holds p.mu.
func (p *Pool) activeCount(ctx context.Context, tenant Tenancy, templateName string) (int, error) {
	page, err := p.dependencies.Desired.List(ctx, Filter{
		Tenant:     tenant,
		Template:   TemplateRef{Name: templateName},
		OnlyActive: true,
		Limit:      0,
	})
	if err != nil {
		return 0, errors.Wrap(errors.KindUnavailable, "orchestrator: count active agents", err)
	}
	return len(page.Agents), nil
}

// newAgentID builds the stable AgentID from the monotonic sequence. The caller holds
// p.mu (idSeq is already incremented). The id is loggable and carries no secret.
func (p *Pool) newAgentID() AgentID {
	return AgentID("agent-" + strconv.FormatUint(p.idSeq, 10))
}
