package orchestrator

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
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
	case agent.Status == StatusStopping:
		// The Stopping waypoint was recorded on a prior step; this pass drains the session and
		// releases the workspace, driving Stopping → Stopped (the reap half of the two-phase stop).
		return p.driveStoppingDrain(ctx, ports, &agent)
	case agent.Desired == DesiredStopped && !agent.Status.Terminal():
		// A Stop (or a budget/Close intent) on a live agent: record the real Stopping waypoint
		// first (Running → Stopping), so the declared lifecycle state is actually entered and
		// telemetry/record agree. The next pass drains it (driveStoppingDrain above).
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

	spec := toWorkspaceSpec(agent, &inputs.template, inputs.effectiveWorkdirRepo())
	provisionCtx, cancel := p.provisionContext(ctx)
	defer cancel()
	workspace, err := ports.Workspaces.Provision(provisionCtx, spec)
	if err != nil {
		// Defend against a partial workspace even though Provision is all-or-nothing. A hung
		// provision trips provisionCtx's deadline (ProvisionTimeout) and surfaces here as a
		// KindDeadline/Canceled fault → the agent is marked Failed rather than wedged forever.
		return p.failProvision(ctx, ports, agent, err)
	}
	p.ensureLive().putWorkspace(agent.ID, workspace)

	from := agent.Status
	agent.Status = StatusProvisioning
	agent.Workspace = workspace.Handle()
	agent.Detail = "workspace provisioned"
	return p.commit(ctx, agent, from, "workspace provisioned", ObsTransition, false)
}

