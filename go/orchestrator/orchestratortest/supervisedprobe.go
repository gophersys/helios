//go:build integration || load

package orchestratortest

import (
	"context"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// SupervisedProbe is the REAL orchestrator.Probe (ADR-0022 §4): it derives each agent's
// Actual from the provider's SUPERVISED Status (the docker/k8s API = the HARD lifecycle)
// rather than the orchestrator's in-process liveTable or raw NATS heartbeats. It is the
// "the orchestrator THINS: it Probes the provider's supervised Status" refinement made
// concrete — reconcile-from-reality on the real substrate, so a stateless restart
// re-derives the truthful actual from the LIVE world.
//
// It reads each agent's recorded workspace Handle (the durable per-agent join key the
// reconcile loop persists at Provision time) from a HandleResolver, then calls the real
// workspaceprovider.Supervisor.Supervised(handle) for the live substrate Status, and maps
// that Status into the orchestrator's Actual. NATS heartbeats remain the SOFT liveness the
// runtime publishes; this probe reads the HARD truth. Read-only — it never mutates.
type SupervisedProbe struct {
	supervisor workspaceprovider.Supervisor // the B2 fat provider's supervision plane (*Provisioner)
	resolver   HandleResolver               // resolves an AgentID to its persisted workspace Handle + last ledger
}

// HandleResolver yields the persisted workspace Handle (and last-observed ledger) for an
// agent — the DesiredStore record the orchestrator already keeps. The probe needs the
// Handle (the supervised-read key) and the Ledger (the budget input the substrate Status
// does not carry — the harness ledger rides NATS/the session, folded onto the record).
// Consumer-defined, one method (≤5).
type HandleResolver interface {
	// HandleFor returns the agent's persisted workspace Handle and last-observed ledger.
	// ok=false when the agent has no record yet (not-yet-provisioned), so the probe reports
	// the absent (all-false) Actual the reconcile diff reads as "no live actual".
	HandleFor(ctx context.Context, id orchestrator.AgentID) (handle workspaceprovider.Handle, ledger agentsession.TokenLedger, ok bool)
}

// NewSupervisedProbe builds the real probe over the provider's supervision plane and a
// resolver for the persisted handles. Pure: no I/O until Observe.
func NewSupervisedProbe(supervisor workspaceprovider.Supervisor, resolver HandleResolver) *SupervisedProbe {
	return &SupervisedProbe{supervisor: supervisor, resolver: resolver}
}

// Observe returns the real Actual for each id, derived from the provider's supervised
// Status (the HARD lifecycle truth). An id with no persisted handle, or whose workspace is
// Gone, reports the absent (all-false) Actual — exactly what the reconcile diff reads as a
// dropped actual (→ Suspended) or not-yet-provisioned. NEVER mutates.
func (p *SupervisedProbe) Observe(ctx context.Context, ids []orchestrator.AgentID) (map[orchestrator.AgentID]orchestrator.Actual, error) {
	out := make(map[orchestrator.AgentID]orchestrator.Actual, len(ids))
	for _, id := range ids {
		handle, ledger, ok := p.resolver.HandleFor(ctx, id)
		if !ok || handle.IsZero() {
			out[id] = orchestrator.Actual{} // no live actual yet (Pending) — absent from the truthful world
			continue
		}
		actual, err := p.observeOne(ctx, handle, ledger)
		if err != nil {
			return nil, err
		}
		out[id] = actual
	}
	return out, nil
}

// observeOne reads one workspace's supervised Status and maps it onto Actual. A gone
// workspace (NotFoundError) is the dropped actual (all-false). The session liveness is read
// off the SAME supervised Status (the Entrypoint workload IS the session's PID-1, so the
// workspace's liveness is the session's liveness — OD-15-a: one supervised truth).
//
//nolint:gocritic // TokenLedger is the contract's copyable value record; the probe folds it back by value.
func (p *SupervisedProbe) observeOne(ctx context.Context, handle workspaceprovider.Handle, ledger agentsession.TokenLedger) (orchestrator.Actual, error) {
	status, err := p.supervisor.Supervised(ctx, handle)
	if err != nil {
		if errors.KindOf(err) == errors.KindNotFound {
			return orchestrator.Actual{}, nil // the workspace is Gone — a dropped actual
		}
		return orchestrator.Actual{}, errors.Wrap(errors.KindUnavailable, "orchestratortest: supervised probe read", err)
	}
	live := workspaceLive(status.State)
	return orchestrator.Actual{
		WorkspaceLive: live,
		// The Entrypoint workload (agent-runtime PID-1) IS the session; its liveness is the
		// workspace's supervised liveness (one hard truth — the provider kills the pod, the
		// session dies with it). A Degraded/Evicted/Gone workspace is a dropped session.
		SessionLive:  live,
		SessionState: sessionStateFor(status.State),
		Ledger:       ledger,
	}, nil
}

// workspaceLive reports whether a supervised State counts the workspace (and its Entrypoint
// session) as live for the reconcile diff. Ready/Running/Provisioning/Degraded are LIVE (a
// Provisioning pod is still settling, a Degraded pod is "recoverable" per the State doc — a
// transient substrate condition must NOT spuriously drop a healthy agent to Suspended). Only
// the TRUE drops — Evicted (the substrate reclaimed it out-of-band, the drift signal) and Gone
// (torn down / never existed) — count as a dropped actual the orchestrator re-adopts.
func workspaceLive(state workspaceprovider.State) bool {
	switch state {
	case workspaceprovider.StateEvicted, workspaceprovider.StateGone:
		return false
	case workspaceprovider.StateProvisioning, workspaceprovider.StateReady,
		workspaceprovider.StateRunning, workspaceprovider.StateDegraded:
		return true
	default:
		return true
	}
}

// sessionStateFor maps the supervised workspace State onto the inner agentsession.State the
// Actual carries (the last-observed agent-loop state the record surfaces). A live workspace
// is StateRunning; anything else is the zero (the dropped/absent reading).
func sessionStateFor(state workspaceprovider.State) agentsession.State {
	if workspaceLive(state) {
		return agentsession.StateRunning
	}
	return agentsession.State(0)
}

// compile-time assertion: *SupervisedProbe is an orchestrator.Probe.
var _ orchestrator.Probe = (*SupervisedProbe)(nil)
