# cluster-cloud-oracle-oke

Template for Oracle-managed Kubernetes (OKE). OCI runs the control plane
(OKE Basic's control plane is free).

## When to use

- Exploiting OCI Always-Free A1.Flex capacity at scale.
- Need an Oracle-managed alternative to our self-managed K3s when ops
  complexity outweighs cost savings.

## Note vs manual K3s

Our current `prod` runs self-managed K3s on OCI — **not** OKE. That
decision was deliberate: the A1.Flex nodes are joined to a Tailscale mesh
with AWS nodes, which is awkward under OKE's managed networking.

Populate this template only if a future cluster needs OCI-native managed
K8s semantics (e.g., tight integration with OCI IAM, Object Storage state,
Logging, etc.).

## Status

Stub.
