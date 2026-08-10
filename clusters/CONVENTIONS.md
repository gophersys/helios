# clusters — conventions

A cluster instance is `clusters/instances/<name>/`. It contains:

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

A managed cluster (EKS, AKS or OKE) has no `nodes/` subdirectory, because the
cloud owns the node lifecycle.

## The identity.yaml schema

These fields are the minimum:

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

A namespace in a cluster is one of 3 kinds:

| Pattern                | Example                                   | Scope                                          |
|------------------------|-------------------------------------------|------------------------------------------------|
| `<project>-<env>`      | `codectl-prod`, `fintel-staging`          | All apps of that project in that env           |
| `platform-<component>` | `platform-ingress`, `platform-monitoring` | One platform component installation            |
| `kube-*`               | `kube-system`                             | Kubernetes-reserved (never touched by platform) |

- `<project>` MUST appear in the cluster's `projects_hosted:` list.
- `<env>` MUST be `prod`, `staging`, `dev` or `lab`.
- Inside `<project>-<env>` the apps talk to each other freely, because the
  NetworkPolicy allows traffic in the same namespace. Traffic between projects
  needs explicit allow rules.
- The quota applies at the level of the `<project>-<env>` namespace, and all the
  apps of that project in that env share it.

A **single-project cluster** works the same way. Its `projects_hosted:` list has
1 entry, and its namespaces look like `onlyproject-prod` and
`onlyproject-staging`. A **multi-project cluster** serves many projects side by
side, each in its own `<project>-<env>` namespaces. A move between the 2
topologies needs no code change.

## Node role taxonomy

Every cluster node declares a `kubernetes.cluster_role` in its identity.yaml.
The valid roles and their defaults:

| Role      | Label `role=` | Taint                              | Typical workloads                          |
|-----------|---------------|------------------------------------|--------------------------------------------|
| `apps`    | `apps`        | none (default — anything schedules) | Stateless APIs, frontends, workers         |
| `data`    | `data`        | `data=true:NoSchedule`             | Databases, NATS, object stores             |
| `devops`  | `devops`      | `devops=true:PreferNoSchedule`     | Platform components (observability, ingress) |
| `build`   | `build`       | `build=true:NoSchedule`            | CI job runners                             |
| `batch`   | `batch`       | `batch=true:PreferNoSchedule`      | Short-lived jobs on preemptible compute    |

The `node_role_assignments:` block of the cluster and the
`kubernetes.cluster_role` of each node must agree.
`bash clusters/ctl.sh validate` enforces this.

For a self-managed cluster, the Ansible role `cluster-node-labels` applies the
labels and the taints to the k8s node at k3s-join time. For a managed cluster,
the Terraform module of the provider sets them through the labels and taints
configuration of the node group.

## Platform component opt-in

Every cluster always installs `platform/core/*`. See the install order in
`platform/core/README.md`. A cluster opts into `platform/services/*` through
`platform_services:` in its identity.yaml.

The value overrides for one cluster live at
`clusters/instances/<c>/overlays/{core,services}/<path>/values.yaml`. The `apply`
verb of the platform merges them on top of the baseline of the archetype.

## Cluster lifecycle

### Bootstrap

1. Declare the cluster: scaffold identity.yaml, resolve the TODOs, and commit.
2. For a self-managed cluster, declare every node in
   `nodes/<host>/identity.yaml`.
3. Provision the hosts with Terraform through `providers/<cloud>/modules/`, or
   with the bare-metal provider for existing hardware.
4. Run the Ansible `bootstrap.yaml` playbook across the nodes. It installs
   Tailscale, joins the mesh and bootstraps the Bitwarden client.
5. Install K3s with the Ansible `k3s-install` and `k3s-join` playbooks
   (`providers/kubernetes-manual/`).
6. Apply `platform/core/*` in order. See its README.
7. Apply `platform/services/*` for each opt-in in `platform_services:`.
8. Verify: `kubectl get pods -A` shows everything Running, and the policy
   PolicyReports show no unexpected denial.

### Upgrade (Kubernetes version)

1. Change `distribution_version` in identity.yaml.
2. Commit, open a PR, and merge.
3. Run the `k3s-upgrade` playbook. It drains and upgrades one node at a time, and
   it respects the PDBs.
4. Verify that `cluster_slo.control_plane_availability` did not change across the
   upgrade window.

### Teardown

**This is never a routine operation.** Terraform `prevent_destroy` protects the
`irreplaceable_nodes:`. `platform/core/policy/` protects the namespaces and the
PVCs. See `CATALOG.md`.

If a cluster must genuinely be retired:

1. Set `status: retired` in identity.yaml.
2. Migrate or snapshot every PV labeled `platform.gophersys/retain=true`.
3. Open an explicit platform PR that documents the reason for the teardown.
4. Remove the `irreplaceable_nodes` entries one at a time. Each removal needs an
   override annotation.

## Ownership: who manages what

- **The host OS, the k3s install, Tailscale and the secrets client** → Ansible,
  through `machines/roles/*`, which
  `providers/kubernetes-manual/ansible/` calls for cluster members.
- **The Kubernetes control plane, the node registration, and the labels and
  taints** → the k3s or provider install step, plus the `cluster-node-labels`
  Ansible role.
- **Cluster-wide resources (NetworkPolicy baselines, PSS labels, Kyverno CRs)** →
  `platform/core/*`.
- **Cluster-wide shared services (observability, databases, messaging)** →
  `platform/services/*`, which this cluster opts into.
- **Tuning for one cluster (chart values, quotas, routes)** → the `overlays/`
  directory of this instance.
- **App workloads** → outside this repo. An app consumes the cluster through
  `contracts/*`.

## Templates

A cluster template at `clusters/templates/<name>/` contains:

```
clusters/templates/<t>/
├── README.md                # when to use this template
├── identity.yaml            # scaffold for instance identity.yaml (with __CLUSTER_NAME__ placeholder)
└── nodes/                   # (self-managed only) per-node templates
    └── <node-template>/
        └── identity.yaml    # scaffold for node identity.yaml (with __HOST_NAME__)
```

See `clusters/templates/README.md` for the catalog.

## ctl.sh verbs (current and planned)

Current:
- `status` — counts the instances, the templates and the nodes.
- `validate` — schema checks on identity.yaml, plus shellcheck and a JSON parse.
- `new-cluster` — scaffold an instance from a template.
- `new-cluster-node` — scaffold a node under an existing cluster.

Planned, and they land when the first cluster bootstraps:
- `bootstrap <cluster>` — run the full provision and install sequence.
- `apply <cluster>` — apply every `platform/*` component: core plus the services
  that the cluster opted into.
- `upgrade <cluster> --distribution-version=<v>` — a rolling Kubernetes upgrade.
- `drift <cluster>` — compare the declared state with the live state.
- `shell <cluster>` — a kubectl shell with the cluster's kubeconfig from
  Bitwarden.
