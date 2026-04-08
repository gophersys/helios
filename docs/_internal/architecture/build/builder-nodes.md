# Builder Node Architecture

Concord CI uses a DaemonSet to deploy firmware build workers on all nodes labeled as builders. This allows dynamic scaling - add your machine as a builder and it automatically joins the build pool.

## How It Works

1. **Node Label**: Any K8s node with `corekinect.com/purpose=builder` runs a build worker
2. **DaemonSet**: `concord-build-worker` DaemonSet spawns one pod per builder node
3. **Auto-scaling**: Add/remove builder nodes by labeling them
4. **Resource Isolation**: Builders have generous CPU/memory limits (8 CPU, 14Gi)

## Current Builder Nodes

| Node | Specs | Status |
|------|-------|--------|
| concordproxy | 8 cores, 16GB RAM | Active |
| (your-wsl) | varies | Add via instructions below |

## Adding Your WSL as a Builder Node

### Prerequisites

1. K3s agent installed on your WSL
2. Network access to the Concord cluster
3. Docker/containerd for pulling build images

### Step 1: Install K3s Agent

On your WSL instance:

```bash
# Get the cluster token from a server node
# SSH to concordserver01 and run:
sudo cat /var/lib/rancher/k3s/server/node-token

# On your WSL, install k3s agent
curl -sfL https://get.k3s.io | K3S_URL=https://concordserver01:6443 K3S_TOKEN=<token> sh -s - agent
```

### Step 2: Label Your Node

From any machine with kubectl access:

```bash
# Find your node name
kubectl get nodes

# Label it as a builder
kubectl label node <your-node-name> corekinect.com/purpose=builder

# Optional: Add taint to prevent other workloads
kubectl taint nodes <your-node-name> corekinect.com/purpose=builder:PreferNoSchedule
```

### Step 3: Verify

```bash
# Check DaemonSet
kubectl get daemonset -n staging concord-build-worker

# Should show DESIRED increased by 1
# Check pods
kubectl get pods -n staging -l app=concord-build-worker -o wide

# Your node should have a pod
```

### Step 4: When Done

To remove your machine from the build pool:

```bash
# Remove the label
kubectl label node <your-node-name> corekinect.com/purpose-

# The DaemonSet will automatically remove the pod
```

## Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │         Concord API Server          │
                    │  GET /v2/ci/builds?status=QUEUED    │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
            │ concordproxy  │ │  your-wsl │ │ future-node   │
            │ (builder)     │ │ (builder) │ │ (builder)     │
            ├───────────────┤ ├───────────┤ ├───────────────┤
            │ build-worker  │ │ build-    │ │ build-worker  │
            │ pod (NCS 2.7) │ │ worker    │ │ pod           │
            └───────────────┘ └───────────┘ └───────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │    MinIO (Build Scripts)      │
                    │    ci/build-scripts/alpha/    │
                    └───────────────────────────────┘
```

## Build Worker Configuration

Each build worker container includes:

- **NCS 2.7.0**: Nordic Connect SDK for Alpha, Sigma5 firmware
- **NCS 2.4.2**: (Optional) For legacy Theta firmware
- **Zephyr SDK**: ARM toolchain
- **west**: Zephyr build tool

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CONCORD_API_URL` | API endpoint for job polling |
| `CONCORD_API_KEY` | Authentication key |
| `WORKER_ID` | Node name (from fieldRef) |
| `NCS_VERSION` | SDK version (2.7.0 or 2.4.2) |
| `PRODUCT_FILTER` | Optional: only build specific products |

### Resource Requirements

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 4 | 8 |
| Memory | 8Gi | 14Gi |
| Disk (emptyDir) | - | 30Gi |

## Troubleshooting

### Pod Stuck Pending

```bash
# Check node resources
kubectl describe node <builder-node> | grep -A 10 "Allocated"

# Check resource quota
kubectl describe resourcequota -n staging
```

### Build Not Starting

```bash
# Check worker logs
kubectl logs -n staging -l app=concord-build-worker

# Verify API connectivity
kubectl exec -n staging -l app=concord-build-worker -- curl -s http://concord-http-api:9001/health
```

### SSH Clone Failures

```bash
# Check SSH key mount
kubectl exec -n staging -l app=concord-build-worker -- ls -la /root/.ssh/

# Test SSH access
kubectl exec -n staging -l app=concord-build-worker -- ssh -T git@bitbucket.org
```
