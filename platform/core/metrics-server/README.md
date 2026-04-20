# platform/core/metrics-server

Baseline node + pod metrics. Required for `kubectl top` and Horizontal Pod
Autoscaler. Not the monitoring stack — just the kubelet resource metrics API.

## Default implementation

**metrics-server** (Helm chart: `metrics-server/metrics-server`). Stock
deployment, one replica per cluster (two on multi-node clusters for HA).

## Fulfills
- Implicit: the Kubernetes `metrics.k8s.io` API. Used by HPA and `kubectl top`.

## Dependencies
- None beyond a running cluster (self-contained).

## Status

STUB.

## TODO (when populating)
- Pin chart version.
- Enable host TLS verification (default-off on k3s; flip on for managed
  clusters that expose proper kubelet certs).
- Verify HPA works against it with a canary deployment.
