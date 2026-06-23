package orchestratorservice

import (
	"context"

	"github.com/gophersys/libs/go/orchestrator"
)

// The white-box test seam: it exposes the package-internal composition units (the pure id
// helpers, the namespacing decorator, the template/lease/telemetry seams) to the in-package
// _test files WITHOUT widening the public surface. The Service exposes only the orchestrator
// .Manager verbs + Start/Close; these are the wiring internals a fast unit fault arm exercises
// mock-free.

// BareSequence re-exports bareSequence for the unit test (the bare agent-<n> sequence parser).
func BareSequence(id orchestrator.AgentID) (uint64, bool) { return bareSequence(id) }

// NewSupervisorTemplateStore re-exports the HOST-SIDE supervisor store (inPod false) for the unit
// test — the existing default the existing tests assert against, unchanged.
//
//nolint:ireturn // the test drives the store through the orchestrator.TemplateStore port (Resolve); returning the port is the seam.
func NewSupervisorTemplateStore(substrate orchestrator.Substrate) orchestrator.TemplateStore {
	return newSupervisorTemplateStore(substrate, false, "")
}

// NewInPodSupervisorTemplateStore re-exports the IN-POD supervisor variant (inPod true) so the unit
// test asserts the additive workload-pod shape (a non-empty Entrypoint + the in-pod Env).
//
//nolint:ireturn // the test drives the store through the orchestrator.TemplateStore port (Resolve); returning the port is the seam.
func NewInPodSupervisorTemplateStore(substrate orchestrator.Substrate, natsURL string) orchestrator.TemplateStore {
	return newSupervisorTemplateStore(substrate, true, natsURL)
}

// SupervisorTemplateRef re-exports the pinned supervisor ref for the unit test.
func SupervisorTemplateRef() orchestrator.TemplateRef { return supervisorTemplateRef }

// ToNamespaced re-exports the bare->namespaced rewrite for the unit test (driven without a store).
func ToNamespaced(id orchestrator.AgentID, tenant orchestrator.Tenancy) orchestrator.AgentID {
	return (&namespacingStore{namespaced: map[orchestrator.AgentID]orchestrator.AgentID{}}).toNamespaced(id, tenant)
}

// DockerLeaderProbe re-exports the docker lease's leadership for the unit test.
//
//nolint:ireturn // the test drives the lease through the Lease port (IsLeader); returning the port is the seam.
func DockerLeaderProbe() Lease { return dockerLease{} }

// LocalDockerClusterID re-exports the default cluster id the docker-first Spawn resolves to.
func LocalDockerClusterID() string { return localDockerCluster.ID }

// ReconcileOnce drives ONE deterministic reconcile pass through the embedded Pool, so the
// integration test observes each transition step-by-step (Pending -> Provisioning -> Running and
// the Stop drain) without waiting on the timed loop. It returns the per-pass report.
func (s *Service) ReconcileOnce(ctx context.Context) (orchestrator.ReconcileReport, error) {
	return s.pool.Reconcile(ctx, orchestrator.ReconcilePorts{})
}
