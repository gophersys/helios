# cluster-kubernetes-manual-k3s

Template for a self-managed K3s cluster bootstrapped on Ansible-managed
hosts (typically Tailscale-joined).

Use this template when:
- You have hosts you manage yourself (OCI Always-Free, AWS, bare-metal,
  homelab) and want a K8s cluster on top.
- You're NOT using a cloud's managed K8s (EKS/AKS/OKE — use those templates
  instead).
- Cost or control matters more than managed-service convenience.

## What gets created

Running `bash clusters/ctl.sh new-cluster cluster-kubernetes-manual-k3s <name>`
scaffolds:

```
clusters/instances/<name>/
├── identity.yaml             # from this template's cluster-identity.yaml
├── nodes/                    # populate with node definitions later
└── overlays/                 # platform component overrides
```

## Node templates

Under this template's `nodes/` dir:

- `linux-k3s-node/` — a single node template that serves both `server` and
  `agent` roles (set `kubernetes.role` in the node's identity.yaml).

Scaffold a node with:
```
bash clusters/ctl.sh new-cluster-node <cluster> linux-k3s-node <hostname>
```

## Bring-up sequence (manual, for now)

1. Declare each node in `clusters/instances/<c>/nodes/<host>/identity.yaml`.
2. Ansible `k3s-install` playbook runs against the declared nodes:
   - Server first; wait for `k3s-ready`.
   - Agents in parallel, passing the server's `K3S_TOKEN`.
3. Apply `platform/core/*` in order (see `platform/CONVENTIONS.md`).
4. Apply any `platform/services/*` the cluster opts into.
5. Regenerate cluster index (future: `clusters/ctl.sh generate-index`).

Status: template only — the Ansible playbooks and the `new-cluster-node`
verb are future work.
