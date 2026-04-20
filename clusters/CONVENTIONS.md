# clusters — conventions

A cluster instance is `clusters/instances/<name>/` and contains:

```
clusters/instances/<name>/
├── identity.yaml             # required — cluster-level declaration
├── nodes/                    # cluster member hosts (self-managed clusters only)
│   └── <host>/
│       └── identity.yaml     # per-node declaration
├── overlays/                 # per-cluster platform component value overrides
│   ├── core/
│   │   └── <component>/values.yaml
│   └── services/
│       └── <category>/<impl>/values.yaml
├── terraform/                # (optional) provider-rooted TF that creates the cluster + nodes
└── kubeconfig/               # (generated, gitignored, tmpfs only) kubeconfig shuttled via BW
```

Managed clusters (EKS/AKS/OKE) have no `nodes/` subdir — node lifecycle
is owned by the cloud.

## identity.yaml schema

Required at minimum:

```yaml
name: <cluster-name>                      # matches directory name
template: <cluster-template>              # references clusters/templates/<t>/
distribution: k3s | eks | aks | oke
distribution_version: <pinned>

purpose: <short free-text>
status: planned | active | retired
owner: <email>
domain: <public DNS zone, e.g. brain.mateosegura.com>

network:
  cni: cilium | calico | flannel | vpc-cni | azure-cni
  tailnet_joined: true | false
  pod_cidr: <CIDR>
  service_cidr: <CIDR>

node_role_assignments:                    # hostname → cluster_role
  <hostname>: apps | data | devops | build | batch

policy_profile: baseline | strict | audit-only

# Projects hosted on this cluster — source of truth for namespace naming.
# Every <project>-<env> namespace created must have <project> listed here;
# namespace-provisioner rejects otherwise. One cluster can serve many
# projects (multi-project cluster) or a single project (dedicated cluster).
projects_hosted:
  - <project-name>                        # e.g., codectl, fintel, finances

namespace_provisioning:
  default_quota_tier_by_env:              # quota tier per env
    prod:     medium                      # medium | small | large
    staging:  small
    dev:      small
    lab:      small
  auto_netpol: true | false
  auto_pss_label: true | false
  quota_overrides: {}                     # map <project>-<env>: <tier> — explicit escalations
    # codectl-prod: large

platform_services:                        # opt-in per service; core is always on
  <category>:
    <impl>:
      enabled: true | false
      version: <pinned>                   # required when enabled

chart_archetypes: []                      # informational — which charts this cluster serves

cluster_slo:
  control_plane_availability: { target: <%>, window: <d> }
  api_latency:                { target_ms: <n>, window: <d>, percentile: 90 | 95 | 99 }

cost_envelope:
  monthly_usd_target: <n>
  monthly_usd_ceiling: <n>
  note: <free-text>

protection:
  irreplaceable_nodes: []                 # hostnames; Terraform marks these prevent_destroy
  prod_volume_delete_requires_override: true | false
  namespace_delete_requires_override: true | false
```

## Namespace taxonomy

Namespaces in a cluster fall into three kinds:

| Pattern                | Example                                   | Scope                                          |
|------------------------|-------------------------------------------|------------------------------------------------|
| `<project>-<env>`      | `codectl-prod`, `fintel-staging`          | All apps of that project in that env           |
| `platform-<component>` | `platform-ingress`, `platform-monitoring` | One platform component installation            |
| `kube-*`               | `kube-system`                             | Kubernetes-reserved (never touched by platform) |

- `<project>` MUST be listed in the cluster's `projects_hosted:` list.
- `<env>` MUST be `prod | staging | dev | lab`.
- Inside `<project>-<env>`, apps talk to each other freely (same-ns
  NetworkPolicy). Cross-project traffic requires explicit allow rules.
- Quota applies at the `<project>-<env>` namespace level (shared by
  all apps of that project in that env).

**Single-project clusters** work the same way — their `projects_hosted:`
has one entry, their namespaces look like `onlyproject-prod`,
`onlyproject-staging`, etc. **Multi-project clusters** serve many
projects side by side, each in its own `<project>-<env>` namespaces.
No code change moves between the two topologies.

## Node role taxonomy

Every cluster node declares a `kubernetes.cluster_role` in its
identity.yaml. Valid roles + defaults:

| Role      | Label `role=` | Taint                              | Typical workloads                          |
|-----------|---------------|------------------------------------|--------------------------------------------|
| `apps`    | `apps`        | none (default — anything schedules) | Stateless APIs, frontends, workers         |
| `data`    | `data`        | `data=true:NoSchedule`             | Databases, NATS, object stores             |
| `devops`  | `devops`      | `devops=true:PreferNoSchedule`     | Platform components (observability, ingress) |
| `build`   | `build`       | `build=true:NoSchedule`            | CI job runners                             |
| `batch`   | `batch`       | `batch=true:PreferNoSchedule`      | Short-lived jobs on preemptible compute    |