// provisionContext bounds a single Provision call by Config.ProvisionTimeout when it is
// set (>0), so a hung workspaceprovider.Provision trips the deadline and the agent is
// marked Failed rather than wedged in Provisioning forever. A zero ProvisionTimeout means
// "unbounded here" — the parent ctx (the loop's, or the caller's) is the only bound. The
// returned cancel is ALWAYS non-nil and must be called.
func (p *Pool) provisionContext(ctx context.Context) (context.Context, context.CancelFunc) {
	if p.configuration.ProvisionTimeout > 0 {
		return context.WithTimeout(ctx, p.configuration.ProvisionTimeout)
	}
	return ctx, func() {}
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

	workDir := inputs.effectiveWorkDir(agent.Workspace.WorkDir())
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
// tails), branch on the observed inner SessionState (an unrecoverable inner fault → Failed,
// NOT a re-attachable Suspended), and detect a dropped actual (→ Suspended). It performs at
// most one transition per pass.
func (p *Pool) driveRunning(ctx context.Context, ports ReconcilePorts, agent *Agent, actual *Actual) (AgentEvent, bool, bool) {
	// Budget authority: a crossed ledger forces a Stop (records DesiredStopped + a budget
	// reason). The harness-native cap is folded into Spec.Budget; this is the watchdog so
	// a runaway agent is stopped even when no consumer tails (agentsession.md Q6).
	if budgetExceeded(agent.Limits.Budget, actual.Ledger) {
		agent.Desired = DesiredStopped
		agent.Ledger = actual.Ledger
		agent.Detail = "budget exceeded"
		// Emit the budget verdict, then record the real Running → Stopping waypoint (the next
		// pass drains it). The event's To now MATCHES the committed transition (both Stopping),
		// so observability and the record never disagree.
		p.emit(ctx, ObservabilityEvent{
			AgentID: agent.ID, Tenant: agent.Tenant, Kind: ObsBudgetExceeded,
			From: StatusRunning, To: StatusStopping, Ledger: actual.Ledger, Detail: "budget exceeded",
		})
		return p.driveStopping(ctx, ports, agent)
	}

	// Inner-state authority: a session observed in an UNRECOVERABLE terminal inner state
	// (StateFailed / StateAborted — the harness loop hit a transport/auth/abort fault, not a
	// graceful StateCompleted) is NOT re-attachable, so it drives Failed-and-teardown rather
	// than the Suspended (re-attach) path below. This is the production decision that READS
	// the observed Actual.SessionState — without it a crashed inner loop would masquerade as a
	// transient drop and the orchestrator would fruitlessly try to Resume an unrecoverable
	// session. StateCompleted (graceful) is NOT a fault here: it falls through to the
	// dropped-actual check (a completed session whose actual then drops is reaped normally).
	if isUnrecoverableInnerState(actual.SessionState) {
		agent.Ledger = actual.Ledger
		return p.failAndTeardown(ctx, ports, agent, "session entered unrecoverable inner state: "+actual.SessionState.String())
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
	workDir := inputs.effectiveWorkDir(agent.Workspace.WorkDir())
	reattached := false
	if !agent.Workspace.IsZero() && ports.Workspaces != nil {
		if ws, err := ports.Workspaces.Open(ctx, agent.Workspace); err == nil {
			// The host-CWD override (if any) wins over the re-attached container WorkDir — the
			// materialized working tree is external to the pod and survives the re-dial.
			if inputs.workspace == "" {
				workDir = ws.Handle().WorkDir()
			}
			reattached = true
		}
	}
	if !reattached && ports.Workspaces != nil {
		// The pod is gone (Open failed): re-provision from the same folded spec (idempotent on
		// Name) so a re-adopt across a real recycle restores a live workspace. A ConflictError
		// means the workspace actually still EXISTS (a transient Open miss against a pod still
		// settling) — re-dial it rather than fail; the spec is unchanged, so this is the same
		// workspace re-adopted, never a duplicate. Any other provisioning fault marks Failed.
		spec := toWorkspaceSpec(agent, &inputs.template, inputs.effectiveWorkdirRepo())
		provisionCtx, cancel := p.provisionContext(ctx)
		workspace, err := ports.Workspaces.Provision(provisionCtx, spec)
		cancel()
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

// driveStopping records the real Stopping waypoint for a live agent whose desired is
// Stopped: it commits <live-status> → Stopping (the first half of the two-phase stop), so
// the declared lifecycle state is actually entered and a Watcher/telemetry sees the drain
// window open BEFORE the pod is reaped. The drain+release itself runs on the next pass
// (driveStoppingDrain), keeping the contract's at-most-one-transition-per-agent-per-pass.
func (p *Pool) driveStopping(ctx context.Context, _ ReconcilePorts, agent *Agent) (AgentEvent, bool, bool) {
	from := agent.Status
	detail := "stopping: draining session"
	if budgetExceeded(agent.Limits.Budget, agent.Ledger) {
		detail = "stopping: budget exceeded"
	}
	agent.Status = StatusStopping
	agent.Detail = detail
	return p.commit(ctx, agent, from, detail, ObsTransition, false)
}

// driveStoppingDrain drains the session (Close reaps the harness, never the pod) and
// RELEASES the workspace (Teardown is the sole pod-reaper), then moves an agent already at
// Stopping to Stopped. Close-then-Teardown is the drain-then-reap order. Both are
// idempotent, so a retried pass converges.
func (p *Pool) driveStoppingDrain(ctx context.Context, ports ReconcilePorts, agent *Agent) (AgentEvent, bool, bool) {
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
		// fault keeps the agent at Stopping so a later pass retries — never a leak.
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
// workspace lease (a terminal agent whose Teardown never ran — a Failed agent the
// fault path left holding a partial pod, or a record whose final drain pass never
// landed) and drops the desired record's fold material. Teardown is idempotent (absent
// == nil), so an already-released workspace costs one no-op call and never double-reaps.
// A teardown fault keeps the agent (it is NOT counted reaped and its record/inputs are
// retained) so a later pass retries — never a silent leak. Reap uses the Deps-default
// Workspaces seam (Start's loop cadence binding); when none is bound it reaps the record
// material only. Idempotent.
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
		// Skip a terminal agent that has nothing left to release — zero workspace handle AND
		// no lingering fold/live material. This makes the report COUNT idempotent: once an agent
		// is reaped (its handle zeroed, its fold material dropped), a later Reap pass no-ops it
		// rather than re-counting it. The DesiredStore has no delete; archival of the terminal
		// record itself is the store's policy (a Postgres store moves it to an archive table).
		_, hasInputs := p.lookupSpawnInputs(agent.ID)
		_, hasLive := p.ensureLive().get(agent.ID)
		if agent.Workspace.IsZero() && !hasInputs && !hasLive {
			continue
		}
		// Release any lingering workspace lease before dropping the fold material, so a
		// terminal agent whose Teardown never ran does not leave an orphaned pod the record
		// GC would otherwise silently abandon. A teardown fault is retryable: keep the agent
		// (record + inputs) so a later Reap pass converges, never a leak.
		if !agent.Workspace.IsZero() && p.dependencies.Workspaces != nil {
			if terr := p.dependencies.Workspaces.Teardown(ctx, agent.Workspace); terr != nil {
				continue
			}
			// Mark the lease released on the record (zero the handle) so a later Reap pass does
			// NOT re-Teardown it — Teardown runs AT MOST ONCE per reaped agent (idempotent in
			// effect, not just in the adapter).
			agent.Workspace = workspaceprovider.Handle{}
			if perr := p.dependencies.Desired.Put(ctx, agent); perr != nil {
				continue // a record write fault retries on a later pass; nothing leaked (workspace gone)
			}
		}
		p.ensureLive().drop(agent.ID)
		p.forgetSpawnInputs(agent.ID)
		report.Reaped++
	}
	return report, nil
}

// isUnrecoverableInnerState reports whether an observed agentsession.State is a terminal
// inner FAULT (Failed/Aborted) the orchestrator must surface as a terminal Failed agent
// rather than a re-attachable Suspended one. A graceful StateCompleted is NOT a fault (the
// session finished cleanly); the zero state (StateInitializing) is "not yet observed" and is
// never treated as a fault here.
func isUnrecoverableInnerState(state agentsession.State) bool {
	return state == agentsession.StateFailed || state == agentsession.StateAborted
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
