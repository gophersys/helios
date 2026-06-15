package orchestrator

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// Reconcile performs ONE bounded, idempotent, convergent pass: read DESIRED records,
// OBSERVE actuals via the Probe, and drive each agent at most one step toward its desired
// Status. A single agent's failure is recorded on that agent and never fails the pass.
//
//nolint:gocritic // contract §3: ReconcilePorts is the frozen per-pass port bundle; passing it by value scopes a pass without aliasing the Pool's defaults.
func (p *Pool) Reconcile(ctx context.Context, ports ReconcilePorts) (ReconcileReport, error) {
	ports = p.reconcilePorts(ports)

	page, err := p.dependencies.Desired.List(ctx, Filter{Limit: 0})
	if err != nil {
		return ReconcileReport{}, errors.Wrap(errors.KindUnavailable, "orchestrator: reconcile list desired", err)
	}

	ids := make([]AgentID, 0, len(page.Agents))
	for i := range page.Agents {
		ids = append(ids, page.Agents[i].ID)
	}
	observed := map[AgentID]Actual{}
	if ports.Probe != nil && len(ids) > 0 {
		observed, err = ports.Probe.Observe(ctx, ids)
		if err != nil {
			return ReconcileReport{}, errors.Wrap(errors.KindUnavailable, "orchestrator: reconcile observe actual", err)
		}
	}

	report := ReconcileReport{Observed: len(page.Agents)}
	for i := range page.Agents {
		agent := page.Agents[i]
		actual := observed[agent.ID]
		event, changed, failed := p.step(ctx, ports, agent, actual)
		if !changed {
			continue
		}
		report.Transitioned++
		if failed {
			report.Failed++
		}
		report.Outcomes = append(report.Outcomes, event)
	}
	return report, nil
}

// step drives ONE agent at most one transition toward its desired Status, given the
// observed actual. It returns the transition event (zero if no change), whether a change
// occurred, and whether that change was a failure. Each transition persists the new
// record, emits the observability event, and notifies watchers — all under p.mu so a
// concurrent Manager verb sees a consistent record.
//
//nolint:gocritic // Agent/Actual are the contract's copyable value records; step takes its own copies to mutate then persist (no aliasing of the store).
func (p *Pool) step(ctx context.Context, ports ReconcilePorts, agent Agent, actual Actual) (AgentEvent, bool, bool) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Re-read under the lock so a Stop/Resume that landed since the snapshot wins (the
	// desired record is the single source of intent).
	fresh, err := p.dependencies.Desired.Get(ctx, agent.ID)
	if err == nil {
		agent = fresh
	}

	switch {
	case agent.Desired == DesiredStopped && !agent.Status.Terminal():
		return p.driveStopping(ctx, ports, &agent)
	case agent.Status == StatusPending:
		return p.driveProvision(ctx, ports, &agent)
	case agent.Status == StatusProvisioning:
		return p.driveOpen(ctx, ports, &agent, &actual)
	case agent.Status == StatusResuming:
		return p.driveResume(ctx, ports, &agent)
	case agent.Status == StatusRunning:
		return p.driveRunning(ctx, ports, &agent, &actual)
	case agent.Status == StatusSuspended:
		// Desired is still running but actual dropped; reconcile re-attaches by moving to
		// Resuming (the same path Resume records explicitly).
		return p.driveReattachFromSuspended(ctx, &agent, actual)
	default:
		return AgentEvent{}, false, false
	}
}

