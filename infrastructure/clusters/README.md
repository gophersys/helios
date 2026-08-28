# clusters

Kubernetes clusters — one directory per real cluster under `instances/`.
Blueprints under `templates/`.

This subtree is intentionally sparse for now. Clusters show up when there
is a real one to model, via:

    bash clusters/ctl.sh new-cluster <template> <cluster-name>

Available templates (stubs — each is a `.gitkeep` until a cluster is
actually created):

- `cluster-cloud-aws-eks`
- `cluster-cloud-oracle-oke`
- `cluster-cloud-azure-aks`
- `cluster-kubernetes-manual-k3s`

See `CONVENTIONS.md` for the instance file layout.
