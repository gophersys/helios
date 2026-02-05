# Concord Infrastructure v2 Plan

This document outlines the plan for taking a barebones K3s cluster to a
fully-ready state for deploying Concord application Helm charts.

---

## Table of Contents

1. [Folder Structure](#1-folder-structure)
2. [Node Labeling & Taints](#2-node-labeling--taints)
3. [Storage (Longhorn)](#3-storage-longhorn)
4. [Namespaces](#4-namespaces)
5. [RBAC](#5-rbac)
6. [Additional Cluster Concerns](#6-additional-cluster-concerns)
7. [Execution Order](#7-execution-order)
8. [File Manifest](#8-file-manifest)

---

## 1. Folder Structure

```
deploy/infra/
├── terraform/                    # Future cloud IaC definitions
│   ├── .gitkeep
│   └── README.md                 # Explains purpose, empty for now
│
├── v2/                           # "Barebones to ready" cluster setup
│   ├── plan/
│   │   └── README.md             # This file
│   ├── 00-labels-taints.sh       # Node labeling (and optional tainting) script
│   ├── 01-namespaces.yaml        # Namespace definitions
│   ├── 02-longhorn-values.yaml   # Longhorn Helm values
│   ├── 03-storage-classes.yaml   # StorageClass definitions
│   ├── 04-rbac.yaml              # All RBAC resources
│   ├── 05-resource-quotas.yaml   # Per-namespace resource quotas
│   ├── 06-limit-ranges.yaml      # Default pod resource boundaries
│   ├── 07-network-policies.yaml  # Namespace isolation rules
│   ├── ctl.sh                    # Orchestration script (apply all in order)
│   └── README.md                 # Usage documentation
│
└── project.json                  # Nx config
```

Legacy files (`deploy/infra/ctl.sh`, `deploy/infra/README.md`,
`deploy/infra/roles/admin.yaml`, and the empty `roles/` and `labels/`
directories) have been deleted. v2 is the sole source of truth for cluster
infrastructure.

The numbered prefixes enforce apply order. `ctl.sh` will apply them
sequentially so there are no dependency issues.

---

## 2. Node Labeling & Taints

### Current State

- Server nodes: only have built-in `node-role.kubernetes.io/control-plane` labels
  and LB pool labels. No custom taints.
- Agent nodes: have `node.longhorn.io/create-default-disk=true`. No taints.
- MTIB nodes: no custom labels or taints at all.

### Target State

All nodes get a standardized `corekinect.com/role` label. Nodes also get a
`corekinect.com/purpose` label where applicable:

| Node | Role Label | Purpose Label | Taint (opt-in) |
|------|------------|---------------|----------------|
| concordserver01-03 | `server` | `platform` | `corekinect.com/role=server:PreferNoSchedule` |
| concordagent01-02 | `agent` | `manufacturing` | `corekinect.com/role=agent:PreferNoSchedule` |
| concordagent03 | `agent` | _(none)_ | `corekinect.com/role=agent:PreferNoSchedule` |
| verdin-imx8mm-* (mfg) | `edge` | `manufacturing` | `corekinect.com/role=edge:NoSchedule` |
| verdin-imx8mm-15702161 | `edge` | `validation` | `corekinect.com/role=edge:NoSchedule` |

Taints are **opt-in** via `--with-taints`. Labels are always applied.

### Why PreferNoSchedule (not NoSchedule) for server and agent?

- `PreferNoSchedule` means "prefer not to schedule here unless the pod explicitly
  tolerates it OR there's nowhere else to go." This gives flexibility: if an app
  Helm chart sets the right tolerations + nodeSelector, it lands on the correct
  nodes. If a system-level DaemonSet (like Longhorn) needs to run, it still can
  without extra config.
- MTIB nodes use hard `NoSchedule` because nothing should ever accidentally
  land on custom hardware.

### Implementation

`00-labels-taints.sh` - a bash script that:

1. Labels all server nodes with `corekinect.com/role=server`
2. Labels all agent nodes with `corekinect.com/role=agent`
3. Labels all edge nodes with `corekinect.com/role=edge` (discovered via `kubernetes.io/arch=arm64`)
4. Applies `corekinect.com/purpose` per node using a `NODE_PURPOSE` associative array
5. Edge nodes are split into `EDGE_MANUFACTURING` and `EDGE_VALIDATION` arrays
6. Applies taints only when `--with-taints` is passed
7. Is idempotent (safe to re-run)

---

## 3. Storage (Longhorn)

### Critical Finding: Agent Nodes Have the Most Storage

| Node Type | Ephemeral Storage | Count | Total |
|-----------|-------------------|-------|-------|
| Server | ~20.5 GiB | 3 | ~61.5 GiB |
| Agent | **~44 GiB** | 3 | **~132 GiB** |
| MTIB | ~14.3 GiB | 6 | ~85.8 GiB (unusable for storage) |

Server nodes are the smallest. They're also already running etcd (which uses
disk I/O and storage). **Longhorn storage should run on agent nodes.**

### Longhorn Deployment Strategy

Install via Helm with the following constraints:

- **Data plane (storage replicas)**: Agent nodes only
  - `node.longhorn.io/create-default-disk=true` is already on agent nodes
  - Longhorn `defaultDataPath`: `/var/lib/longhorn`
  - Replica count: **2** (3 agent nodes, but 2 replicas gives good
    redundancy without eating all capacity)
- **Control plane (manager/driver)**: Runs as DaemonSet on all amd64 nodes
  by default, but we restrict to server + agent nodes only via node selector
  on the Longhorn system components to avoid scheduling on ARM edge nodes.

### Storage Classes

Two classes:

1. **`longhorn` (default)** - General purpose, 2 replicas, `Retain` reclaim policy.
   This is the one your databases (Postgres, etc.) will use. `Retain` means
   if you delete the PVC, the PV and data stick around for manual recovery.

2. **`longhorn-ephemeral`** - 1 replica, `Delete` reclaim policy. For scratch
   volumes, build caches, anything you don't care about keeping.

### Recovery Path

With `Retain` reclaim policy on the default storage class:

- **First deploy**: Longhorn creates new PVs, PVCs bind to them, databases
  initialize fresh.
- **Recovery**: If a PVC is deleted but the PV remains (status `Released`),
  you can manually patch the PV to remove its `claimRef`, then create a new
  PVC that binds to it. Your data is intact.
- **Full nuke**: Delete both PVC and PV. Next deploy starts fresh.

The `ctl.sh` script will NOT auto-delete PVs. Recovery/cleanup is always manual
and intentional.

### Longhorn Helm Values (`02-longhorn-values.yaml`)

Key settings:
```yaml
persistence:
  defaultClassReplicaCount: 2
  reclaimPolicy: Retain

defaultSettings:
  defaultDataPath: /var/lib/longhorn
  createDefaultDiskLabeledNodes: true       # Only nodes with the label get disks
  defaultDataLocality: disabled             # Allow replicas on any storage node
  nodeDownPodDeletionPolicy: delete-both-statefulset-and-deployment-pod
  systemManagedComponentsNodeSelector: "kubernetes.io/arch:amd64"

longhornManager:
  nodeSelector:
    kubernetes.io/arch: amd64               # Exclude ARM edge nodes

longhornDriver:
  nodeSelector:
    kubernetes.io/arch: amd64

longhornUI:
  nodeSelector:
    corekinect.com/role: server                 # UI only on server nodes
  tolerations:
    - key: corekinect.com/role
      value: server
      effect: PreferNoSchedule
```

---

## 4. Namespaces

### Namespace Definitions

| Namespace | Purpose | Who deploys here |
|-----------|---------|------------------|
| `production` | Live workloads serving real users/processes | Super Admins only |
| `staging` | Pre-production testing, mirrors production config | Admins + Developers |
| `dev` | Development and experimentation | Admins + Developers |
| `longhorn-system` | Longhorn storage (created by Helm) | Infra scripts only |

The existing `default` namespace should eventually be emptied of workloads.
Nothing new gets deployed there.

### Namespace Labels

Each namespace gets standard labels for policy targeting:

```yaml
metadata:
  labels:
    corekinect.com/environment: production | staging | dev
    pod-security.kubernetes.io/enforce: baseline
```

The `pod-security.kubernetes.io/enforce: baseline` label enables the built-in
Pod Security Standards at the `baseline` level. This blocks the most dangerous
pod configurations (hostPID, hostNetwork, privileged) unless explicitly
exempted. We use `baseline` rather than `restricted` because your
manufacturing workloads need some elevated privileges.

---

## 5. RBAC

### Design Principles

- Use **ClusterRoles** to define permission sets (reusable, defined once).
- Use **RoleBindings** (namespaced) to grant those permissions in specific
  namespaces.
- Users/groups get bound via **Group** subjects so you can manage membership
  in your identity provider rather than editing RBAC manifests.
- Kubeconfig generation uses K8s service accounts + tokens (or CSR-based
  certs if you prefer).

### Role Definitions

#### 1. `concord-super-admin`

Full cluster access. Equivalent to `cluster-admin` but scoped as a custom
ClusterRole so it shows up clearly in audits.

| Resource | Verbs | Scope |
|----------|-------|-------|
| `*` | `*` | Cluster-wide |

**Bound via**: ClusterRoleBinding (not namespaced - applies everywhere)

**Use case**: Platform operators who deploy to production, manage RBAC,
handle storage, etc.

#### 2. `concord-admin`

Can view production. Full control of staging and dev.

| Namespace | Permissions |
|-----------|-------------|
| `production` | `get`, `list`, `watch` on all resources |
| `staging` | `*` on all resources |
| `dev` | `*` on all resources |

**Implemented as**:
- ClusterRole `concord-namespace-readonly` (get/list/watch on common resources)
- ClusterRole `concord-namespace-admin` (full CRUD on common resources)
- RoleBinding in `production` -> `concord-namespace-readonly` for group `concord-admins`
- RoleBinding in `staging` -> `concord-namespace-admin` for group `concord-admins`
- RoleBinding in `dev` -> `concord-namespace-admin` for group `concord-admins`

#### 3. `concord-developer`

No access to production at all. Full control of staging and dev.

| Namespace | Permissions |
|-----------|-------------|
| `production` | **none** |
| `staging` | `*` on all resources |
| `dev` | `*` on all resources |

**Implemented as**:
- RoleBinding in `staging` -> `concord-namespace-admin` for group `concord-developers`
- RoleBinding in `dev` -> `concord-namespace-admin` for group `concord-developers`

#### 4. `concord-viewer`

Read-only access to specified namespaces. Useful for dashboards, CI
read access, stakeholders.

| Namespace | Permissions |
|-----------|-------------|
| `production` | `get`, `list`, `watch` |
| `staging` | `get`, `list`, `watch` |
| `dev` | `get`, `list`, `watch` |

**Implemented as**:
- RoleBinding in each namespace -> `concord-namespace-readonly` for group `concord-viewers`

### What "Common Resources" Means

The `concord-namespace-admin` and `concord-namespace-readonly` ClusterRoles
cover these API resources:

```
pods, pods/log, pods/exec, pods/portforward
deployments, replicasets, statefulsets, daemonsets
services, endpoints, ingresses
configmaps, secrets
persistentvolumeclaims
jobs, cronjobs
events
horizontalpodautoscalers
```

They do NOT cover cluster-scoped resources (nodes, namespaces,
clusterroles, storageclasses, PVs). Only `concord-super-admin` can
touch those.

### Kubeconfig Generation

`ctl.sh` will include a `generate-kubeconfig` command that:

1. Creates a ServiceAccount in the appropriate namespace
2. Creates a long-lived token (or short-lived via TokenRequest API)
3. Binds it to the correct role via a RoleBinding
4. Outputs a kubeconfig file ready to hand to the user

Usage:
```bash
./ctl.sh generate-kubeconfig --role admin --user jdoe --output jdoe.kubeconfig
```

---

## 6. Additional Cluster Concerns

### 6a. Resource Quotas

Prevent any single namespace from consuming the entire cluster.

| Namespace | CPU Request Limit | Memory Request Limit | PVC Count | PVC Storage |
|-----------|-------------------|----------------------|-----------|-------------|
| `production` | 4 cores | 8 Gi | 10 | 40 Gi |
| `staging` | 2 cores | 4 Gi | 5 | 20 Gi |
| `dev` | 2 cores | 4 Gi | 5 | 10 Gi |

These are starting values. Tuned as real usage patterns emerge. The quotas
are applied per-namespace and don't affect `kube-system` or `longhorn-system`.

### 6b. LimitRanges

Set default resource requests/limits so that pods without explicit resource
specs don't run unbounded.

Per namespace:
```yaml
default:
  cpu: 250m
  memory: 256Mi
defaultRequest:
  cpu: 100m
  memory: 128Mi
max:
  cpu: 2000m
  memory: 2Gi
```

This means if a developer deploys a pod without specifying resources, it
automatically gets 100m CPU request / 250m limit and 128Mi memory request /
256Mi limit. No pod can request more than 2 cores / 2Gi without an
explicit quota exemption.

### 6c. Network Policies

Basic namespace isolation so that workloads in `dev` can't talk to pods in
`production`:

- **Default deny all ingress** in each namespace
- **Allow intra-namespace traffic** (pods within the same namespace can talk)
- **Allow DNS** (all pods can reach kube-dns in kube-system)
- **Production ingress from Traefik only** (external traffic comes through
  the ingress controller, not from other namespaces)
- **Staging can reach production services** only if you explicitly create
  an allow rule (not created by default)

This prevents lateral movement between environments while keeping things
simple. Each policy is a short, readable YAML.

### 6d. Ingress & TLS

Traefik is already running. The infra setup should:

- Create an `IngressRoute` or `Ingress` pattern that the app Helm chart
  will follow (not created here - that's the app chart's job)
- Document the expected DNS pattern:
  - `app.concord.example.com` -> production
  - `staging.concord.example.com` -> staging
  - `dev.concord.example.com` -> dev

TLS certificate management is out of scope for this infra layer. Options
for later: cert-manager with Let's Encrypt, or manual certs via Traefik's
static config. Just noting it here so it's not forgotten.

### 6e. Cleanup of Current State

Before applying v2, the existing cluster needs cleanup:

1. Delete the stuck Terminating pod (`mtib-server-manufacturing-...-m9xwl`)
   with `--force --grace-period=0`
2. Clean up stale ReplicaSets (8 for sigma5, 11 for theta, etc.)
3. Clean up old completed/failed Jobs from 83 days ago
4. Remove the `node.longhorn.io/create-default-disk=true` labels from agent
   nodes (Longhorn Helm values will handle this properly)
5. Migrate workloads out of `default` namespace into proper namespaces
   (this happens at app chart level, not infra)

Steps 1-4 will be a `cleanup` command in `ctl.sh`.

---

## 7. Execution Order

The `ctl.sh` script will run these steps in order:

```
1. 00-labels-taints.sh        # Label all nodes (taints opt-in via --with-taints)
2. 01-namespaces.yaml          # Create namespaces
3. helm install longhorn        # Install Longhorn with 02-longhorn-values.yaml
4. 03-storage-classes.yaml     # Create/update storage classes
5. kubectl wait longhorn        # Wait for Longhorn to be ready
6. 04-rbac.yaml                # Apply all RBAC resources
7. 05-resource-quotas.yaml     # Apply resource quotas
8. 06-limit-ranges.yaml        # Apply limit ranges
9. 07-network-policies.yaml   # Apply network policies
```

Each step is idempotent. Running `ctl.sh` again just reconciles to the
desired state.

### Commands

```bash
./ctl.sh apply          # Run all steps
./ctl.sh apply --step 3 # Run only step 3 (Longhorn install)
./ctl.sh status         # Show current state of all resources
./ctl.sh cleanup        # Clean up stale resources (see 6e)
./ctl.sh generate-kubeconfig --role <role> --user <name> --output <file>
```

---

## 8. File Manifest

All v2 files are in place:

| File | Description |
|------|-------------|
| `deploy/infra/terraform/.gitkeep` | Placeholder for future cloud IaC |
| `deploy/infra/terraform/README.md` | Documents purpose of terraform dir |
| `deploy/infra/v2/00-labels-taints.sh` | Node labeling and optional tainting script |
| `deploy/infra/v2/01-namespaces.yaml` | Namespace definitions (production, staging, dev) |
| `deploy/infra/v2/02-longhorn-values.yaml` | Longhorn Helm chart values |
| `deploy/infra/v2/03-storage-classes.yaml` | StorageClass definitions (longhorn, longhorn-ephemeral) |
| `deploy/infra/v2/04-rbac.yaml` | ClusterRoles, RoleBindings for all 4 permission levels |
| `deploy/infra/v2/05-resource-quotas.yaml` | Per-namespace resource quotas |
| `deploy/infra/v2/06-limit-ranges.yaml` | Default resource boundaries per namespace |
| `deploy/infra/v2/07-network-policies.yaml` | Namespace isolation network policies |
| `deploy/infra/v2/ctl.sh` | Main orchestration script |
| `deploy/infra/v2/README.md` | Usage documentation |

Legacy files removed: `deploy/infra/ctl.sh`, `deploy/infra/README.md`,
`deploy/infra/roles/admin.yaml`, `deploy/infra/roles/`, `deploy/infra/labels/`.