// driveProvision provisions the workspace for a Pending agent and moves it to
// Provisioning. Provision is all-or-nothing and idempotent on Name, so a retried pass
// re-adopts. A provisioning fault marks the agent Failed (and tears down any partial
// workspace — Provision's all-or-nothing contract leaves nothing, but reconcile defends
// regardless).
func (p *Pool) driveProvision(ctx context.Context, ports ReconcilePorts, agent *Agent) (AgentEvent, bool, bool) {
	inputs, ok := p.lookupSpawnInputs(agent.ID)
	if !ok {
		return p.fail(ctx, agent, "spawn inputs missing (cannot fold template)")
	}
	if ports.Workspaces == nil {
		return p.fail(ctx, agent, "no workspace provider bound for provisioning")
	}

	spec := toWorkspaceSpec(agent, &inputs.template)
	workspace, err := ports.Workspaces.Provision(ctx, spec)
	if err != nil {
		// Defend against a partial workspace even though Provision is all-or-nothing.
		return p.failProvision(ctx, ports, agent, err)
	}
	p.ensureLive().putWorkspace(agent.ID, workspace)

	from := agent.Status
	agent.Status = StatusProvisioning
	agent.Workspace = workspace.Handle()
	agent.Detail = "workspace provisioned"
	return p.commit(ctx, agent, from, "workspace provisioned", ObsTransition, false)
}

// driveOpen opens the agentsession in the provisioned workspace and moves the agent to
// Running. A spawn/auth fault marks the agent Failed AND tears down the workspace (the
// session never owns the pod). The SessionRef becomes the stable join key a consumer
// tails off.
func (p *Pool) driveOpen(ctx context.Context, ports ReconcilePorts, agent *Agent, actual *Actual) (AgentEvent, bool, bool) {
	inputs, ok := p.lookupSpawnInputs(agent.ID)
	if !ok {
		return p.failAndTeardown(ctx, ports, agent, "spawn inputs missing (cannot open session)")
	}
	if ports.Sessions == nil {
		return p.failAndTeardown(ctx, ports, agent, "no session factory bound for opening")
	}

	workDir := agent.Workspace.WorkDir()
	if workDir == "" {
		workDir = defaultWorkDir
	}
	spec := foldSession(workDir, &inputs, "")
	session, err := ports.Sessions.Open(ctx, spec)
	if err != nil {
		return p.failAndTeardown(ctx, ports, agent, "session open failed: "+redactCause(err))
	}

	// The orchestration RECORD never holds the live Session — it stores the opaque
	// SessionRef the consumer resolves through agentsession to tail Events (rationale
	// 2/7). AgentID == the agentsession SessionID by contract, so the ref is the AgentID.
	// The live Session goes to the in-process side table so reconcile can Close it (the
	// harness reap) before Teardown (the pod reap) on Stop.
	p.ensureLive().putSession(agent.ID, session)
	from := agent.Status
	agent.Status = StatusRunning
	agent.Session = SessionRef(agent.ID)
	agent.Ledger = actual.Ledger
	agent.Detail = "session open; agent loop live"
	return p.commit(ctx, agent, from, "session opened", ObsTransition, false)
}

// driveRunning watches a live agent: fold the observed ledger onto the orchestration
// stream, enforce the per-session budget (the authoritative stop even when no consumer
// tails), and detect a dropped actual (→ Suspended). It performs at most one transition
// per pass.
func (p *Pool) driveRunning(ctx context.Context, ports ReconcilePorts, agent *Agent, actual *Actual) (AgentEvent, bool, bool) {
	// Budget authority: a crossed ledger forces a Stop (records DesiredStopped + a budget
	// reason). The harness-native cap is folded into Spec.Budget; this is the watchdog so
	// a runaway agent is stopped even when no consumer tails (agentsession.md Q6).
	if budgetExceeded(agent.Limits.Budget, actual.Ledger) {
		agent.Desired = DesiredStopped
		agent.Ledger = actual.Ledger
		agent.Detail = "budget exceeded"
		p.emit(ctx, ObservabilityEvent{
			AgentID: agent.ID, Tenant: agent.Tenant, Kind: ObsBudgetExceeded,
			From: StatusRunning, To: StatusStopping, Ledger: actual.Ledger, Detail: "budget exceeded",
		})
		return p.driveStopping(ctx, ports, agent)
	}

	// A dropped actual (workspace gone or session dead) while desired is still running →
	// Suspended (re-attachable when CapResume present).
	if !actual.WorkspaceLive || !actual.SessionLive {
		from := agent.Status
		agent.Status = StatusSuspended
		agent.Detail = "actual dropped; re-attachable"
		return p.commit(ctx, agent, from, "actual dropped", ObsTransition, false)
	}

	// Live and within budget: fold the ledger tick if it advanced, but do NOT count it as
	// a transition (idempotent: actual == desired).
	if ledgerAdvanced(agent.Ledger, actual.Ledger) {
		agent.Ledger = actual.Ledger
		agent.Detail = "ledger tick"
		if err := p.dependencies.Desired.Put(ctx, *agent); err == nil {
			p.emit(ctx, ObservabilityEvent{
				AgentID: agent.ID, Tenant: agent.Tenant, Kind: ObsLedgerTick,
				From: StatusRunning, To: StatusRunning, Ledger: actual.Ledger, Detail: "ledger tick",
			})
		}
	}
	return AgentEvent{}, false, false
}

