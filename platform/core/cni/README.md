# platform/core/cni

Pod networking. Installed first on every cluster — nothing else runs without
a CNI plugin.

## Default implementation

**Cilium** (Helm chart: `cilium/cilium`). Chosen because:
- eBPF-based datapath is fast and observable.
- Native support for NetworkPolicy + cluster-wide L7 policies.
- Hubble observability pairs well with our `platform/services/observability/`.
- Works on kubeadm, k3s, OKE, EKS, AKS without custom bootstrap.

## Fulfills
- Implicit: all pod-to-pod networking. No app-visible contract.

## Dependencies
- None (installed first on every cluster).

## Status

STUB — no manifests yet. Pin chart version in `helm/values.yaml` when the
first cluster lands.

## TODO (when populating)
- Choose kube-proxy replacement vs coexist per cluster.
- Enable Hubble UI behind cluster ingress + SSO.
- Decide on BGP vs VXLAN overlay per cluster (Tailscale-joined nodes may
  prefer the overlay).
