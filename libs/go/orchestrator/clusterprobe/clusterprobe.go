package clusterprobe

import (
	"context"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// WorkspaceLister is the WORKSPACE-liveness source — the narrow subset of the
// workspaceprovider.Supervisor port this Probe needs (accept-interfaces, 10 §9): one
// list-by-label of the LIVE workspaces in a project's ownership domain, read from the
// substrate (reconcile-from-reality, never an in-memory cache that can lie across a
// restart). The concrete *workspaceprovider.Provisioner satisfies it (its Reconcile verb
// is exactly this shape); a fake satisfies it in a unit test. One method — well under the
// ≤5 ceiling.
type WorkspaceLister interface {
	// Reconcile lists the workspaces Eden authored within the selector's tenancy with each
	// Descriptor's CURRENT normalized State (the live substrate truth). It is the
	// list-by-label re-adoption a stateless restart performs; this Probe calls it scoped to
	// ONE project so any replica sees the same workspace set. It binds
	// workspaceprovider.Supervisor.Reconcile verbatim.
	Reconcile(ctx context.Context, selector workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error)
}

// HealthSource is the SESSION-liveness source — the most-recent NATS health heartbeat per
// agent (agentruntime.Heartbeat on agent.<id>.health). The Probe reads a SNAPSHOT of the
// latest-known beat (a last-value/KV-style read), NOT a subscription: the per-pass Probe is
// read-only and stateless, so the same snapshot read makes any replica derive the same
// SessionState. An adapter over a NATS last-value bucket / a most-recent-beat cache fed by a
// durable subscription satisfies it; a fake satisfies it in a unit test. One method.
//
// The returned map is keyed by agentruntime.AgentID (the health-subject token); an id with
// no observed beat is ABSENT from the map (the not-yet-heartbeated or expired-beat path),
// which the derivation reads as "no live session", mirroring live.go's absent-handle rule.
type HealthSource interface {
	// LatestHealth returns the most-recent heartbeat per requested agent id. An id this
	// source has never observed (or whose last beat has expired under the source's own
	// liveness window) is omitted from the result — the source NEVER fabricates a beat.
	LatestHealth(ctx context.Context, ids []agentruntime.AgentID) (map[agentruntime.AgentID]agentruntime.Heartbeat, error)
}

// Config is the immutable, fully-resolved input for one Probe (the configuration discipline:
// parsed at the edge, frozen — the idiomatic spine type name per HNS-1 10 §5). It is SCOPED TO
// ONE PROJECT: every Observe lists only that project's namespace, so a per-tenant reconcile
// pass never reads another tenant's workspaces. It holds NO live handle and NO secret value.
type Config struct {
	// Tenant is the org/project this Probe observes (orchestrator.Tenancy, 07 §6). It scopes
	// the workspace list-by-label to one namespace. Required: the zero Tenant is a
	// ConfigError (a Probe that lists ALL tenancies would let one project's reconcile pass
	// read another's workspaces).
	Tenant orchestrator.Tenancy

	// AgentLabelKey is the ownership-domain label key under which a provisioned workspace
	// carries its orchestrator.AgentID — the join key between a workspaceprovider.Descriptor
	// and an agent id. It MUST equal the key the orchestrator's fold stamps (today
	// "eden.agent"); DefaultAgentLabelKey supplies that default when this is empty, so the
	// common wiring needs no override. (Integration note: the orchestrator should promote its
	// unexported labelAgentID constant to an exported one this field cites, so producer and
	// consumer share one home — 10 §9.)
	AgentLabelKey string
}

// DefaultAgentLabelKey is the ownership-domain label key the orchestrator's fold stamps an
// agent id under today (orchestrator fold.go labelAgentID). Config.AgentLabelKey defaults to
// this when left empty. It lives here as the consumer-side default ONLY because
// the producer constant is currently unexported; the integration note asks the orchestrator
// to export the one home both sides cite.
const DefaultAgentLabelKey = "eden.agent"

// Deps is the injected record of ports the Probe drives (the hexagon — the idiomatic spine
// type name per HNS-1 10 §5). Both ports are required; a nil port is a ConfigError at New
// (fail cheap, before any query).
type Deps struct {
	Workspaces WorkspaceLister // the project-namespace workspace list-by-label (the HARD lifecycle)
	Health     HealthSource    // the most-recent NATS health heartbeat per agent (the inner-loop signal)
}

// ClusterProbe is the cluster-querying orchestrator.Probe (return-concrete). It is stateless: every
// Observe is a fresh query of the two sources, so any orchestrator replica computes the same
// Actual after a restart (no in-memory table — live.go's table is exactly what this replaces
// at multi-node). Safe for concurrent use (it holds only immutable configuration + two
// concurrency-safe ports). Its zero value is unusable; obtain one from New.
type ClusterProbe struct {
	tenant        orchestrator.Tenancy
	agentLabelKey string
	workspaces    WorkspaceLister
	health        HealthSource
}

// Static assertion: *ClusterProbe satisfies the orchestrator.Probe port it binds (one concept, one
// home — it never redefines Probe or Actual).
var _ orchestrator.Probe = (*ClusterProbe)(nil)

// New is the pure constructor spine New(configuration, dependencies) -> (T, error): it
// validates the wiring and freezes the configuration, doing NO I/O, NO clock read, NO
// globals — every source the Probe touches arrives through the two ports. It returns a
// ConfigError (Kind=Invalid) on a zero Tenant or a nil port, so a misconfigured Probe fails
// at composition, never at the first Observe.
func New(configuration Config, dependencies Deps) (*ClusterProbe, error) {
	if configuration.Tenant.IsZero() {
		return nil, wrapKind(&ConfigError{Reason: "Config.Tenant is required (a project-scoped Probe must name its tenancy)"})
	}
	if dependencies.Workspaces == nil {
		return nil, wrapKind(&ConfigError{Reason: "Deps.Workspaces is required (the workspace list-by-label source)"})
	}
	if dependencies.Health == nil {
		return nil, wrapKind(&ConfigError{Reason: "Deps.Health is required (the most-recent-heartbeat source)"})
	}
	agentLabelKey := configuration.AgentLabelKey
	if agentLabelKey == "" {
		agentLabelKey = DefaultAgentLabelKey
	}
	return &ClusterProbe{
		tenant:        configuration.Tenant,
		agentLabelKey: agentLabelKey,
		workspaces:    dependencies.Workspaces,
		health:        dependencies.Health,
	}, nil
}

// Observe returns the actual world-state of the agents in ids, derived from the live
// workspace set + the most-recent heartbeats — NOT from an in-memory table, so the result is
// identical on any replica after a restart. It binds orchestrator.Probe.Observe verbatim:
//
//   - List the LIVE workspaces in this Probe's project namespace ONCE (one list-by-label,
//     not one query per id), keyed by the AgentID carried on each Descriptor's label.
//   - Read the most-recent heartbeat for the requested ids ONCE.
//   - For each requested id, FOLD its workspace Descriptor (if any) + its heartbeat (if any)
//     into an orchestrator.Actual via the pure deriveActual; an id with NEITHER a live
//     workspace NOR a heartbeat is ABSENT from the result (the not-yet-provisioned /
//     dropped-actual path, mirroring live.go's absent-handle rule).
//
// It NEVER mutates (the Probe is read-only — the property that keeps the reconcile diff's
// "actual" truthful and independent of the desired record). A source fault surfaces as a
// wrapped WorkspaceQueryError / HealthQueryError (Kind=Unavailable) so the reconcile pass
// treats the whole Observe as failed rather than acting on a half-known, fabricated actual.
func (p *ClusterProbe) Observe(ctx context.Context, ids []orchestrator.AgentID) (map[orchestrator.AgentID]orchestrator.Actual, error) {
	if len(ids) == 0 {
		return map[orchestrator.AgentID]orchestrator.Actual{}, nil
	}

	descriptors, err := p.workspaces.Reconcile(ctx, p.projectSelector())
	if err != nil {
		return nil, wrapKind(&WorkspaceQueryError{
			Organization: p.tenant.OrganizationID,
			Project:      p.tenant.ProjectID,
			Cause:        err,
		})
	}
	liveWorkspaces := p.indexWorkspacesByAgentID(descriptors)

	beats, err := p.health.LatestHealth(ctx, toRuntimeIDs(ids))
	if err != nil {
		return nil, wrapKind(&HealthQueryError{Cause: err})
	}

	out := make(map[orchestrator.AgentID]orchestrator.Actual, len(ids))
	for _, id := range ids {
		workspace, hasWorkspace := liveWorkspaces[id]
		beat, hasBeat := beats[agentruntime.AgentID(id)]
		if !hasWorkspace && !hasBeat {
			// No live actual on either source — absent from the result (the not-yet-
			// provisioned or fully-dropped path; live.go reports both-false for this id, this
			// Probe omits it, which is the documented "no live actual" contract on
			// orchestrator.Probe.Observe — an id with no live actual is absent).
			continue
		}
		out[id] = deriveActual(hasWorkspace, workspace, hasBeat, beat)
	}
	return out, nil
}

// projectSelector is the list-by-label selector scoping a workspace query to this Probe's
// ONE project: the tenancy keys are a REQUIRED selector match (cross-tenant listing is
// impossible by construction, workspaceprovider 07 §6), so a per-tenant pass can never read
// another tenant's workspaces.
func (p *ClusterProbe) projectSelector() workspaceprovider.Selector {
	return workspaceprovider.Selector{
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: p.tenant.OrganizationID,
			workspaceprovider.LabelProject:      p.tenant.ProjectID,
		},
	}
}