// driveReattachFromSuspended moves a Suspended agent whose desired is still running into
// Resuming (the reconcile-initiated re-attach path).
//
//nolint:gocritic // Actual is the contract's copyable value record; unused here but part of the uniform step signature.
func (p *Pool) driveReattachFromSuspended(ctx context.Context, agent *Agent, _ Actual) (AgentEvent, bool, bool) {
	if agent.Desired != DesiredRunning {
		return AgentEvent{}, false, false
	}
	from := agent.Status
	agent.Status = StatusResuming
	agent.Detail = "re-attaching dropped session"
	return p.commit(ctx, agent, from, "re-attaching", ObsTransition, false)
}

// driveResume re-attaches an existing harness-native session (Spec.ResumeFrom) for a
// Resuming agent and moves it back to Running. UnsupportedError surfaces (marking Failed)
// when the adapter declares CapResume absent — modeled here as an Open failure carrying
// the resume handle.
func (p *Pool) driveResume(ctx context.Context, ports ReconcilePorts, agent *Agent) (AgentEvent, bool, bool) {
	inputs, ok := p.lookupSpawnInputs(agent.ID)
	if !ok {
		return p.failAndTeardown(ctx, ports, agent, "spawn inputs missing (cannot resume session)")
	}
	if ports.Sessions == nil {
		return p.failAndTeardown(ctx, ports, agent, "no session factory bound for resume")
	}

	// A workspace that survived the drop is re-dialed via Open; one that is GONE (a node
	// recycle reclaimed the pod) is RE-PROVISIONED, so a re-adopt across a real recycle
	// restores a live sandbox before the session re-attaches. Provision is idempotent on Name
	// within a tenancy, so a still-live workspace re-adopts rather than duplicates.
	workDir := agent.Workspace.WorkDir()
	if workDir == "" {
		workDir = defaultWorkDir
	}
	reattached := false
	if !agent.Workspace.IsZero() && ports.Workspaces != nil {
		if ws, err := ports.Workspaces.Open(ctx, agent.Workspace); err == nil {
			workDir = ws.Handle().WorkDir()
			reattached = true
		}
	}
	if !reattached && ports.Workspaces != nil {
		// The pod is gone (Open failed): re-provision from the same folded spec (idempotent on
		// Name) so a re-adopt across a real recycle restores a live workspace. A ConflictError
		// means the workspace actually still EXISTS (a transient Open miss against a pod still
		// settling) — re-dial it rather than fail; the spec is unchanged, so this is the same
		// workspace re-adopted, never a duplicate. Any other provisioning fault marks Failed.
		spec := toWorkspaceSpec(agent, &inputs.template)
		workspace, err := ports.Workspaces.Provision(ctx, spec)
		switch {
		case err == nil:
			p.ensureLive().putWorkspace(agent.ID, workspace)
			agent.Workspace = workspace.Handle()
			workDir = workspace.Handle().WorkDir()
		case errors.IsType[*ConflictError](err) || errors.KindOf(err) == errors.KindConflict:
			// The workspace exists and is settling — keep the recorded handle and re-open the
			// session over it (a retried pass converges once the pod is Ready).
			if ws, oerr := ports.Workspaces.Open(ctx, agent.Workspace); oerr == nil {
				workDir = ws.Handle().WorkDir()
			}
		default:
			return p.failProvision(ctx, ports, agent, err)
		}
	}

	spec := foldSession(workDir, &inputs, agent.Session)
	session, err := ports.Sessions.Open(ctx, spec)
	if err != nil {
		return p.failAndTeardown(ctx, ports, agent, "resume open failed: "+redactCause(err))
	}

	p.ensureLive().putSession(agent.ID, session) // record the re-attached live Session
	from := agent.Status
	agent.Status = StatusRunning
	agent.Session = SessionRef(agent.ID)
	agent.Detail = "session re-attached"
	return p.commit(ctx, agent, from, "session re-attached", ObsTransition, false)
}

