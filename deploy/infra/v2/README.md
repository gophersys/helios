# Concord Infrastructure v2

Takes a barebones K3s cluster to a fully-ready state for deploying
application Helm charts.

## Prerequisites

- `kubectl` configured with cluster-admin access
- `helm` v3 installed
- Cluster nodes online and joined

## Node Architecture

All nodes are labeled with `corekinect.com/role` and `corekinect.com/purpose`:

| Node | Role | Purpose | Description |
|------|------|---------|-------------|
| concordserver01-03 | `server` | `platform` | Core services: http-api, databases, UI, Vault |
| concordagent01-02 | `agent` | `manufacturing` | Ephemeral compute (theta/sigma5 fixtures), Longhorn storage |
| concordagent03 | `agent` | _(none)_ | Idle agent, Longhorn storage |
| verdin-imx8mm-* (5 nodes) | `edge` | `manufacturing` | MTIB custom hardware servers |
| verdin-imx8mm-15702161 | `edge` | `validation` | MTIB validation hardware |

## Quick Start

```bash
# Apply everything (steps 0-7 in order)
./ctl.sh apply

# Apply a single step
./ctl.sh apply --step 2

# Check cluster state
./ctl.sh status

# Clean up stale resources
./ctl.sh cleanup
```

## Steps

| # | File | What it does |
|---|------|--------------|
| 0 | `00-labels-taints.sh` | Labels nodes with `corekinect.com/role` and `corekinect.com/purpose`; taints opt-in via `--with-taints` |
| 1 | `01-namespaces.yaml` | Creates `production`, `staging`, `dev` namespaces |
| 2 | `02-longhorn-values.yaml` | Installs Longhorn via Helm (storage on agent nodes) |
| 3 | `03-storage-classes.yaml` | Creates `longhorn-ephemeral` storage class |
| 4 | `04-rbac.yaml` | RBAC: super-admin, admin, developer, viewer roles |
| 5 | `05-resource-quotas.yaml` | Per-namespace CPU/memory/storage quotas |
| 6 | `06-limit-ranges.yaml` | Default resource requests/limits for pods |
| 7 | `07-network-policies.yaml` | Namespace isolation (deny cross-namespace by default) |

## RBAC Roles

| Role | Production | Staging | Dev |
|------|------------|---------|-----|
| super-admin | Full access | Full access | Full access |
| admin | Read-only | Full access | Full access |
| developer | No access | Full access | Full access |
| viewer | Read-only | Read-only | Read-only |

### Generating a kubeconfig

```bash
./ctl.sh generate-kubeconfig --role developer --user jdoe --output jdoe.kubeconfig
```

## Storage

Longhorn runs on agent nodes only (44 GiB each, 132 GiB total across 3 nodes).
Two storage classes:

- **`longhorn`** (default) - 2 replicas, `Retain` reclaim policy. For databases
  and persistent data.
- **`longhorn-ephemeral`** - 1 replica, `Delete` reclaim policy. For scratch
  volumes and temp data.

### PV Recovery

If a PVC is deleted but the PV remains (Retain policy), recover it:

```bash
# Find the released PV
kubectl get pv | grep Released

# Remove the old claim reference
kubectl patch pv <pv-name> -p '{"spec":{"claimRef":null}}'

# Create a new PVC that binds to it
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-recovered-pvc
  namespace: production
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 5Gi
  volumeName: <pv-name>
  storageClassName: longhorn
EOF
```
