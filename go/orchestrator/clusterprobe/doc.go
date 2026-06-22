// Package clusterprobe is the cluster-querying orchestrator.Probe: it derives an
// agent's ACTUAL world-state from TWO durable, restart-survivable sources instead of an
// in-process side table, so any orchestrator replica computes the SAME Actual after a
// recycle (the multi-node Probe seam, orchestrator ports.go §Probe / live.go).
//
//   - WORKSPACE liveness comes from the workspaceprovider Supervisor: a list-by-label of
//     the LIVE workspaces in a project's namespace (reconcile-from-reality — the docker/k8s
//     API is the HARD lifecycle, never an in-memory cache that can lie across a restart,
//     workspaceprovider supervise.go). The agent id rides each workspace's ownership-domain
//     label (the join key the orchestrator's fold stamps), so a Descriptor maps back to an
//     orchestrator.AgentID with no separate table.
//   - SESSION liveness + the inner agent-loop state come from the NATS health heartbeats
//     (agentruntime.Heartbeat on agent.<id>.health: Phase / SessionState / LastSeq). The
//     Probe reads the MOST-RECENT beat per agent (a last-value snapshot, not a subscription)
//     and folds Phase+SessionState into SessionLive + the observed agentsession.State the
//     reconcile loop branches on.
//
// Observe is SCOPED TO A PROJECT (an orchestrator.Tenancy = organization/project): one
// list-by-label query over that namespace, intersected with the requested ids, so a
// per-tenant reconcile pass never reads another tenant's workspaces (cross-tenant listing
// is impossible by construction — the tenancy keys are a required selector match,
// workspaceprovider 07 §6).
//
// It binds the EXISTING orchestrator.Probe port (one method, Observe) and returns the
// EXISTING orchestrator.Actual value — it redefines neither (one concept, one home, 10 §9).
// The heartbeat shape it reads is agentruntime.Heartbeat verbatim (the health-subject wire
// contract owner); the workspace shape is workspaceprovider.Descriptor verbatim. New is the
// pure constructor spine New(configuration Config, dependencies Deps) -> (*Probe, error): no I/O, no
// clock read, no globals — every source arrives through an injected, consumer-defined port,
// which is exactly what makes the cluster Probe fakeable without a real cluster or a real
// NATS bus.
package clusterprobe