// driveStopping drains the session (Close reaps the harness, never the pod) and RELEASES
// the workspace (Teardown is the sole pod-reaper), then moves the agent to Stopped.
// Close-then-Teardown is the drain-then-reap order. Both are idempotent, so a retried
// pass converges.
func (p *Pool) driveStopping(ctx context.Context, ports ReconcilePorts, agent *Agent) (AgentEvent, bool, bool) {
	from := agent.Status
	detail := "stopped gracefully"
	if budgetExceeded(agent.Limits.Budget, agent.Ledger) {
		detail = "stopped: budget exceeded"
	}

	// Drain-then-reap. FIRST agentsession.Close reaps the harness (it does NOT tear down
	// the pod — agentsession §2); THEN Teardown RELEASES the workspace, the SOLE pod-reaper
	// (02 §1). The orchestration record holds only the SessionRef (rationale 2/7); the live
	// Session rides the in-process side table, which is what reconcile Closes here.
	if live, ok := p.ensureLive().get(agent.ID); ok && live.session != nil {
		_ = live.session.Close(ctx) //nolint:errcheck // best-effort harness drain; the pod reap below is the authoritative teardown.
	}
	if !agent.Workspace.IsZero() && ports.Workspaces != nil {
		// Teardown is idempotent (absent == nil), so a retried pass converges; a transient
		// fault keeps the agent non-terminal so a later pass retries — never a leak.
		if err := ports.Workspaces.Teardown(ctx, agent.Workspace); err != nil {
			return AgentEvent{}, false, false
		}
	}
	p.ensureLive().drop(agent.ID)

	agent.Status = StatusStopped
	agent.Detail = detail
	return p.commit(ctx, agent, from, detail, ObsTransition, false)
}

// failProvision marks an agent Failed after a provisioning fault, tearing down any
// partial workspace and recording the redacted cause. The cause's Kind is preserved so a
// caller can branch (Exhausted/Unavailable are often retryable; reconcile records Failed
// once ProvisionTimeout is exhausted — the timeout is enforced by the ctx the loop
// passes).
func (p *Pool) failProvision(ctx context.Context, ports ReconcilePorts, agent *Agent, cause error) (AgentEvent, bool, bool) {
	if !agent.Workspace.IsZero() && ports.Workspaces != nil {
		_ = ports.Workspaces.Teardown(ctx, agent.Workspace) //nolint:errcheck // best-effort partial-workspace reap; Teardown is idempotent.
	}
	provErr := &ProvisionError{Tenant: agent.Tenant, Cluster: agent.Cluster, Message: redactCause(cause)}
	return p.fail(ctx, agent, provErr.Error())
}

// failAndTeardown marks an agent Failed and releases its workspace (so a session-open
// fault never leaks the pod).
func (p *Pool) failAndTeardown(ctx context.Context, ports ReconcilePorts, agent *Agent, detail string) (AgentEvent, bool, bool) {
	if !agent.Workspace.IsZero() && ports.Workspaces != nil {
		_ = ports.Workspaces.Teardown(ctx, agent.Workspace) //nolint:errcheck // best-effort reap on a failed open; Teardown is idempotent.
	}
	return p.fail(ctx, agent, detail)
}

