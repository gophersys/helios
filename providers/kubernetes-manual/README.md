# providers/kubernetes-manual

Modules for manually-provisioned Kubernetes clusters on hosts enrolled in
`machines/hosts/`. Primary target: k3s on mixed-architecture tailnet nodes.

Intended contents once populated:

- `modules/k3s-server/` — bootstrap a k3s server on a machine, emit
  kubeconfig into an output that cluster instances can consume.
- `modules/k3s-agent/` — register a machine as an agent, joining a
  running server via node token.
- `modules/kubeconfig/` — helper that writes kubeconfig to tmpfs and
  returns a handle for consuming modules.

These modules coordinate with Ansible roles in
`machines/roles/developer-kubernetes-operator/` (kubectl/helm install on
the local operator host) and the manual `k3s` install on each machine.

TODO: modules not yet written.
