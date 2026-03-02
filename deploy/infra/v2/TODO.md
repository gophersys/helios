# Infrastructure TODO

> Tracked items discovered during Stage 4 validation proof setup (2026-03-01).
> These do not block Stage 4 but should be resolved before production validation.

## Cluster Cleanup

### ~~`00-labels-taints.sh` is stale~~ — DONE

Updated in `00-labels-taints.sh`:
- Removed 5 stale manufacturing edge nodes from `EDGE_MANUFACTURING`
- Added `verdin-imx8mm-15005665` (REV 1.2) to `EDGE_VALIDATION`
- Added `EDGE_MTIB_REVISION` associative array for per-node MTIB hardware version
- `label_node()` now applies `corekinect.com/mtib-revision` label on edge nodes
- `label_node()` now assigns `node-role.kubernetes.io/edge` role on edge nodes
- Status summary line includes `mtib-revision` column

**Run to apply:** `bash deploy/infra/v2/00-labels-taints.sh` (from a machine with kubectl access)

### K3s Version Skew

Edge nodes run `v1.28.7-k3s1`, cluster control plane runs `v1.33.5+k3s1`.
This is a 5 minor version gap (supported skew is +/-1). Upgrade the K3s
agent on both Verdin boards to match the cluster version, or at least
bring it within the supported skew window.

**How to upgrade (SSH to each Verdin):**
```bash
ssh torizon@10.4.45.33   # or 10.4.45.32
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.33.5+k3s1" K3S_URL=https://<server>:6443 K3S_TOKEN=<token> sh -
```

### ~~Edge Nodes Have No K8s Roles~~ — DONE (in labels script)

Handled by `label_node()` — now assigns `node-role.kubernetes.io/edge` automatically.

## Validation Deployment Manifests

### ~~Split `validation.yaml` into per-revision manifests~~ — DONE

Already created:
- `deploy/edge/mtib-server/validation-rev11.yaml` — targets `mtib-revision=1.1` node
- `deploy/edge/mtib-server/validation-rev12.yaml` — targets `mtib-revision=1.2` node

After Phase 1 adds hardware auto-detection (TCA9534A probe), these can
optionally be consolidated back into a single manifest.