// indexWorkspacesByAgentID keys the listed Descriptors by the orchestrator.AgentID each
// carries on its ownership-domain label (the join key the orchestrator's fold stamps). A
// Descriptor with no agent-id label is SKIPPED (a workspace this Probe cannot attribute to a
// requested agent — never mis-attributed). A live workspace is one whose normalized State is
// not terminal Gone (a Gone Descriptor is a tombstone the substrate has not yet reaped, not a
// live workspace).
func (p *ClusterProbe) indexWorkspacesByAgentID(descriptors []workspaceprovider.Descriptor) map[orchestrator.AgentID]workspaceprovider.Descriptor {
	byID := make(map[orchestrator.AgentID]workspaceprovider.Descriptor, len(descriptors))
	for _, descriptor := range descriptors {
		id, ok := descriptor.Labels[p.agentLabelKey]
		if !ok || id == "" {
			continue
		}
		if descriptor.State == workspaceprovider.StateGone {
			continue
		}
		byID[orchestrator.AgentID(id)] = descriptor
	}
	return byID
}

// toRuntimeIDs maps the orchestrator agent ids onto the agentruntime health-subject ids (the
// two id spaces are the SAME stable per-agent token — orchestrator.AgentID equals the
// agentsession SessionID equals the agentruntime AgentID; this is the explicit conversion at
// the seam, never a redefinition of either type).
func toRuntimeIDs(ids []orchestrator.AgentID) []agentruntime.AgentID {
	out := make([]agentruntime.AgentID, len(ids))
	for i, id := range ids {
		out[i] = agentruntime.AgentID(id)
	}
	return out
}
