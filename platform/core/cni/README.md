# platform/core/cni

Pod networking. It is installed first on every cluster, because nothing else runs
without a CNI plugin.

## Default implementation

**Cilium**, from the Helm chart `cilium/cilium`. We chose it for 4 reasons:
- Its datapath is based on eBPF, so it is fast and you can observe it.
- It supports NetworkPolicy and cluster-wide L7 policies natively.
- Its Hubble observability works well with our
  `platform/services/observability/`.
- It works on kubeadm, k3s, OKE, EKS and AKS with no custom bootstrap.

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