// fail records a terminal Failed transition with a redacted detail and emits the fault.
func (p *Pool) fail(ctx context.Context, agent *Agent, detail string) (AgentEvent, bool, bool) {
	from := agent.Status
	agent.Status = StatusFailed
	agent.Detail = detail
	event, changed, _ := p.commit(ctx, agent, from, detail, ObsReconcileError, true)
	return event, changed, true
}

// commit persists the transitioned record, emits the observability event, notifies
// watchers, and returns the AgentEvent. The caller holds p.mu. failed marks the kind as a
// fault for the report. A store write failure leaves the record at its prior status (the
// next pass retries) and is reported as no-change.
func (p *Pool) commit(ctx context.Context, agent *Agent, from Status, reason string, kind ObservabilityKind, failed bool) (AgentEvent, bool, bool) {
	now := p.now()
	agent.UpdatedAt = now
	if err := p.dependencies.Desired.Put(ctx, *agent); err != nil {
		return AgentEvent{}, false, false
	}
	if agent.Status.Terminal() {
		p.forgetSpawnInputs(agent.ID)
	}
	event := AgentEvent{AgentID: agent.ID, From: from, To: agent.Status, At: now, Reason: reason}
	p.emit(ctx, ObservabilityEvent{
		AgentID: agent.ID, Tenant: agent.Tenant, Kind: kind,
		From: from, To: agent.Status, Ledger: agent.Ledger, Detail: reason,
	})
	p.notifyWatchers(event)
	return event, true, failed
}

// Reap garbage-collects terminal agents older than before: it releases any lingering
// workspace lease and drops the desired record's fold material. Idempotent.
func (p *Pool) Reap(ctx context.Context, before time.Time) (ReapReport, error) {
	page, err := p.dependencies.Desired.List(ctx, Filter{Limit: 0})
	if err != nil {
		return ReapReport{}, errors.Wrap(errors.KindUnavailable, "orchestrator: reap list", err)
	}
	report := ReapReport{}
	for i := range page.Agents {
		agent := page.Agents[i]
		if !agent.Status.Terminal() || !agent.UpdatedAt.Before(before) {
			continue
		}
		p.forgetSpawnInputs(agent.ID)
		report.Reaped++
	}
	return report, nil
}

// budgetExceeded reports whether the observed ledger crossed any non-zero budget ceiling
// (the authoritative stop). A zero ceiling means "unbounded here".
//
//nolint:gocritic // Budget/TokenLedger are the contract's copyable value records; the predicate reads them by value.
func budgetExceeded(budget agentsession.Budget, ledger agentsession.TokenLedger) bool {
	if budget.MaxCostMicros > 0 && ledger.CostMicros >= budget.MaxCostMicros {
		return true
	}
	if budget.MaxTurns > 0 && ledger.Turns >= budget.MaxTurns {
		return true
	}
	if budget.MaxWall > 0 && ledger.WallTime >= budget.MaxWall {
		return true
	}
	return false
}

// ledgerAdvanced reports whether the observed ledger moved past the last-recorded one (so
// a ledger tick is emitted only on real progress, never on a no-op pass).
//
//nolint:gocritic // TokenLedger is the contract's copyable value record; the predicate reads both by value.
func ledgerAdvanced(prev, observed agentsession.TokenLedger) bool {
	return observed.CostMicros > prev.CostMicros ||
		observed.Turns > prev.Turns ||
		observed.InputTokens > prev.InputTokens ||
		observed.OutputTokens > prev.OutputTokens
}

// redactCause renders a fault's classification + message for the Detail field WITHOUT
// leaking a secret. The Eden errors model never embeds a value, so the error string is
// already redaction-safe; this prefixes the stable Kind so the dashboard branches.
func redactCause(err error) string {
	if err == nil {
		return ""
	}
	return errors.KindOf(err).String() + ": " + err.Error()
}
