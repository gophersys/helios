// Package orchestratorservice is the docker-first ORCHESTRATOR SERVICE: the composition
// root that wires the REAL orchestrator.Pool over its production adapters and runs the
// reconcile loop, exposing the Manager verbs (Spawn/Get/List/Stop/Resume) the create-saga
// calls. It is the single-process, single-instance binding (docker substrate) of the same
// orchestrator contract that scales out to a multi-node controller with NO surface change —
// the desired-state PostgresStore and the cluster Probe are the only seams sharding touches.
//
// Module: github.com/gophersys/eden/apps/agentgateway (an internal app package, NOT a
// reusable library — it is the product-specific wiring, so it lives here, not in libs/).
//
// THE HEXAGON IT COMPOSES (every port a cited contract, never redefined):
//
//   - Desired   — orchestrator/postgresstore.PostgresStore (the production DesiredStore; the ONE
//     adapter swap for multi-node). The Pool mints bare agent-<n> ids; the production store
//     keys on project-namespaced agent-<project>-<n> ids and REJECTS a bare id. The
//     namespacingStore decorator (this package) bridges the two id spaces at the persistence
//     boundary so the Pool's bare-id side tables and the store's namespaced rows stay coherent
//     — a deterministic bijection, never a redefinition of the store or the id minter.
//   - Probe     — orchestrator/clusterprobe.Probe (the multi-node actual-state Probe over the
//     workspaceprovider supervisor + the NATS health heartbeats). Bound when a HealthSource is
//     supplied; otherwise the Pool's in-process default Probe drives the single-node loop.
//   - Templates — the supervisorTemplateStore (this package): the in-memory TemplateStore that
//     resolves the supervisor AgentTemplate (libs/plugins/supervisor/AGENT-TEMPLATE.md) verbatim,
//     compiled to the docker substrate for the local single-instance posture.
//   - Provider  — workspaceprovider.Provisioner bound to the DOCKER adapter (the single-instance
//     local substrate; ADR-0012 — a kubernetes cluster is the same Provider with a different
//     adapter, not a new code path).
//   - Sessions  — agentsession.Pool bound to the claude Factory (the harness the orchestrator
//     opens sessions through).
//   - Telemetry — the observabilityTelemetry shim (this package): it maps the orchestrator's
//     narrow ObservabilityEvent onto an observability.Event on PlaneAgent (the seam mapping, so
//     orchestrator stays a leaf-ish library and never imports observability's Event shape).
//
// THE LEASE SEAM (lease.go): on docker this service is a SINGLE instance, so the multi-node
// leader Lease is a no-op that is ALWAYS the leader. The seam exists so the kubernetes
// deployment binds a real k8s Lease (only the leader runs the reconcile loop) with NO change
// to this service — Start consults the Lease before each pass the same way locally and in k8s.
//
// SpawnRequest.Cluster defaults to local-docker (Config.DefaultCluster) when a request names
// no cluster, so a docker-first Spawn lands on the local daemon without the caller naming it.
package orchestratorservice