The cluster's `node_role_assignments:` block and each node's
`kubernetes.cluster_role` must agree; `bash clusters/ctl.sh validate`
enforces.

Ansible role `cluster-node-labels` applies the labels + taints to the
k8s node at k3s-join time (for self-managed). For managed clusters, the
provider's Terraform module sets them via the node group's labels /
taints config.

## Platform component opt-in

`platform/core/*` is always installed on every cluster (see
`platform/core/README.md` install order). `platform/services/*` is
per-cluster opt-in via `platform_services:` in the cluster's
identity.yaml.

Per-cluster value overrides live at
`clusters/instances/<c>/overlays/{core,services}/<path>/values.yaml`
and are merged by the platform's `apply` verb on top of the archetype's
baseline.

## Cluster lifecycle

### Bootstrap

1. Declare the cluster: scaffold identity.yaml, fill TODOs, commit.
2. For self-managed: declare every node in `nodes/<host>/identity.yaml`.
3. Provision hosts: Terraform via `providers/<cloud>/modules/` (or
   bare-metal provider for existing hardware).
4. Ansible: run `bootstrap.yaml` playbook across the nodes (installs
   Tailscale, joins mesh, bootstraps BW client).
5. K3s install: Ansible `k3s-install` + `k3s-join` playbooks
   (`providers/kubernetes-manual/`).
6. Apply `platform/core/*` in order (see its README).
7. Apply `platform/services/*` per `platform_services:` opt-ins.
8. Verify: `kubectl get pods -A` shows everything Running; policy
   PolicyReports show no unexpected denies.

### Upgrade (K8s version)

1. Bump `distribution_version` in identity.yaml.
2. Commit + PR + merge.
3. Run `k3s-upgrade` playbook — drains + upgrades one node at a time,
   respecting PDBs.
4. Verify cluster_slo.control_plane_availability unchanged across the
   upgrade window.

### Teardown

**Never a routine operation.** `irreplaceable_nodes:` are protected
by Terraform `prevent_destroy`. Namespaces and PVCs are protected by
`platform/core/policy/` (see `CATALOG.md`).

If a cluster genuinely must be retired:

1. Change `status: retired` in identity.yaml.
2. Migrate or snapshot every PV labeled `platform.gophersys/retain=true`.
3. Explicit platform PR documenting the teardown rationale.
4. Remove `irreplaceable_nodes` entries one by one (requires override
   annotation on each).

## Ownership: who manages what

- **Host OS, k3s install, Tailscale, secrets client** → Ansible (via
  `machines/roles/*`, called by `providers/kubernetes-manual/ansible/`
  for cluster members).
- **K8s control plane, node registration, labels+taints** → the k3s /
  provider install step + `cluster-node-labels` Ansible role.
- **Cluster-wide resources (NetPol baselines, PSS labels, Kyverno CRs)**
  → `platform/core/*`.
- **Cluster-wide shared services (observability, dbs, msg)** →
  `platform/services/*`, opted into by this cluster.
- **Per-cluster tuning (chart values, quotas, routes)** → this instance's
  `overlays/` directory.
- **App workloads** → out-of-repo; apps consume the cluster via
  `contracts/*`.

## Templates

Cluster templates under `clusters/templates/<name>/` contain:

```
clusters/templates/<t>/
├── README.md                # when to use this template
├── identity.yaml            # scaffold for instance identity.yaml (with __CLUSTER_NAME__ placeholder)
└── nodes/                   # (self-managed only) per-node templates
    └── <node-template>/
        └── identity.yaml    # scaffold for node identity.yaml (with __HOST_NAME__)
```

See `clusters/templates/README.md` for the catalog.

## ctl.sh verbs (current + planned)

Current:
- `status` — counts instances + templates + nodes.
- `validate` — schema checks on identity.yaml + shellcheck + JSON parse.
- `new-cluster` — scaffold an instance from a template.
- `new-cluster-node` — scaffold a node under an existing cluster.

Planned (land as the first cluster bootstraps):
- `bootstrap <cluster>` — run the full provision + install sequence.
- `apply <cluster>` — apply every platform/* component (core + opted services).
- `upgrade <cluster> --distribution-version=<v>` — rolling k8s upgrade.
- `drift <cluster>` — diff declared state vs live state.
- `shell <cluster>` — kubectl shell with the cluster's kubeconfig from BW.
