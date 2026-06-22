# Eden orchestrator on Kubernetes (W5)

The per-project orchestrator deployed on Kubernetes: a **stateless, HA Deployment** (3 replicas)
under a **real `coordination.k8s.io/v1` Lease**, with a **namespace-per-project** workspace model.
Proven on a local **k3d** cluster (see "Proof" below). The same manifests target the **remote
eden-central** cluster — only the kubeconfig differs.

## What is here

| File | What it deploys |
|---|---|
| `00-namespace.yaml` | `eden-system` — the orchestrator's control-plane namespace (NOT a project namespace). |
| `10-rbac.yaml` | The `eden-orchestrator` ServiceAccount; the **Lease** Role/RoleBinding (coordination.k8s.io leases in `eden-system`); the **workspace** ClusterRole/ClusterRoleBinding (create project namespaces + workspace pods/secrets/networkpolicies/resourcequotas). |
| `20-postgres.yaml` | The desired-state Postgres (StatefulSet + headless Service + PVC). |
| `30-nats.yaml` | NATS + JetStream (StatefulSet + Service + PVC + config). |
| `40-orchestrator-deployment.yaml` | The orchestrator **Deployment (replicas: 3)** + Service. Only the Lease holder reconciles. |
| `templates/project-namespace.yaml` | The per-project namespace **template**: `eden-<prefix>-<projectUUID>` + a `ResourceQuota` + a default-deny egress `NetworkPolicy`. Substituted per project at runtime (the orchestrator's kubernetesadapter creates the namespace; this is the declarative shape of the project-scoped quota/policy). |

## The Lease seam (how HA works)

`apps/agentgateway/internal/orchestratorservice/lease.go`:

- **`Lease`** is the one-method seam (`IsLeader(ctx)`) the reconcile loop consults before each pass.
- **`dockerLease`** (local docker) is always the leader — one process, no election.
- **`KubernetesLease`** (`NewKubernetesLease`) runs a `client-go`
  `tools/leaderelection` election over a `coordination.k8s.io/v1` Lease object. `Start(ctx)` launches
  the election in the background; `IsLeader` returns the live flag. Only the replica holding the
  Lease runs `Pool.Start` (the reconcile loop), so **two controllers never both provision the same
  Pending agent**. A replica that loses the Lease (a partition / a rollout) stops reconciling within
  the lease duration; a peer acquires it and continues — the HA property.

`Service.Start` consults the injected `Lease` identically locally and in k8s; only the binding
differs (`dockerLease` vs `KubernetesLease`). The kubernetes provisioner is selected by
`Config.Substrate = SubstrateKubernetes` (zero value is docker — this is the docker-FIRST service),
with `Config.Kubeconfig=""` resolving the in-cluster ServiceAccount config.

## The orchestrator command

`cmd/agentgateway` today is the stateless NATS→SSE bridge; the orchestrator role (the binary that
runs `orchestratorservice.Service.Start` under the Lease) is its sibling composition root. The
Deployment's image and env (`EDEN_WORKSPACE_SUBSTRATE`, `EDEN_LEASE_NAME`, `EDEN_LEASE_NAMESPACE`,
`EDEN_LEASE_IDENTITY`, `DATABASE_URL`, `EDEN_NATS_URL`, `EDEN_LABEL_NAMESPACE`) are the contract that
command reads once at the edge (the configuration pattern) into `orchestratorservice.Config` +
`LeaseConfig`/`LeaseDependencies`. The library seam (`lease.go`, the kubernetes provisioner in
`service.go`) is complete and proven; wiring that command is the remaining composition step.

## Apply (local k3d)

```bash
k3d cluster create eden-orch-test
kubectl create namespace eden-system  # or: kubectl apply -f 00-namespace.yaml
# the Postgres password is a Secret reference, never inlined:
kubectl -n eden-system create secret generic eden-orchestrator-postgres \
  --from-literal=password="$(openssl rand -hex 24)"
kubectl apply -f 00-namespace.yaml -f 10-rbac.yaml -f 20-postgres.yaml -f 30-nats.yaml -f 40-orchestrator-deployment.yaml
```

A project namespace from the template (per project, normally applied by the orchestrator):

```bash
PROJECT_UUID=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa LABEL_PREFIX=central \
PROJECT_NAMESPACE=eden-central-$PROJECT_UUID \
  envsubst < templates/project-namespace.yaml | kubectl apply -f -
```

## Proof (real k3d, no mocks)

The orchestrator's kubernetes path is proven end-to-end against a **real k3d cluster** by
`internal/orchestratorservice/service_kubernetes_integration_test.go`
(`TestIntegrationKubernetes_SpawnReconcilesToRunningThenStop`): the production composition
(`Config.Substrate=SubstrateKubernetes` + the k3d kubeconfig) drives **Spawn → reconcile-to-Running
→ Stop → reconcile-to-Stopped**, asserting a real workspace **pod** provisions in a real **project
namespace** that is **created + labeled** with the eden ownership/tenancy labels and **reaped** on
Stop. Run it in the devcontainer:

```bash
bash .devcontainer/base/ctl.sh exec -- bash -lc 'export GOWORK=/workspace/go.work && \
  cd /workspace/apps/agentgateway && go test -tags integration -race \
  -run TestIntegrationKubernetes ./internal/orchestratorservice/...'
```

## Remote eden-central — NOT deployed (human action required)

These manifests deploy IDENTICALLY to the remote **eden-central** cluster — only the kubeconfig (the
`kubectl --kubeconfig <eden-central>` apply target) differs. **This has deliberately NOT been
applied to the remote cluster.** Before a human applies it to eden-central:

1. Provision the `eden-orchestrator-postgres` Secret from **Vault**, not a literal (the secret-safety
   rule); do not commit the value.
2. Pin the image to a digest (`ghcr.io/gophersys/eden/agentgateway@sha256:…`), not `:latest`.
3. Confirm the CNI enforces NetworkPolicy (Calico/Cilium) so the default-deny egress is live (it is
   inert on flannel — the honest `CapEgressPolicy=Absent`).
4. Wire + ship the orchestrator command (see "The orchestrator command") so the Deployment's
   container actually runs `Service.Start` under `NewKubernetesLease`.
