# providers/aws

Reusable Terraform modules for AWS. Intended contents once populated:

- `modules/vpc/` — VPC with public + private subnets, NAT, endpoints.
- `modules/eks/` — EKS control plane + managed node groups. IRSA + OIDC
  provider enabled by default.
- `modules/ecr/` — container registries per app, lifecycle policies.
- `modules/iam/` — assume-role and service-account role factories.
- `modules/dns/` — Route53 hosted zones + ACM certs (DNS-validated).

Consumers (cluster instances) reference these via relative path:

```hcl
module "vpc" {
  source = "../../../providers/aws/modules/vpc"
  ...
}
```

TODO: modules not yet written. First module arrives when the first AWS
cluster is created.
