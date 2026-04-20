# clusters/templates

Blueprints for cluster instances. Each directory is a template; `new-cluster`
copies it verbatim into `clusters/instances/<name>/`.

| Template                          | Purpose                                              |
|-----------------------------------|------------------------------------------------------|
| `cluster-cloud-aws-eks`           | Managed EKS control plane + node groups              |
| `cluster-cloud-oracle-oke`        | Oracle OKE (Always-Free tier friendly)               |
| `cluster-cloud-azure-aks`         | Managed AKS                                          |
| `cluster-kubernetes-manual-k3s`   | k3s on bare machines registered in `machines/hosts/` |

All templates are currently `.gitkeep` placeholders. Populate a template
with a real skeleton only when the first cluster of that flavor is being
created — keeps the repo from carrying unused scaffolding.
