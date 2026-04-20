# providers

Reusable Terraform modules, one subdirectory per cloud/substrate. Consumed
by cluster instances under `clusters/instances/<name>/terraform/`.

| Provider              | Purpose                                     |
|-----------------------|---------------------------------------------|
| `aws/`                | VPC, IAM, EKS, ECR, Route53, ACM            |
| `azure/`              | Resource groups, networking, AKS            |
| `oracle/`             | VCN, compartments, compute, OKE             |
| `kubernetes-manual/`  | k3s install + kubeconfig emission           |

Each provider directory is a self-contained Terraform root module library:
multiple sibling modules that cluster roots can `module "..." { source = "../../providers/<provider>/<module>" }`.

Providers do not carry state of their own — consumers own state. Providers
are pure libraries.
