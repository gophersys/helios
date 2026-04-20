# providers/kubernetes-manual

"Provisioner" for manual K3s installs on hosts that have already been
created by another provider (oracle / aws / bare-metal). Not Terraform per
se — an Ansible playbook set that:
1. Installs k3s on target hosts.
2. Joins agents to the server using a shared token.
3. Emits a kubeconfig pointing at the cluster's ingress (or tailnet IP).

Consumers: `cluster-kubernetes-manual-k3s` cluster template.

## Planned contents

- `ansible/` — `k3s-install`, `k3s-join`, `k3s-upgrade`, `k3s-drain` playbooks.
- `scripts/` — bootstrap helpers (token rotation, kubeconfig emit to tmpfs).
- `modules/kubeconfig/` — Terraform module that reads kubeconfig from tmpfs
  and returns a handle consumers can pass to the Helm provider.

These modules coordinate with Ansible roles in
`machines/roles/developer-kubernetes-operator/` (kubectl/helm install on
the local operator host).

## Status

STUB. Populate when `app-prod` node bring-up is ready to be automated
(today it was manual ssh-in).
