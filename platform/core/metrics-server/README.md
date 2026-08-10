# platform/core/metrics-server

The baseline metrics for a node and a pod. `kubectl top` and the Horizontal Pod
Autoscaler need them. This is not the monitoring stack. It is the resource
metrics API of the kubelet only.

## Default implementation

**metrics-server**, from the Helm chart `metrics-server/metrics-server`. It is a
standard deployment with 1 replica per cluster, and 2 replicas for HA on a
cluster with several nodes.

## Fulfills
- Implicit: the Kubernetes `metrics.k8s.io` API. Used by HPA and `kubectl top`.

## Dependencies
- None beyond a running cluster (self-contained).

## Status

STUB.

## TODO, when we populate this component
- Pin the chart version.
- Enable the TLS verification of the host. It is off by default on k3s. Turn it
  on for a managed cluster that exposes correct kubelet certificates.
- Verify that the HPA works against it, with a canary deployment.
